import os
from dotenv import load_dotenv
from pydantic import Field
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    AWS_REGION: str
    tavily_api_key: str 
    data_dir: Path = Path("data")
    concurrency: int = 8


settings = Settings()
