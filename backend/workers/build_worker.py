"""
Build Worker — GitHub Actions strategy.

Instead of shelling out to Gradle inside the worker container (which required a
full Android SDK in the image and a privileged docker.sock mount, and never
actually worked), this worker delegates the compile to GitHub Actions:

  1. Download the generated project.zip from object storage.
  2. Commit its files to a per-job branch (build/<job_id>) in the build repo.
  3. Dispatch the "Build Generated App" workflow against that branch.
  4. Poll the workflow run until it completes.
  5. Download the produced APK artifact and upload it back to object storage.
  6. Enqueue the signing step.

Why: GitHub Actions runners already have the Android SDK + JDK, builds are free
within plan limits, and there is no build VM to host. This mirrors the workflow
already proven to produce real APKs in the NL2Build- repo.

Configuration (environment variables):
  GH_TOKEN        - PAT / app token with `repo` + `actions` scope
  GH_BUILD_REPO   - "owner/repo" that holds .github/workflows/build-generated.yml
  GH_WORKFLOW     - workflow file name (default: build-generated.yml)

IMPORTANT / STATUS: the build half of this design is proven in CI (see
.github/workflows/build-generated.yml building examples/generated-sample into a
real APK). This runtime orchestration path is implemented but NOT yet
runtime-verified end to end — it needs a deployed backend with GH_TOKEN set and
a real Actions run. Until then it fails loudly rather than pretending to build.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import io
import time
import base64
import zipfile
import tempfile

import requests
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Job, JobStatus
from queue import enqueue_sign_job
from storage import storage

GITHUB_API = "https://api.github.com"
POLL_INTERVAL_SECONDS = 10
POLL_TIMEOUT_SECONDS = 1800


def _config():
    token = os.environ.get("GH_TOKEN")
    repo = os.environ.get("GH_BUILD_REPO")
    workflow = os.environ.get("GH_WORKFLOW", "build-generated.yml")
    if not token or not repo:
        raise Exception(
            "Build worker is not configured. Set GH_TOKEN and GH_BUILD_REPO "
            "(owner/repo). Refusing to fake a build."
        )
    return token, repo, workflow


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def build_app(job_id: str) -> None:
    db: Session = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")

        job.status = JobStatus.BUILDING
        job.current_step = "building"
        db.commit()

        token, repo, workflow = _config()

        project_bytes = storage.download_bytes(f"{job_id}/project.zip")
        branch = f"build/{job_id}"

        _push_project_to_branch(token, repo, branch, project_bytes, job_id)
        _dispatch_workflow(token, repo, workflow, branch)
        run_id = _wait_for_run(token, repo, workflow, branch)
        artifacts = _download_apk_artifacts(token, repo, run_id, job_id)

        if not artifacts:
            raise Exception("Workflow completed but produced no APK artifact")

        job.current_step = "build_complete"
        db.commit()

        enqueue_sign_job(job_id)
        print(f"Build completed for job {job_id} (run {run_id})")

    except Exception as e:
        print(f"Build failed for job {job_id}: {str(e)}")
        if 'job' in dir() and job:
            job.status = JobStatus.FAILED
            job.errors = f"Build error: {str(e)}"
            db.commit()
        raise

    finally:
        db.close()


def _get_default_branch_sha(token: str, repo: str) -> str:
    r = requests.get(f"{GITHUB_API}/repos/{repo}", headers=_headers(token), timeout=30)
    r.raise_for_status()
    default_branch = r.json()["default_branch"]
    r = requests.get(
        f"{GITHUB_API}/repos/{repo}/git/ref/heads/{default_branch}",
        headers=_headers(token), timeout=30,
    )
    r.raise_for_status()
    return r.json()["object"]["sha"]


def _push_project_to_branch(token: str, repo: str, branch: str, project_zip: bytes, job_id: str) -> None:
    """Create branch <branch> and commit the generated project under generated/."""
    base_sha = _get_default_branch_sha(token, repo)

    # Create (or reset) the branch to the default-branch head.
    ref = f"refs/heads/{branch}"
    r = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/refs",
        headers=_headers(token),
        json={"ref": ref, "sha": base_sha},
        timeout=30,
    )
    if r.status_code not in (201, 422):  # 422 == already exists
        r.raise_for_status()

    # Commit each file from the zip via the contents API under generated/.
    with zipfile.ZipFile(io.BytesIO(project_zip)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            content_b64 = base64.b64encode(zf.read(name)).decode("ascii")
            path = f"generated/{name}"
            requests.put(
                f"{GITHUB_API}/repos/{repo}/contents/{path}",
                headers=_headers(token),
                json={
                    "message": f"job {job_id}: add {name}",
                    "content": content_b64,
                    "branch": branch,
                },
                timeout=30,
            ).raise_for_status()


def _dispatch_workflow(token: str, repo: str, workflow: str, branch: str) -> None:
    requests.post(
        f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow}/dispatches",
        headers=_headers(token),
        json={"ref": branch, "inputs": {"project_path": "generated"}},
        timeout=30,
    ).raise_for_status()


def _wait_for_run(token: str, repo: str, workflow: str, branch: str) -> int:
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    run_id = None
    while time.time() < deadline:
        r = requests.get(
            f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow}/runs",
            headers=_headers(token), params={"branch": branch, "per_page": 1}, timeout=30,
        )
        r.raise_for_status()
        runs = r.json().get("workflow_runs", [])
        if runs:
            run = runs[0]
            run_id = run["id"]
            if run["status"] == "completed":
                if run["conclusion"] == "success":
                    return run_id
                raise Exception(f"Build workflow concluded '{run['conclusion']}'")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise Exception("Timed out waiting for build workflow to complete")


def _download_apk_artifacts(token: str, repo: str, run_id: int, job_id: str) -> list:
    r = requests.get(
        f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}/artifacts",
        headers=_headers(token), timeout=30,
    )
    r.raise_for_status()
    stored = []
    for artifact in r.json().get("artifacts", []):
        dl = requests.get(
            f"{GITHUB_API}/repos/{repo}/actions/artifacts/{artifact['id']}/zip",
            headers=_headers(token), timeout=120,
        )
        dl.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(dl.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".apk"):
                    key = f"{job_id}/apk/app-release.apk"
                    storage.upload_bytes(zf.read(name), key)
                    stored.append(key)
    return stored
