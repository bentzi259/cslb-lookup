import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.config import settings

COLUMN_MAP = {
    "LicenseNo": "license_number",
    "LastUpdate": "last_update",
    "BusinessName": "business_name",
    "BUS-NAME-2": "business_name_2",
    "FullBusinessName": "full_business_name",
    "MailingAddress": "address",
    "City": "city",
    "State": "state",
    "County": "county",
    "ZIPCode": "zip_code",
    "BusinessPhone": "phone",
    "BusinessType": "business_type",
    "IssueDate": "issue_date",
    "ReissueDate": "reissue_date",
    "ExpirationDate": "expiration_date",
    "InactivationDate": "inactivation_date",
    "ReactivationDate": "reactivation_date",
    "PrimaryStatus": "primary_status",
    "SecondaryStatus": "secondary_status",
    "Classifications(s)": "classifications",
    "AsbestosReg": "asbestos_reg",
    "WorkersCompCoverageType": "wc_coverage_type",
    "WCInsuranceCompany": "wc_insurance_company",
    "WCPolicyNumber": "wc_policy_number",
    "WCEffectiveDate": "wc_effective_date",
    "WCExpirationDate": "wc_expiration_date",
    "CBSuretyCompany": "cb_surety_company",
    "CBNumber": "cb_number",
    "CBEffectiveDate": "cb_effective_date",
    "CBAmount": "cb_amount",
}

DB_COLUMNS = list(COLUMN_MAP.values())


def load_csv_to_db(csv_path: str, db_path: str | None = None):
    db_path = db_path or settings.database_path
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    print(f"Loading CSV: {csv_path}")
    df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False,
        usecols=list(COLUMN_MAP.keys()),
    )

    df = df.rename(columns=COLUMN_MAP)
    df = df[DB_COLUMNS]

    # Strip whitespace from all string columns
    df = df.apply(lambda col: col.str.strip())

    print(f"Loaded {len(df)} records from CSV")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)

    try:
        # Atomic swap: load into temp table, then rename
        conn.execute("DROP TABLE IF EXISTS licenses_new")
        conn.execute(
            """
            CREATE TABLE licenses_new (
                license_number TEXT PRIMARY KEY,
                last_update TEXT,
                business_name TEXT,
                business_name_2 TEXT,
                full_business_name TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                county TEXT,
                zip_code TEXT,
                phone TEXT,
                business_type TEXT,
                issue_date TEXT,
                reissue_date TEXT,
                expiration_date TEXT,
                inactivation_date TEXT,
                reactivation_date TEXT,
                primary_status TEXT,
                secondary_status TEXT,
                classifications TEXT,
                asbestos_reg TEXT,
                wc_coverage_type TEXT,
                wc_insurance_company TEXT,
                wc_policy_number TEXT,
                wc_effective_date TEXT,
                wc_expiration_date TEXT,
                cb_surety_company TEXT,
                cb_number TEXT,
                cb_effective_date TEXT,
                cb_amount TEXT
            )
            """
        )

        df.to_sql("licenses_new", conn, if_exists="append", index=False)
        print(f"Inserted {len(df)} records into temp table")

        conn.execute("DROP TABLE IF EXISTS licenses")
        conn.execute("ALTER TABLE licenses_new RENAME TO licenses")

        # Update metadata
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_metadata (
                id INTEGER PRIMARY KEY DEFAULT 1,
                row_count INTEGER,
                imported_at TEXT,
                csv_filename TEXT
            )
            """
        )
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT OR REPLACE INTO import_metadata (id, row_count, imported_at, csv_filename)
            VALUES (1, ?, ?, ?)
            """,
            (len(df), now, csv_file.name),
        )

        conn.commit()
        print(f"Database updated successfully at {db_path}")
        print(f"  Records: {len(df)}")
        print(f"  Imported at: {now}")

    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.csv_loader <path_to_csv> [db_path]")
        sys.exit(1)

    csv_path = sys.argv[1]
    db_path = sys.argv[2] if len(sys.argv) > 2 else None
    load_csv_to_db(csv_path, db_path)
