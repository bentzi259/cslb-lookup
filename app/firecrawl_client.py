from firecrawl import FirecrawlApp

from app.config import settings
from app.models import (
    BusinessInfo,
    Classification,
    LicenseResponse,
    LicenseStatus,
    WorkersCompensation,
)

CSLB_SEARCH_URL = (
    "https://www.cslb.ca.gov/onlineservices/checklicenseII/CheckLicense.aspx"
)

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "license_number": {"type": "string"},
        "business_name": {"type": "string"},
        "dba_name": {"type": "string"},
        "address": {"type": "string"},
        "phone": {"type": "string"},
        "issue_date": {"type": "string"},
        "expiration_date": {"type": "string"},
        "business_type": {"type": "string"},
        "status": {"type": "string"},
        "secondary_status": {"type": "string"},
        "bond_amount": {"type": "string"},
        "bond_company": {"type": "string"},
        "classifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "workers_comp_status": {"type": "string"},
        "workers_comp_insurance_company": {"type": "string"},
        "workers_comp_policy_number": {"type": "string"},
        "workers_comp_effective_date": {"type": "string"},
        "workers_comp_expiration_date": {"type": "string"},
    },
}

EXTRACT_PROMPT = (
    "Extract all contractor license details from this CSLB license detail page. "
    "Include the business name, DBA name (if any), full address, phone, issue date, "
    "expiration date, license status, bond information, all classification codes "
    "with descriptions, and workers compensation details."
)


def _get_client() -> FirecrawlApp:
    if not settings.firecrawl_api_key:
        raise ValueError(
            "FIRECRAWL_API_KEY is required when using firecrawl data source"
        )
    return FirecrawlApp(api_key=settings.firecrawl_api_key)


def _build_actions(license_number: str) -> list[dict]:
    return [
        {"type": "wait", "milliseconds": 2000},
        {"type": "click", "selector": 'input[id*="LicNum"]'},
        {"type": "write", "text": license_number},
        {"type": "click", "selector": 'input[id*="BtnSearch"]'},
        {"type": "wait", "milliseconds": 5000},
    ]


def _extract_to_response(data: dict, license_number: str) -> LicenseResponse:
    biz_name = (data.get("business_name") or "").strip()
    dba_name = (data.get("dba_name") or "").strip()
    if biz_name and dba_name:
        combined_name = f"{biz_name} | {dba_name}"
    else:
        combined_name = biz_name or None

    classifications = []
    for c in data.get("classifications") or []:
        if c.get("code"):
            classifications.append(
                Classification(
                    code=c["code"],
                    description=c.get("description", ""),
                )
            )

    return LicenseResponse(
        license_number=license_number,
        business_information=BusinessInfo(
            business_name=combined_name,
            address=data.get("address"),
            phone=data.get("phone"),
            issue_date=data.get("issue_date"),
            expiration_date=data.get("expiration_date"),
            business_type=data.get("business_type"),
        ),
        license_status=LicenseStatus(
            status=data.get("status"),
            secondary_status=data.get("secondary_status"),
            bond_amount=data.get("bond_amount"),
            bond_company=data.get("bond_company"),
        ),
        classifications=classifications,
        workers_compensation=WorkersCompensation(
            status=data.get("workers_comp_status"),
            insurance_company=data.get("workers_comp_insurance_company"),
            policy_number=data.get("workers_comp_policy_number"),
            policy_effective_date=data.get("workers_comp_effective_date"),
            policy_expiration_date=data.get("workers_comp_expiration_date"),
        ),
        data_source="firecrawl",
    )


def scrape_license(license_number: str) -> LicenseResponse | None:
    client = _get_client()
    result = client.scrape_url(
        CSLB_SEARCH_URL,
        params={
            "formats": ["extract"],
            "extract": {"schema": EXTRACT_SCHEMA, "prompt": EXTRACT_PROMPT},
            "actions": _build_actions(license_number),
        },
    )

    extracted = result.get("extract") if result else None
    if not extracted or not extracted.get("license_number"):
        return None

    return _extract_to_response(extracted, license_number)


def scrape_licenses(license_numbers: list[str]) -> list[LicenseResponse]:
    results = []
    for num in license_numbers:
        resp = scrape_license(num)
        if resp:
            results.append(resp)
    return results
