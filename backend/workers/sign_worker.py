"""
Sign Worker (Phase 4 & 8)
Signs APK/AAB files with KMS
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Job, JobStatus
from storage import storage
from config import settings
import tempfile
import subprocess


def sign_artifacts(job_id: str) -> None:
    db: Session = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")

        job.status = JobStatus.SIGNING
        job.current_step = "signing"
        db.commit()

        artifacts = []

        for deliverable_type in job.deliverables:
            unsigned_key = f"{job_id}/{deliverable_type}/app-release.{deliverable_type}"

            if storage.file_exists(unsigned_key):
                unsigned_data = storage.download_bytes(unsigned_key)

                signed_data = sign_file(unsigned_data, deliverable_type)

                signed_key = f"{job_id}/{deliverable_type}/app-release-signed.{deliverable_type}"
                storage.upload_bytes(signed_data, signed_key)

                sha256 = storage.calculate_sha256(signed_data)

                url = storage.generate_presigned_url(signed_key, expiration=86400)

                artifacts.append({
                    "type": deliverable_type,
                    "url": url,
                    "sha256": sha256
                })

        job.artifacts = artifacts
        job.status = JobStatus.SUCCEEDED
        job.current_step = "done"
        db.commit()

        print(f"Signing completed for job {job_id}")

    except Exception as e:
        print(f"Signing failed for job {job_id}: {str(e)}")
        job.status = JobStatus.FAILED
        job.errors = f"Signing error: {str(e)}"
        db.commit()
        raise

    finally:
        db.close()


def sign_file(data: bytes, file_type: str) -> bytes:
    if settings.kms_provider == "mock":
        return sign_with_mock_kms(data, file_type)
    elif settings.kms_provider == "gcp":
        return sign_with_gcp_kms(data, file_type)
    elif settings.kms_provider == "aws":
        return sign_with_aws_kms(data, file_type)
    else:
        raise Exception(f"Unknown KMS provider: {settings.kms_provider}")


def sign_with_mock_kms(data: bytes, file_type: str) -> bytes:
    print(f"Mock signing {file_type} file...")

    with tempfile.TemporaryDirectory() as tmpdir:
        unsigned_path = os.path.join(tmpdir, f'unsigned.{file_type}')
        signed_path = os.path.join(tmpdir, f'signed.{file_type}')
        keystore_path = os.path.join(tmpdir, 'debug.keystore')

        with open(unsigned_path, 'wb') as f:
            f.write(data)

        create_debug_keystore(keystore_path)

        sign_with_jarsigner(unsigned_path, signed_path, keystore_path)

        with open(signed_path, 'rb') as f:
            return f.read()


def create_debug_keystore(keystore_path: str) -> None:
    result = subprocess.run([
        'keytool',
        '-genkey',
        '-v',
        '-keystore', keystore_path,
        '-storepass', 'android',
        '-alias', 'androiddebugkey',
        '-keypass', 'android',
        '-keyalg', 'RSA',
        '-keysize', '2048',
        '-validity', '10000',
        '-dname', 'CN=Android Debug,O=Android,C=US'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Failed to create keystore: {result.stderr}")


def sign_with_jarsigner(unsigned_path: str, signed_path: str, keystore_path: str) -> None:
    import shutil
    shutil.copy(unsigned_path, signed_path)

    result = subprocess.run([
        'jarsigner',
        '-verbose',
        '-sigalg', 'SHA256withRSA',
        '-digestalg', 'SHA-256',
        '-keystore', keystore_path,
        '-storepass', 'android',
        '-keypass', 'android',
        signed_path,
        'androiddebugkey'
    ], capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Failed to sign: {result.stderr}")


def sign_with_gcp_kms(data: bytes, file_type: str) -> bytes:
    raise NotImplementedError("GCP KMS signing not yet implemented")


def sign_with_aws_kms(data: bytes, file_type: str) -> bytes:
    raise NotImplementedError("AWS KMS signing not yet implemented")
