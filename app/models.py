from pydantic import BaseModel, Field


class BusinessInformation(BaseModel):
    business_name: str | None = None
    full_business_name: str | None = None
    address: str | None = None
    county: str | None = None
    phone: str | None = None
    entity: str | None = None
    issue_date: str | None = None
    reissue_date: str | None = None
    expire_date: str | None = None


class LicenseStatus(BaseModel):
    status: str | None = None
    secondary_status: str | None = None
    additional_status: str | None = None
    inactivation_date: str | None = None
    reactivation_date: str | None = None


class ContractorsBond(BaseModel):
    bond_number: str | None = None
    bond_amount: str | None = None
    bond_company: str | None = None
    effective_date: str | None = None


class Classification(BaseModel):
    code: str
    description: str


class WorkersCompensation(BaseModel):
    coverage_type: str | None = None
    insurance_company: str | None = None
    policy_number: str | None = None
    effective_date: str | None = None
    expire_date: str | None = None


class PersonnelMember(BaseModel):
    name: str | None = None
    role: str | None = None


class LicenseResponse(BaseModel):
    license_number: str
    last_update: str | None = None
    extract_date: str | None = None
    business_information: BusinessInformation
    license_status: LicenseStatus
    contractors_bond: ContractorsBond
    classifications: list[Classification]
    workers_compensation: WorkersCompensation
    personnel: list[PersonnelMember] | None = None
    asbestos_reg: str | None = None
    data_source: str = "csv"


class FieldMetadataResponse(BaseModel):
    state: list[str] = Field(..., description="U.S. state codes where contractors are registered (e.g. CA, NV, AZ)")
    county: list[str] = Field(..., description="California counties (e.g. Los Angeles, San Diego, Orange)")
    business_type: list[str] = Field(..., description="Business entity types (e.g. Corporation, Sole Owner, Partnership, Limited Liability, JointVenture)")
    primary_status: list[str] = Field(..., description="Primary license status (e.g. CLEAR, Work Comp Susp, Citation Susp, BOND Pay Susp)")
    secondary_status: list[str] = Field(..., description="Secondary/additional status flags, may contain multiple pipe-separated values (e.g. Pending IFS, WC Susp Pending, DISC Bond Filed)")
    asbestos_reg: list[str] = Field(..., description="Asbestos registration codes (e.g. 1-5, 8, 9, C, R)")
    wc_coverage_type: list[str] = Field(..., description="Workers' compensation coverage types (e.g. Exempt, Self-Insured, Workers' Compensation Insurance)")


class BulkLicenseRequest(BaseModel):
    license_numbers: list[str] = Field(..., max_length=100)
    source: str | None = None


class BulkResponse(BaseModel):
    results: list[LicenseResponse]
    errors: list[dict] | None = None
