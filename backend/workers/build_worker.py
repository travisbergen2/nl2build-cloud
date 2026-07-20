"""
Build Worker (Phase 3)
Executes Gradle build in Docker container
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Job, JobStatus
from queue import enqueue_sign_job
from storage import storage
import tempfile
import subprocess


def build_app(job_id: str) -> None:
    db: Session = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")

        job.status = JobStatus.BUILDING
        job.current_step = "building"
        db.commit()

        project_key = f"{job_id}/project.zip"

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, 'project.zip')
            with open(zip_path, 'wb') as f:
                data = storage.download_bytes(project_key)
                f.write(data)

            import zipfile
            project_dir = os.path.join(tmpdir, 'project')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(project_dir)

            build_outputs = run_gradle_build(project_dir, job.deliverables)

            for output_type, output_path in build_outputs.items():
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        key = f"{job_id}/{output_type}/app-release.{output_type}"
                        storage.upload_file(f, key)

        job.current_step = "build_complete"
        db.commit()

        enqueue_sign_job(job_id)

        print(f"Build completed for job {job_id}")

    except Exception as e:
        print(f"Build failed for job {job_id}: {str(e)}")
        job.status = JobStatus.FAILED
        job.errors = f"Build error: {str(e)}"
        db.commit()
        raise

    finally:
        db.close()


def run_gradle_build(project_dir: str, deliverables: list) -> dict:
    outputs = {}

    gradlew = os.path.join(project_dir, 'gradlew')
    if not os.path.exists(gradlew):
        create_gradle_wrapper(project_dir)

    os.chmod(gradlew, 0o755)

    if 'aab' in deliverables:
        print("Building AAB...")
        result = subprocess.run(
            [gradlew, 'bundleRelease'],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode == 0:
            aab_path = os.path.join(project_dir, 'app/build/outputs/bundle/release/app-release.aab')
            outputs['aab'] = aab_path
        else:
            print(f"AAB build stderr: {result.stderr}")
            raise Exception(f"AAB build failed: {result.stderr}")

    if 'apk' in deliverables:
        print("Building APK...")
        result = subprocess.run(
            [gradlew, 'assembleRelease'],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode == 0:
            apk_path = os.path.join(project_dir, 'app/build/outputs/apk/release/app-release-unsigned.apk')
            outputs['apk'] = apk_path
        else:
            print(f"APK build stderr: {result.stderr}")
            raise Exception(f"APK build failed: {result.stderr}")

    return outputs


def create_gradle_wrapper(project_dir: str) -> None:
    wrapper_dir = os.path.join(project_dir, 'gradle', 'wrapper')
    os.makedirs(wrapper_dir, exist_ok=True)

    gradlew_content = """#!/bin/sh
./gradlew "$@"
"""

    gradlew_path = os.path.join(project_dir, 'gradlew')
    with open(gradlew_path, 'w') as f:
        f.write(gradlew_content)

    os.chmod(gradlew_path, 0o755)
