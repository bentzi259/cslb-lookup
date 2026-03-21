import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security import APIKeyHeader

from app.config import settings
from app.database import db_is_loaded, get_field_values, get_license, get_licenses, get_stats, init_db
from app.scraper_client import scrape_license, scrape_licenses
from app.models import BulkLicenseRequest, BulkResponse, FieldMetadataResponse, LicenseResponse

logger = logging.getLogger("cslb-api")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)):
    if not settings.api_key:
        return  # No key configured = auth disabled
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    loaded = await db_is_loaded()
    if not loaded:
        logger.warning(
            "Database is empty. Run: python -m app.csv_loader <path_to_csv>"
        )
    yield


app = FastAPI(
    title="CSLB Lookup API",
    description=(
        "API for looking up California Contractors State License Board (CSLB) license data. "
        "Returns structured JSON with business info, license status, classifications, bond details, "
        "workers' compensation, and personnel data.\n\n"
        "**Data Sources:**\n"
        "- `csv` (default) — CSLB bulk CSV (~240k records) loaded into SQLite\n"
        "- `scraper` — Direct HTTP scraping of the CSLB website for real-time data\n\n"
        "**Authentication:** Pass `X-API-Key` header for all `/api/*` endpoints."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def _resolve_source(source: str | None) -> str:
    if source and source in ("csv", "scraper"):
        return source
    return settings.data_source


@app.get("/health", summary="Health check", description="Returns API health status and whether the database is loaded. No authentication required.")
async def health():
    loaded = await db_is_loaded()
    return {
        "status": "healthy",
        "database_loaded": loaded,
        "default_source": settings.data_source,
    }


@app.get("/api/stats", dependencies=[Depends(verify_api_key)], summary="Database statistics", description="Returns record count, last import timestamp, and CSV filename.")
async def stats():
    return await get_stats()


@app.get("/api/field-metadata", response_model=FieldMetadataResponse, dependencies=[Depends(verify_api_key)], summary="Field metadata", description="Returns distinct values for enum-like fields from the database. Useful for building filters, dropdowns, and understanding the possible values each field can have.")
async def field_metadata():
    if not await db_is_loaded():
        raise HTTPException(
            status_code=503,
            detail="Database not loaded. Import CSV data first.",
        )
    return await get_field_values()


@app.get("/api/license/{license_number}", response_model=LicenseResponse, dependencies=[Depends(verify_api_key)], summary="Single license lookup", description="Look up a single CSLB license by number. Returns business info, license status, classifications, bond details, workers' compensation, and personnel data.")
async def lookup_license(
    license_number: str,
    source: str | None = Query(None, regex="^(csv|scraper)$", description="Data source: csv (default) or scraper"),
):
    license_number = license_number.strip()
    if not license_number.isdigit() or len(license_number) > 8:
        raise HTTPException(status_code=400, detail="Invalid license number format")

    resolved_source = _resolve_source(source)

    if resolved_source == "scraper":
        result = scrape_license(license_number)
        if not result:
            raise HTTPException(status_code=404, detail="License not found")
        return result

    # CSV/SQLite lookup
    if not await db_is_loaded():
        raise HTTPException(
            status_code=503,
            detail="Database not loaded. Import CSV data first.",
        )
    result = await get_license(license_number)
    if not result:
        raise HTTPException(status_code=404, detail="License not found")
    return result


@app.post("/api/licenses", response_model=BulkResponse, dependencies=[Depends(verify_api_key)], summary="Bulk license lookup", description="Look up multiple licenses at once. CSV source supports up to 100 licenses per request, scraper supports up to 10.")
async def bulk_lookup(request: BulkLicenseRequest):
    resolved_source = _resolve_source(request.source)

    # Validate limits
    max_count = 10 if resolved_source == "scraper" else 100
    if len(request.license_numbers) > max_count:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_count} license numbers per request for {resolved_source} source",
        )

    # Validate format
    errors = []
    valid_numbers = []
    for num in request.license_numbers:
        num = num.strip()
        if not num.isdigit() or len(num) > 8:
            errors.append({"license_number": num, "error": "Invalid format"})
        else:
            valid_numbers.append(num)

    if resolved_source == "scraper":
        results = scrape_licenses(valid_numbers)
    else:
        if not await db_is_loaded():
            raise HTTPException(
                status_code=503,
                detail="Database not loaded. Import CSV data first.",
            )
        results = await get_licenses(valid_numbers)

    # Report not-found as errors
    found_numbers = {r.license_number for r in results}
    for num in valid_numbers:
        if num not in found_numbers:
            errors.append({"license_number": num, "error": "Not found"})

    return BulkResponse(results=results, errors=errors if errors else None)


