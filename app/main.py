import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.config import settings
from app.database import db_is_loaded, get_license, get_licenses, get_stats, init_db
from app.firecrawl_client import scrape_license, scrape_licenses
from app.models import BulkLicenseRequest, BulkResponse, LicenseResponse

logger = logging.getLogger("cslb-api")


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
    title="CSLB License Checker API",
    description="API for checking California Contractors State License Board license data",
    version="1.0.0",
    lifespan=lifespan,
)


def _resolve_source(source: str | None) -> str:
    if source and source in ("csv", "firecrawl"):
        return source
    return settings.data_source


@app.get("/health")
async def health():
    loaded = await db_is_loaded()
    return {
        "status": "healthy",
        "database_loaded": loaded,
        "default_source": settings.data_source,
    }


@app.get("/api/stats")
async def stats():
    return await get_stats()


@app.get("/api/license/{license_number}", response_model=LicenseResponse)
async def lookup_license(
    license_number: str,
    source: str | None = Query(None, regex="^(csv|firecrawl)$"),
):
    license_number = license_number.strip()
    if not license_number.isdigit() or len(license_number) > 8:
        raise HTTPException(status_code=400, detail="Invalid license number format")

    resolved_source = _resolve_source(source)

    if resolved_source == "firecrawl":
        if not settings.firecrawl_api_key:
            raise HTTPException(
                status_code=400,
                detail="FIRECRAWL_API_KEY not configured",
            )
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


@app.post("/api/licenses", response_model=BulkResponse)
async def bulk_lookup(request: BulkLicenseRequest):
    resolved_source = _resolve_source(request.source)

    # Validate limits
    max_count = 10 if resolved_source == "firecrawl" else 100
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

    if resolved_source == "firecrawl":
        if not settings.firecrawl_api_key:
            raise HTTPException(
                status_code=400,
                detail="FIRECRAWL_API_KEY not configured",
            )
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
