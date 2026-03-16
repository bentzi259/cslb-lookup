#!/bin/bash
set -e

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') Starting CSV refresh..."

DATA_DIR="${DATA_DIR:-/data}"
DB_PATH="${DATABASE_PATH:-$DATA_DIR/licenses.db}"
CSV_PATH="$DATA_DIR/MasterLicenseData.csv"
BACKUP_PATH="$DATA_DIR/MasterLicenseData.csv.bak"

# Backup current CSV before downloading
if [ -f "$CSV_PATH" ]; then
    cp "$CSV_PATH" "$BACKUP_PATH"
    echo "Backed up existing CSV."
fi

# Download fresh CSV from CSLB data portal
echo "Downloading CSV from CSLB data portal..."
python -m app.csv_downloader "$CSV_PATH"

if [ $? -ne 0 ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') CSV download failed. Keeping existing database."
    if [ -f "$BACKUP_PATH" ]; then
        cp "$BACKUP_PATH" "$CSV_PATH"
        echo "Restored backup CSV."
    fi
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

# Load into database
echo "Loading CSV into database..."
python -m app.csv_loader "$CSV_PATH" "$DB_PATH"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') CSV refresh completed successfully."
