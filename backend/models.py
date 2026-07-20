from sqlalchemy import Column, String, Text, JSON, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from database import Base
import enum


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    SPEC_GENERATING = "spec_generating"
    SPEC_GENERATED = "spec_generated"
    CODEGEN = "codegen"
    BUILDING = "building"
    SIGNING = "signing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(20), primary_key=True, index=True)
    nl_prompt = Column(Text, nullable=False)
    package_name = Column(String(255), nullable=False)
    signing_profile = Column(String(100), nullable=False, default="prod-default")
    deliverables = Column(JSON, nullable=False)

    status = Column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    current_step = Column(String(50), nullable=True)

    spec = Column(JSON, nullable=True)
    artifacts = Column(JSON, nullable=True)
    errors = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<Job {self.id} - {self.status}>"
