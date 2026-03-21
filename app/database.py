import aiosqlite
from pathlib import Path

from app.config import settings
from app.classifications import get_classification_description
from app.models import (
    BusinessInformation,
    Classification,
    ContractorsBond,
    LicenseResponse,
    LicenseStatus,
    WorkersCompensation,
)

DB_PATH = settings.database_path

CREATE_LICENSES_TABLE = """
CREATE TABLE IF NOT EXISTS licenses (
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

CREATE_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS import_metadata (
    id INTEGER PRIMARY KEY DEFAULT 1,
    row_count INTEGER,
    imported_at TEXT,
    csv_filename TEXT
)
"""


async def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_LICENSES_TABLE)
        await db.execute(CREATE_METADATA_TABLE)
        await db.commit()


def _build_business_name(name: str | None, name_2: str | None) -> str | None:
    name = (name or "").strip()
    name_2 = (name_2 or "").strip()
    if name and name_2:
        return f"{name} | {name_2}"
    return name or None


def _build_address(row: dict) -> str | None:
    parts = [
        (row.get("address") or "").strip(),
        (row.get("city") or "").strip(),
        (row.get("state") or "").strip(),
        (row.get("zip_code") or "").strip(),
    ]
    addr = parts[0]
    city_state_zip = ", ".join(p for p in parts[1:] if p)
    if addr and city_state_zip:
        return f"{addr}, {city_state_zip}"
    return addr or city_state_zip or None


def _parse_classifications(raw: str | None) -> list[Classification]:
    if not raw or not raw.strip():
        return []
    codes = [c.strip() for c in raw.split("|") if c.strip()]
    return [
        Classification(code=code, description=get_classification_description(code))
        for code in codes
    ]


def _row_to_response(row: dict) -> LicenseResponse:
    return LicenseResponse(
        license_number=row["license_number"],
        last_update=(row.get("last_update") or "").strip() or None,
        business_information=BusinessInformation(
            business_name=_build_business_name(
                row.get("business_name"), row.get("business_name_2")
            ),
            full_business_name=(row.get("full_business_name") or "").strip() or None,
            address=_build_address(row),
            county=(row.get("county") or "").strip() or None,
            phone=(row.get("phone") or "").strip() or None,
            entity=(row.get("business_type") or "").strip() or None,
            issue_date=(row.get("issue_date") or "").strip() or None,
            reissue_date=(row.get("reissue_date") or "").strip() or None,
            expire_date=(row.get("expiration_date") or "").strip() or None,
        ),
        license_status=LicenseStatus(
            status=(row.get("primary_status") or "").strip() or None,
            secondary_status=(row.get("secondary_status") or "").strip() or None,
            inactivation_date=(row.get("inactivation_date") or "").strip() or None,
            reactivation_date=(row.get("reactivation_date") or "").strip() or None,
        ),
        contractors_bond=ContractorsBond(
            bond_number=(row.get("cb_number") or "").strip() or None,
            bond_amount=(row.get("cb_amount") or "").strip() or None,
            bond_company=(row.get("cb_surety_company") or "").strip() or None,
            effective_date=(row.get("cb_effective_date") or "").strip() or None,
        ),
        classifications=_parse_classifications(row.get("classifications")),
        workers_compensation=WorkersCompensation(
            coverage_type=(row.get("wc_coverage_type") or "").strip() or None,
            insurance_company=(row.get("wc_insurance_company") or "").strip() or None,
            policy_number=(row.get("wc_policy_number") or "").strip() or None,
            effective_date=(row.get("wc_effective_date") or "").strip() or None,
            expire_date=(row.get("wc_expiration_date") or "").strip() or None,
        ),
        asbestos_reg=(row.get("asbestos_reg") or "").strip() or None,
        data_source="csv",
    )


async def get_license(license_number: str) -> LicenseResponse | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM licenses WHERE license_number = ?", (license_number,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return _row_to_response(dict(row))


async def get_licenses(license_numbers: list[str]) -> list[LicenseResponse]:
    if not license_numbers:
        return []
    placeholders = ",".join("?" for _ in license_numbers)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"SELECT * FROM licenses WHERE license_number IN ({placeholders})",
            license_numbers,
        )
        rows = await cursor.fetchall()
        return [_row_to_response(dict(row)) for row in rows]


async def get_stats() -> dict:
    if not Path(DB_PATH).exists():
        return {"status": "no_database", "record_count": 0, "last_import": None}

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM licenses")
        row = await cursor.fetchone()
        record_count = dict(row)["cnt"] if row else 0

        cursor = await db.execute(
            "SELECT * FROM import_metadata WHERE id = 1"
        )
        meta = await cursor.fetchone()
        meta_dict = dict(meta) if meta else {}

        return {
            "status": "loaded",
            "record_count": record_count,
            "last_import": meta_dict.get("imported_at"),
            "csv_filename": meta_dict.get("csv_filename"),
        }


ENUM_COLUMNS = [
    "state",
    "county",
    "business_type",
    "primary_status",
    "secondary_status",
    "asbestos_reg",
    "wc_coverage_type",
]


async def get_field_values() -> dict[str, list[str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        result = {}
        for col in ENUM_COLUMNS:
            cursor = await db.execute(
                f"SELECT DISTINCT {col} FROM licenses "
                f"WHERE {col} IS NOT NULL AND TRIM({col}) != '' "
                f"ORDER BY {col}"
            )
            rows = await cursor.fetchall()
            result[col] = [row[0].strip() for row in rows]
        return result


async def db_is_loaded() -> bool:
    if not Path(DB_PATH).exists():
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='licenses'"
        )
        table = await cursor.fetchone()
        if not table:
            return False
        cursor = await db.execute("SELECT COUNT(*) FROM licenses")
        row = await cursor.fetchone()
        return row[0] > 0 if row else False
