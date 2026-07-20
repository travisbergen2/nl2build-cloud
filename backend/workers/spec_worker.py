"""
Spec Generation Worker (Phase 6)
Converts natural language to app specification using LLM
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Job, JobStatus
from queue import enqueue_codegen_job
from config import settings
import yaml
from openai import OpenAI


SPEC_SYSTEM_PROMPT = """You are an expert Android app specification generator.
Convert natural language descriptions into detailed app specifications in YAML format.

The spec should include:
- app_name: Human-readable app name
- package_name: Android package identifier
- min_sdk: Minimum Android SDK version (default 24)
- target_sdk: Target Android SDK version (default 34)
- features: List of app features
- screens: List of screen definitions with UI components
- permissions: Required Android permissions
- dependencies: Required libraries (Compose, Material3, etc.)

Return ONLY valid YAML. No markdown, no code blocks."""


def generate_spec(job_id: str) -> None:
    db: Session = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")

        job.status = JobStatus.SPEC_GENERATING
        job.current_step = "spec_generating"
        db.commit()

        if settings.openai_api_key:
            spec = generate_spec_with_llm(job.nl_prompt, job.package_name)
        else:
            spec = generate_simple_spec(job.nl_prompt, job.package_name)

        job.spec = spec
        job.status = JobStatus.SPEC_GENERATED
        job.current_step = "spec_generated"
        db.commit()

        enqueue_codegen_job(job_id)

        print(f"Spec generated for job {job_id}")

    except Exception as e:
        print(f"Spec generation failed for job {job_id}: {str(e)}")
        job.status = JobStatus.FAILED
        job.errors = f"Spec generation error: {str(e)}"
        db.commit()
        raise

    finally:
        db.close()


def generate_spec_with_llm(nl_prompt: str, package_name: str) -> dict:
    client = OpenAI(api_key=settings.openai_api_key)

    user_prompt = f"""Generate an Android app specification for:

Description: {nl_prompt}
Package Name: {package_name}

Create a detailed YAML specification."""

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SPEC_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        spec_yaml = response.choices[0].message.content.strip()

        if spec_yaml.startswith("```"):
            lines = spec_yaml.split("\n")
            spec_yaml = "\n".join(lines[1:-1])

        spec = yaml.safe_load(spec_yaml)

        return spec

    except Exception as e:
        print(f"LLM generation failed: {str(e)}")
        return generate_simple_spec(nl_prompt, package_name)


def generate_simple_spec(nl_prompt: str, package_name: str) -> dict:
    app_name = package_name.split('.')[-1].replace('_', ' ').title()

    spec = {
        "app_name": app_name,
        "package_name": package_name,
        "min_sdk": 24,
        "target_sdk": 34,
        "description": nl_prompt,
        "features": [
            "Material Design 3",
            "Jetpack Compose UI"
        ],
        "screens": [
            {
                "name": "MainActivity",
                "type": "main",
                "components": [
                    {
                        "type": "scaffold",
                        "topBar": "App Bar",
                        "content": "Main Content"
                    }
                ]
            }
        ],
        "permissions": [],
        "dependencies": {
            "compose": "1.5.4",
            "compose_material3": "1.1.2",
            "compose_navigation": "2.7.5"
        }
    }

    return spec
