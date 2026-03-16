from pydantic import BaseModel, Field


class BusinessInfo(BaseModel):
    business_name: str | None = None
    address: str | None = None
    phone: str | None = None
    issue_date: str | None = None
    expiration_date: str | None = None
    business_type: str | None = None


class LicenseStatus(BaseModel):
    status: str | None = None
    secondary_status: str | None = None
    bond_amount: str | None = None
    bond_company: str | None = None


class Classification(BaseModel):
    code: str
    description: str


class WorkersCompensation(BaseModel):
    status: str | None = None
    insurance_company: str | None = None
    policy_number: str | None = None
    policy_effective_date: str | None = None
    policy_expiration_date: str | None = None


class LicenseResponse(BaseModel):
    license_number: str
    business_information: BusinessInfo
    license_status: LicenseStatus
    classifications: list[Classification]
    workers_compensation: WorkersCompensation
    data_source: str = "csv"


class BulkLicenseRequest(BaseModel):
    license_numbers: list[str] = Field(..., max_length=100)
    source: str | None = None


class BulkResponse(BaseModel):
    results: list[LicenseResponse]
    errors: list[dict] | None = None
