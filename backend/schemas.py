from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from models import JobStatus


class JobCreate(BaseModel):
    nl_prompt: str = Field(..., min_length=10)
    package_name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
    deliverables: List[str] = Field(default=["aab", "apk"])
    signing_profile: str = Field(default="prod-default")


class Artifact(BaseModel):
    type: str
    url: str
    sha256: str


class JobResponse(BaseModel):
    job_id: str
    status_url: str


class JobDetail(BaseModel):
    job_id: str
    status: JobStatus
    current_step: Optional[str] = None
    steps: List[str] = ["spec_generated", "codegen", "build", "sign", "done"]
    artifacts: Optional[List[Artifact]] = None
    errors: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobListItem(BaseModel):
    job_id: str
    status: JobStatus
    package_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    redis: str
    storage: str
