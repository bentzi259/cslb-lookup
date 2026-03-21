"""CSLB license scraper - direct HTTP requests to the CSLB website."""

import re

import httpx

from app.models import (
    BusinessInformation,
    Classification,
    ContractorsBond,
    LicenseResponse,
    LicenseStatus,
    PersonnelMember,
    WorkersCompensation,
)

CSLB_DETAIL_URL = (
    "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
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
    start_pattern = rf'id="{re.escape(element_id)}"[^>]*>'
    match = re.search(start_pattern, html, re.DOTALL)
    if not match:
        return None
    start = match.end()
    depth = 1
    pos = start
    while depth > 0 and pos < len(html):
        next_open = html.find("<td", pos)
        next_close = html.find("</td>", pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 3
        else:
            depth -= 1
            if depth == 0:
                return html[start:next_close]
            pos = next_close + 5
    return None


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
    company_match = re.search(r'<a[^>]*>([^<]+)</a>', raw)
    if company_match:
        result["bond_company"] = company_match.group(1).strip()

    number_match = re.search(r"Bond Number:\s*</strong>\s*([^<]+)", raw)
    if number_match:
        result["bond_number"] = number_match.group(1).strip()

    amount_match = re.search(r"Bond Amount:\s*</strong>\s*([^<]+)", raw)
    if amount_match:
        result["bond_amount"] = amount_match.group(1).strip()

    eff_match = re.search(r"Effective Date:\s*</strong>\s*([^<]+)", raw)
    if eff_match:
        result["effective_date"] = eff_match.group(1).strip()

    return result


def _parse_wc_info(html: str) -> dict:
    raw = _get_html_by_id(html, "MainContent_WCStatus")
    if not raw:
        return {}

    result = {}
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    if text:
        first_line = text.split("Policy Number:")[0].strip() if "Policy Number:" in text else text.split(".")[0].strip()
        result["coverage_type"] = first_line or None

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
        result["expire_date"] = exp_match.group(1).strip()

    return result


def _parse_personnel(html: str) -> list[PersonnelMember]:
    raw = _get_html_by_id(html, "MainContent_MultiLicDisplay")
    if not raw:
        return []

    members = []
    # Try table rows first (some licenses list personnel in a table)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", raw, re.DOTALL)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) >= 2:
            name = re.sub(r"<[^>]+>", "", cells[0]).strip()
            role = re.sub(r"<[^>]+>", "", cells[1]).strip()
            if name:
                members.append(PersonnelMember(name=name, role=role or None))

    # Fall back to list items
    if not members:
        items = re.findall(r"<li[^>]*>(.*?)</li>", raw, re.DOTALL)
        for item in items:
            text = re.sub(r"<[^>]+>", "", item).strip()
            if text:
                members.append(PersonnelMember(name=text, role=None))

    return members


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
        additional_status_text = _get_text_by_id(html, "MainContent_AddLicStatus")
        personnel = _parse_personnel(html)

        return LicenseResponse(
            license_number=license_number,
            extract_date=_get_text_by_id(html, "MainContent_extractDate"),
            business_information=BusinessInformation(
                business_name=combined_name,
                address=bus.get("address"),
                phone=bus.get("phone"),
                entity=_get_text_by_id(html, "MainContent_Entity"),
                issue_date=_get_text_by_id(html, "MainContent_IssDt"),
                reissue_date=_get_text_by_id(html, "MainContent_ReissDt"),
                expire_date=_get_text_by_id(html, "MainContent_ExpDt"),
            ),
            license_status=LicenseStatus(
                status=status_text,
                additional_status=additional_status_text,
                inactivation_date=_get_text_by_id(html, "MainContent_InactDt"),
                reactivation_date=_get_text_by_id(html, "MainContent_ReactDt"),
            ),
            contractors_bond=ContractorsBond(
                **_parse_bond_info(html),
            ),
            classifications=_parse_classifications(html),
            workers_compensation=WorkersCompensation(
                **_parse_wc_info(html),
            ),
            personnel=personnel or None,
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
