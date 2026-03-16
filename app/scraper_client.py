"""Free CSLB license scraper - replaces Firecrawl with direct HTTP requests."""

import re

import httpx

from app.models import (
    BusinessInfo,
    Classification,
    LicenseResponse,
    LicenseStatus,
    WorkersCompensation,
)

CSLB_DETAIL_URL = (
    "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _get_text_by_id(html: str, element_id: str) -> str | None:
    pattern = rf'id="{re.escape(element_id)}"[^>]*>(.*?)</(?:td|span)>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return None
    text = match.group(1)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _get_html_by_id(html: str, element_id: str) -> str | None:
    pattern = rf'id="{re.escape(element_id)}"[^>]*>(.*?)</td>'
    match = re.search(pattern, html, re.DOTALL)
    return match.group(1) if match else None


def _parse_bus_info(html: str) -> dict:
    raw = _get_html_by_id(html, "MainContent_BusInfo")
    if not raw:
        return {}

    raw = re.sub(r"<br\s*/?>", "\n", raw)
    raw = re.sub(r"<[^>]+>", "", raw)
    raw = re.sub(r"&amp;", "&", raw)
    raw = re.sub(r"&nbsp;", " ", raw)
    lines = [l.strip() for l in raw.strip().split("\n") if l.strip()]

    result = {}
    phone_line = None
    for i, line in enumerate(lines):
        if "Business Phone Number:" in line:
            phone_line = i
            result["phone"] = line.split("Business Phone Number:")[-1].strip()
            break

    if lines:
        result["business_name"] = lines[0]

    if len(lines) > 1 and lines[1].lower().startswith("dba "):
        result["dba_name"] = lines[1][4:].strip()
        addr_start = 2
    else:
        addr_start = 1

    addr_end = phone_line if phone_line else len(lines)
    addr_lines = lines[addr_start:addr_end]
    if addr_lines:
        result["address"] = ", ".join(addr_lines)

    return result


def _parse_classifications(html: str) -> list[Classification]:
    raw = _get_html_by_id(html, "MainContent_ClassCellTable")
    if not raw:
        return []

    classifications = []
    links = re.findall(r">([\w\d]+)\s*-\s*([^<]+)<", raw)
    for code, desc in links:
        classifications.append(Classification(code=code.strip(), description=desc.strip()))

    if not classifications:
        text = re.sub(r"<[^>]+>", "", raw).strip()
        parts = re.findall(r"(\w+\d*)\s*-\s*([^,\n]+)", text)
        for code, desc in parts:
            classifications.append(Classification(code=code.strip(), description=desc.strip()))

    return classifications


def _parse_bond_info(html: str) -> dict:
    raw = _get_html_by_id(html, "MainContent_BondingCellTable")
    if not raw:
        return {}

    result = {}
    amount_match = re.search(r"Bond Amount:\s*</strong>\s*([^<]+)", raw)
    if amount_match:
        result["bond_amount"] = amount_match.group(1).strip()

    company_match = re.search(r'<a[^>]*>([^<]+)</a>', raw)
    if company_match:
        result["bond_company"] = company_match.group(1).strip()

    return result


def _parse_wc_info(html: str) -> dict:
    raw = _get_html_by_id(html, "MainContent_WCStatus")
    if not raw:
        return {}

    result = {}
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    result["status"] = text.split(".")[0].strip() if text else None

    company_match = re.search(r'<a[^>]*>([^<]+)</a>', raw)
    if company_match:
        result["insurance_company"] = company_match.group(1).strip()

    policy_match = re.search(r"Policy Number:\s*</strong>\s*([^<]+)", raw)
    if policy_match:
        result["policy_number"] = policy_match.group(1).strip()

    eff_match = re.search(r"Effective Date:\s*</strong>\s*([^<]+)", raw)
    if eff_match:
        result["effective_date"] = eff_match.group(1).strip()

    exp_match = re.search(r"Expire Date:\s*</strong>\s*([^<]+)", raw)
    if exp_match:
        result["expiration_date"] = exp_match.group(1).strip()

    return result


def scrape_license(license_number: str) -> LicenseResponse | None:
    client = httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS)
    try:
        resp = client.get(CSLB_DETAIL_URL, params={"LicNum": license_number})
        resp.raise_for_status()
        html = resp.text

        if "MainContent_MFError" in html:
            mf_text = _get_text_by_id(html, "MainContent_MFError")
            if mf_text and "maintenance" in mf_text.lower():
                raise ConnectionError("CSLB database is under maintenance")

        err_text = _get_text_by_id(html, "MainContent_ErrMsg")
        if err_text and err_text.strip():
            return None

        lic_num = _get_text_by_id(html, "MainContent_Header2Detail")
        if not lic_num:
            return None

        bus = _parse_bus_info(html)
        biz_name = bus.get("business_name")
        dba = bus.get("dba_name")
        if biz_name and dba:
            combined_name = f"{biz_name} | {dba}"
        else:
            combined_name = biz_name

        status_text = _get_text_by_id(html, "MainContent_Status")

        return LicenseResponse(
            license_number=license_number,
            business_information=BusinessInfo(
                business_name=combined_name,
                address=bus.get("address"),
                phone=bus.get("phone"),
                issue_date=_get_text_by_id(html, "MainContent_IssDt"),
                expiration_date=_get_text_by_id(html, "MainContent_ExpDt"),
                business_type=_get_text_by_id(html, "MainContent_Entity"),
            ),
            license_status=LicenseStatus(
                status=status_text,
                **_parse_bond_info(html),
            ),
            classifications=_parse_classifications(html),
            workers_compensation=WorkersCompensation(
                **_parse_wc_info(html),
            ),
            data_source="scraper",
        )
    finally:
        client.close()


def scrape_licenses(license_numbers: list[str]) -> list[LicenseResponse]:
    results = []
    for num in license_numbers:
        resp = scrape_license(num)
        if resp:
            results.append(resp)
    return results
