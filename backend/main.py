from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import string
import random

from config import settings
from database import get_db, init_db
from models import Job, JobStatus
from schemas import (
    JobCreate, JobResponse, JobDetail, JobListItem,
    HealthResponse, Artifact
)
from queue import enqueue_spec_job, redis_conn
from storage import storage

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Transform natural language into production-ready Android apps"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    init_db()


def generate_job_id() -> str:
    chars = string.ascii_letters + string.digits
    suffix = ''.join(random.choices(chars, k=8))
    return f"J_{suffix}"


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "NL2Build Cloud API",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    try:
        redis_conn.ping()
        redis_status = "healthy"
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"

    try:
        storage.s3_client.list_buckets()
        storage_status = "healthy"
    except Exception as e:
        storage_status = f"unhealthy: {str(e)}"

    overall_status = "healthy" if all(
        s == "healthy" for s in [db_status, redis_status, storage_status]
    ) else "degraded"

    return {
        "status": overall_status,
        "version": settings.app_version,
        "database": db_status,
        "redis": redis_status,
        "storage": storage_status
    }


@app.post("/v1/jobs", response_model=JobResponse, status_code=201)
async def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    job_id = generate_job_id()

    job = Job(
        id=job_id,
        nl_prompt=job_data.nl_prompt,
        package_name=job_data.package_name,
        signing_profile=job_data.signing_profile,
        deliverables=job_data.deliverables,
        status=JobStatus.PENDING,
        current_step="pending"
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue_spec_job(job_id)
        job.status = JobStatus.SPEC_GENERATING
        job.current_step = "spec_generating"
        db.commit()
    except Exception as e:
        job.status = JobStatus.FAILED
        job.errors = f"Failed to enqueue job: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "job_id": job_id,
        "status_url": f"/v1/jobs/{job_id}"
    }


@app.get("/v1/jobs/{job_id}", response_model=JobDetail)
async def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts = None
    if job.artifacts:
        artifacts = [Artifact(**art) for art in job.artifacts]

    return {
        "job_id": job.id,
        "status": job.status,
        "current_step": job.current_step,
        "steps": ["spec_generated", "codegen", "build", "sign", "done"],
        "artifacts": artifacts,
        "errors": job.errors,
        "created_at": job.created_at,
        "updated_at": job.updated_at
    }


@app.get("/v1/jobs", response_model=List[JobListItem])
async def list_jobs(
    limit: int = 10,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    jobs = db.query(Job).order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

    return [
        {
            "job_id": job.id,
            "status": job.status,
            "package_name": job.package_name,
            "created_at": job.created_at
        }
        for job in jobs
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
