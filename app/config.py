from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_source: str = "csv"
    database_path: str = "data/licenses.db"
    firecrawl_api_key: str = ""
    cslb_data_portal_url: str = "https://www.cslb.ca.gov/onlineservices/dataportal/ContractorList"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
