import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.integrations.github import validate_repository


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Use a valid email address")
        return value.lower()


class ProjectInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(max_length=2000, default="")


class RepositoryInput(StrictModel):
    project_id: str
    full_name: str
    branch: str = Field(min_length=1, max_length=200)

    @field_validator("full_name")
    @classmethod
    def name_valid(cls, value):
        return validate_repository(value)


class Approval(StrictModel):
    approved: bool
    plan_digest: str = Field(pattern="^[a-f0-9]{64}$")


class DeliveryApproval(StrictModel):
    approved: bool


class ModelSettings(StrictModel):
    endpoint: str = Field(max_length=500)
    model: str = Field(min_length=1, max_length=200)
    local_only: bool = True
    routing: Literal["local", "auto", "cloud"] = "local"


class OAuthPoll(StrictModel):
    device_code: str = Field(min_length=1, max_length=256)