def _merge_responses(
    csv: LicenseResponse | None, scraper: LicenseResponse | None
) -> LicenseResponse | None:
    if not csv and not scraper:
        return None
    if not csv:
        return scraper.model_copy(update={"data_source": "combined"})
    if not scraper:
        return csv.model_copy(update={"data_source": "combined"})

    # CSV as base, overlay scraper-only fields, fallback for nulls
    bi = csv.business_information
    sbi = scraper.business_information
    merged_bi = bi.model_copy(update={
        "business_name": bi.business_name or sbi.business_name,
        "address": bi.address or sbi.address,
        "phone": bi.phone or sbi.phone,
        "entity": bi.entity or sbi.entity,
        "issue_date": bi.issue_date or sbi.issue_date,
        "reissue_date": bi.reissue_date or sbi.reissue_date,
        "expire_date": bi.expire_date or sbi.expire_date,
    })

    ls = csv.license_status
    sls = scraper.license_status
    merged_ls = ls.model_copy(update={
        "status": ls.status or sls.status,
        "additional_status": scraper.license_status.additional_status,
        "inactivation_date": ls.inactivation_date or sls.inactivation_date,
        "reactivation_date": ls.reactivation_date or sls.reactivation_date,
    })

    cb = csv.contractors_bond
    scb = scraper.contractors_bond
    merged_cb = cb.model_copy(update={
        "bond_number": cb.bond_number or scb.bond_number,
        "bond_amount": cb.bond_amount or scb.bond_amount,
        "bond_company": cb.bond_company or scb.bond_company,
        "effective_date": cb.effective_date or scb.effective_date,
    })

    wc = csv.workers_compensation
    swc = scraper.workers_compensation
    merged_wc = wc.model_copy(update={
        "coverage_type": wc.coverage_type or swc.coverage_type,
        "insurance_company": wc.insurance_company or swc.insurance_company,
        "policy_number": wc.policy_number or swc.policy_number,
        "effective_date": wc.effective_date or swc.effective_date,
        "expire_date": wc.expire_date or swc.expire_date,
    })

    return LicenseResponse(
        license_number=csv.license_number,
        last_update=csv.last_update,
        extract_date=scraper.extract_date,
        business_information=merged_bi,
        license_status=merged_ls,
        contractors_bond=merged_cb,
        classifications=csv.classifications or scraper.classifications,
        workers_compensation=merged_wc,
        personnel=scraper.personnel,
        asbestos_reg=csv.asbestos_reg,
        data_source="combined",
    )


@app.get("/api/license/{license_number}/combined", response_model=LicenseResponse, dependencies=[Depends(verify_api_key)], summary="Combined license lookup", description="Look up a license using both CSV and scraper sources in parallel, merging the results. Returns the most complete data: CSV fields (county, secondary_status, asbestos_reg) plus scraper fields (additional_status, extract_date, personnel).")
async def combined_lookup(license_number: str):
    license_number = license_number.strip()
    if not license_number.isdigit() or len(license_number) > 8:
        raise HTTPException(status_code=400, detail="Invalid license number format")

    db_loaded = await db_is_loaded()

    async def _csv():
        return await get_license(license_number) if db_loaded else None

    csv_result, scraper_result = await asyncio.gather(
        _csv(), asyncio.to_thread(scrape_license, license_number), return_exceptions=True
    )

    if isinstance(csv_result, Exception):
        csv_result = None
    if isinstance(scraper_result, Exception):
        scraper_result = None

    result = _merge_responses(csv_result, scraper_result)
    if not result:
        raise HTTPException(status_code=404, detail="License not found")
    return result


@app.post("/api/licenses/combined", response_model=BulkResponse, dependencies=[Depends(verify_api_key)], summary="Bulk combined license lookup", description="Look up multiple licenses using both CSV and scraper in parallel. Max 50 licenses per request. Each result merges CSV and scraper data for the most complete response.")
async def bulk_combined_lookup(request: BulkLicenseRequest):
    if len(request.license_numbers) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 license numbers per request for combined source",
        )

    errors = []
    valid_numbers = []
    for num in request.license_numbers:
        num = num.strip()
        if not num.isdigit() or len(num) > 8:
            errors.append({"license_number": num, "error": "Invalid format"})
        else:
            valid_numbers.append(num)

    # Launch CSV batch + all scraper requests in parallel
    db_loaded = await db_is_loaded()
    tasks = []
    async def _csv_batch():
        return await get_licenses(valid_numbers) if db_loaded else []

    tasks = [_csv_batch()]
    for num in valid_numbers:
        tasks.append(asyncio.to_thread(scrape_license, num))

    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    # First result is the CSV batch, rest are individual scraper results
    csv_list = task_results[0] if not isinstance(task_results[0], Exception) else []
    csv_map = {r.license_number: r for r in csv_list}

    scraper_map = {}
    for i, num in enumerate(valid_numbers):
        scraper_result = task_results[i + 1]
        if not isinstance(scraper_result, Exception) and scraper_result is not None:
            scraper_map[num] = scraper_result

    results = []
    for num in valid_numbers:
        merged = _merge_responses(csv_map.get(num), scraper_map.get(num))
        if merged:
            results.append(merged)
        else:
            errors.append({"license_number": num, "error": "Not found"})

    return BulkResponse(results=results, errors=errors if errors else None)
