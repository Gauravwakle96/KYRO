from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.sandbox.runner import validate_command


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern="^(build|test|regression)$")
    argv: list[str] = Field(min_length=2, max_length=20)

    @field_validator("argv")
    @classmethod
    def safe_command(cls, value):
        validate_command(value)
        return value


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=180)
    root_cause: str = Field(min_length=10, max_length=4000)
    strategy: str = Field(min_length=10, max_length=4000)
    risks: list[str] = Field(min_length=1, max_length=12)
    files: list[str] = Field(min_length=1, max_length=6)
    commands: list[Command] = Field(max_length=6)
    expected_result: str = Field(min_length=5, max_length=2000)


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=300)
    before_hash: str = Field(pattern="^[a-f0-9]{64}$")
    content: str = Field(max_length=80000)


class Patch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=5, max_length=2000)
    changes: list[Change] = Field(min_length=1, max_length=6)
