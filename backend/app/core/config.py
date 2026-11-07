from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KYRO_", env_file="../.env", extra="ignore")
    database_url: str = "sqlite:///../data/kyro.db"
    data_dir: Path = Path("../data")
    local_only: bool = True
    local_model_url: str = "http://127.0.0.1:8080/v1"
    local_model: str = "qwen3-8b"
    cloud_model_url: str = ""
    cloud_model: str = ""
    cloud_api_key: str = ""
    cloud_api_key_path: str = ""
    cloud_protocol: Literal["chat", "responses"] = "chat"
    model_routing: Literal["local", "auto", "cloud"] = "local"
    cloud_request_limit: int = 2
    cloud_authorized: bool = False
    cloud_input_price_per_million: float | None = None
    cloud_output_price_per_million: float | None = None
    github_token: str = ""
    github_client_id: str = ""
    github_app_id: str = ""
    github_app_private_key_path: str = ""
    github_installation_id: str = ""
    cookie_secure: bool = False
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8787,http://127.0.0.1:8787"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    sandbox_image: str = "kyro-sandbox:local"
    scanner_timeout: int = 300
    command_timeout: int = 180
    model_timeout: int = 180
    max_model_tokens: int = 4096
    max_agent_steps: int = 4
    agent_token_budget: int = 24000
    job_timeout: int = 1800
    automatic_recovery: bool = True
    job_max_attempts: int = Field(default=3, ge=1, le=5)
    job_retry_delay: int = Field(default=2, ge=1, le=60)
    workspace_volume: str = ""
    session_hours: int = 12
    semgrep_image: str = "semgrep/semgrep:1.184.0"
    osv_image: str = "ghcr.io/google/osv-scanner:v2.7.0"
    trivy_image: str = "aquasec/trivy:0.76.2"
    scanner_network: str = "bridge"
    enable_worker: bool = True

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]


settings = Settings()
