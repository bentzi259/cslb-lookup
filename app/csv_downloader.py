"""Download the MasterLicenseData.csv from the CSLB Data Portal.

The CSLB data portal uses ASP.NET Web Forms with a 3-step process:
1. GET the page to obtain ViewState, EventValidation, and cookies
2. AJAX POST to select "License Master" file type (updates ViewState)
3. Regular POST to trigger the CSV file download
"""

import re
import sys

import httpx

PORTAL_URL = "https://www.cslb.ca.gov/onlineservices/dataportal/ContractorList"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _extract_field(html: str, field_name: str) -> str:
    pattern = rf'name="{re.escape(field_name)}"[^>]*value="([^"]*)"'
    match = re.search(pattern, html)
    if not match:
        pattern = rf'id="{re.escape(field_name)}"[^>]*value="([^"]*)"'
        match = re.search(pattern, html)
    if not match:
        raise ValueError(f"Could not find {field_name} in page")
    return match.group(1)


def _extract_from_ajax(response_text: str, field_name: str) -> str:
    pattern = rf"{re.escape(field_name)}\|([^|]*)\|"
    match = re.search(pattern, response_text)
    if not match:
        raise ValueError(f"Could not find {field_name} in AJAX response")
    return match.group(1)


def download_csv(output_path: str) -> bool:
    client = httpx.Client(
        follow_redirects=True,
        timeout=300,
        headers=HEADERS,
    )

    try:
        # Step 1: GET the page to obtain ViewState and cookies
        print("Step 1: Loading data portal page...")
        resp = client.get(PORTAL_URL)
        resp.raise_for_status()
        html = resp.text

        viewstate = _extract_field(html, "__VIEWSTATE")
        viewstate_gen = _extract_field(html, "__VIEWSTATEGENERATOR")
        event_validation = _extract_field(html, "__EVENTVALIDATION")
        print(f"  Got ViewState ({len(viewstate)} chars), cookies: {list(client.cookies.keys())}")

        # Step 2: AJAX POST to select "License Master" (value="M")
        print("Step 2: Selecting License Master file type...")
        ajax_headers = {
            **HEADERS,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-MicrosoftAjax": "Delta=true",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": PORTAL_URL,
            "Origin": "https://www.cslb.ca.gov",
        }
        ajax_data = {
            "ctl00$MainContent$smPanel": "ctl00$MainContent$uplinks|ctl00$MainContent$ddlStatus",
            "__EVENTTARGET": "ctl00$MainContent$ddlStatus",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstate_gen,
            "__EVENTVALIDATION": event_validation,
            "ctl00$MainContent$ddlStatus": "M",
            "__ASYNCPOST": "true",
        }

        resp = client.post(PORTAL_URL, data=ajax_data, headers=ajax_headers)
        resp.raise_for_status()
        ajax_text = resp.text

        # Extract updated ViewState and EventValidation from AJAX response
        viewstate = _extract_from_ajax(ajax_text, "__VIEWSTATE")
        event_validation = _extract_from_ajax(ajax_text, "__EVENTVALIDATION")
        print(f"  Got updated ViewState ({len(viewstate)} chars)")

        # Step 3: POST to download the CSV file
        print("Step 3: Downloading MasterLicenseData.csv...")
        download_data = {
            "__EVENTTARGET": "ctl00$MainContent$lbMasterCSV",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            "__VIEWSTATE": viewstate,
            "__VIEWSTATEGENERATOR": viewstate_gen,
            "__EVENTVALIDATION": event_validation,
            "ctl00$MainContent$ddlStatus": "M",
        }

        resp = client.post(PORTAL_URL, data=download_data, headers={**HEADERS, "Referer": PORTAL_URL})
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "csv" not in content_type and "octet" not in content_type:
            print(f"  WARNING: Unexpected content-type: {content_type}")
            if len(resp.content) < 1000:
                print(f"  Response body: {resp.text[:500]}")
                return False

        with open(output_path, "wb") as f:
            f.write(resp.content)

        size_mb = len(resp.content) / (1024 * 1024)
        print(f"  Downloaded {size_mb:.1f} MB to {output_path}")
        return True

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False
    finally:
        client.close()


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "data/MasterLicenseData.csv"
    success = download_csv(output)
    sys.exit(0 if success else 1)
