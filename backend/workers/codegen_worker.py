"""
Code Generation Worker
Generates a buildable Android project from a specification using the
deterministic template in generator/android_template.py (template-first).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Job, JobStatus
from queue import enqueue_build_job
from storage import storage
from generator.android_template import generate_project
import io
import zipfile


def generate_code(job_id: str) -> None:
    db: Session = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")

        job.status = JobStatus.CODEGEN
        job.current_step = "codegen"
        db.commit()

        project_zip = generate_android_project(job.spec, job.package_name)

        key = f"{job_id}/project.zip"
        storage.upload_bytes(project_zip, key)

        job.current_step = "codegen_complete"
        db.commit()

        enqueue_build_job(job_id)

        print(f"Code generated for job {job_id}")

    except Exception as e:
        print(f"Code generation failed for job {job_id}: {str(e)}")
        job.status = JobStatus.FAILED
        job.errors = f"Code generation error: {str(e)}"
        db.commit()
        raise

    finally:
        db.close()


def generate_android_project(spec: dict, package_name: str) -> bytes:
    """Render the template to a set of files and pack them into a zip."""
    files = generate_project(spec or {}, package_name)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path, content in files.items():
            zip_file.writestr(path, content)
    zip_buffer.seek(0)
    return zip_buffer.read()
