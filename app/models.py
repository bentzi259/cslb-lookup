from pydantic import BaseModel, Field


class BusinessInformation(BaseModel):
    business_name: str | None = Field(None, description="Combined business name and DBA (e.g. 'ACME CORP | DBA NAME')")
    full_business_name: str | None = Field(None, description="Pre-combined full business name from CSLB bulk data (CSV only)")
    address: str | None = Field(None, description="Full street address including city, state, and zip")
    county: str | None = Field(None, description="California county where the business is located (CSV only)")
    phone: str | None = Field(None, description="Business phone number")
    entity: str | None = Field(None, description="Business entity type (e.g. Corporation, Sole Owner, Partnership)")
    issue_date: str | None = Field(None, description="Date the license was originally issued (MM/DD/YYYY)")
    reissue_date: str | None = Field(None, description="Date the license was reissued, if applicable (MM/DD/YYYY)")
    expire_date: str | None = Field(None, description="License expiration date (MM/DD/YYYY)")


class LicenseStatus(BaseModel):
    status: str | None = Field(None, description="Primary license status. CSV returns a code (e.g. 'CLEAR'), scraper returns a full sentence (e.g. 'This license is current and active.')")
    secondary_status: str | None = Field(None, description="Secondary status flags from CSLB bulk data (CSV only, e.g. 'Pending IFS', 'WC Susp Pending')")
    additional_status: str | None = Field(None, description="Additional license status detail from CSLB website (scraper only, e.g. 'The license may be suspended at a future date...')")
    inactivation_date: str | None = Field(None, description="Date the license was inactivated, if applicable (MM/DD/YYYY)")
    reactivation_date: str | None = Field(None, description="Date the license was reactivated, if applicable (MM/DD/YYYY)")


class ContractorsBond(BaseModel):
    bond_number: str | None = Field(None, description="Contractor's bond number")
    bond_amount: str | None = Field(None, description="Bond amount. CSV returns raw number (e.g. '25000'), scraper returns formatted (e.g. '$25,000')")
    bond_company: str | None = Field(None, description="Surety company name")
    effective_date: str | None = Field(None, description="Bond effective date (MM/DD/YYYY)")


class Classification(BaseModel):
    code: str = Field(..., description="CSLB classification code (e.g. 'B', 'C39')")
    description: str = Field(..., description="Classification description (e.g. 'General Building Contractor')")


class WorkersCompensation(BaseModel):
    coverage_type: str | None = Field(None, description="Workers' comp coverage type. CSV returns a label (e.g. 'Exempt', 'Workers\\' Compensation Insurance'), scraper returns a full sentence")
    insurance_company: str | None = Field(None, description="Workers' comp insurance company name")
    policy_number: str | None = Field(None, description="Workers' comp policy number")
    effective_date: str | None = Field(None, description="Workers' comp policy effective date (MM/DD/YYYY)")
    expire_date: str | None = Field(None, description="Workers' comp policy expiration date (MM/DD/YYYY)")


class PersonnelMember(BaseModel):
    name: str | None = Field(None, description="Person's name or personnel note text")
    role: str | None = Field(None, description="Role (e.g. RME, RMO, qualifying individual)")


class LicenseResponse(BaseModel):
    license_number: str = Field(..., description="CSLB license number")
    last_update: str | None = Field(None, description="Date the CSLB record was last updated (CSV only, MM/DD/YYYY)")
    extract_date: str | None = Field(None, description="Timestamp when CSLB data was extracted (scraper only, e.g. 'Data current as of 3/21/2026 12:31:11 PM')")
    business_information: BusinessInformation
    license_status: LicenseStatus
    contractors_bond: ContractorsBond
    classifications: list[Classification]
    workers_compensation: WorkersCompensation
    personnel: list[PersonnelMember] | None = Field(None, description="Personnel associated with the license (scraper only)")
    asbestos_reg: str | None = Field(None, description="Asbestos registration/certification code")
    data_source: str = Field("csv", description="Data source used for this response: 'csv' or 'scraper'")


class FieldMetadataResponse(BaseModel):
    state: list[str] = Field(..., description="U.S. state codes where contractors are registered (e.g. CA, NV, AZ)")
    county: list[str] = Field(..., description="California counties (e.g. Los Angeles, San Diego, Orange)")
    business_type: list[str] = Field(..., description="Business entity types (e.g. Corporation, Sole Owner, Partnership, Limited Liability, JointVenture)")
    primary_status: list[str] = Field(..., description="Primary license status (e.g. CLEAR, Work Comp Susp, Citation Susp, BOND Pay Susp)")
    secondary_status: list[str] = Field(..., description="Secondary/additional status flags, may contain multiple pipe-separated values (e.g. Pending IFS, WC Susp Pending, DISC Bond Filed)")
    asbestos_reg: list[str] = Field(..., description="Asbestos registration codes (e.g. 1-5, 8, 9, C, R)")
    wc_coverage_type: list[str] = Field(..., description="Workers' compensation coverage types (e.g. Exempt, Self-Insured, Workers' Compensation Insurance)")


class BulkLicenseRequest(BaseModel):
    license_numbers: list[str] = Field(..., max_length=100, description="List of license numbers to look up")
    source: str | None = Field(None, description="Data source override: 'csv' or 'scraper'")


class BulkResponse(BaseModel):
    results: list[LicenseResponse] = Field(..., description="List of successfully resolved license records")
    errors: list[dict] | None = Field(None, description="List of errors for license numbers that were not found or had invalid format")
