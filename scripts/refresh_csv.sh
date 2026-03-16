#!/bin/bash
set -e

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') Starting CSV refresh..."

DATA_DIR="${DATA_DIR:-/data}"
DB_PATH="${DATABASE_PATH:-$DATA_DIR/licenses.db}"
CSV_PATH="$DATA_DIR/MasterLicenseData.csv"
BACKUP_PATH="$DATA_DIR/MasterLicenseData.csv.bak"

# Download fresh CSV using Python helper
echo "Downloading CSV from CSLB data portal..."
python -c "
from app.firecrawl_client import _get_client
import httpx, sys

PORTAL_URL = 'https://www.cslb.ca.gov/onlineservices/dataportal/ContractorList'

try:
    client = _get_client()
    result = client.scrape(
        PORTAL_URL,
        formats=['links'],
        actions=[
            {'type': 'wait', 'milliseconds': 3000},
            {'type': 'click', 'selector': 'select[id*=\"FileType\"] option[value*=\"Master\"]'},
            {'type': 'wait', 'milliseconds': 1000},
            {'type': 'click', 'selector': 'input[id*=\"Submit\"], input[id*=\"Download\"], a[id*=\"Download\"]'},
            {'type': 'wait', 'milliseconds': 5000},
        ]
    )

    links = result.get('links', [])
    csv_link = None
    for link in links:
        url = link if isinstance(link, str) else link.get('url', '')
        if '.csv' in url.lower() or 'master' in url.lower():
            csv_link = url
            break

    if csv_link:
        print(f'Downloading: {csv_link}')
        resp = httpx.get(csv_link, follow_redirects=True, timeout=300)
        resp.raise_for_status()
        with open('$CSV_PATH', 'wb') as f:
            f.write(resp.content)
        print('Download complete')
    else:
        print('ERROR: Could not find CSV download link', file=sys.stderr)
        print(f'Links found: {links}', file=sys.stderr)
        sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') CSV download failed. Keeping existing database."
    exit 1
fi

# Verify the downloaded file looks valid
LINE_COUNT=$(wc -l < "$CSV_PATH" 2>/dev/null || echo "0")
echo "Downloaded CSV has $LINE_COUNT lines"

if [ "$LINE_COUNT" -lt 1000 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') ERROR: Downloaded CSV too small ($LINE_COUNT lines). Aborting."
    if [ -f "$BACKUP_PATH" ]; then
        cp "$BACKUP_PATH" "$CSV_PATH"
        echo "Restored backup CSV."
    fi
    exit 1
fi

# Backup current CSV before loading
if [ -f "$CSV_PATH" ]; then
    cp "$CSV_PATH" "$BACKUP_PATH"
fi

# Load into database
echo "Loading CSV into database..."
python -m app.csv_loader "$CSV_PATH" "$DB_PATH"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') CSV refresh completed successfully."
