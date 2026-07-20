from redis import Redis
from rq import Queue
from config import settings

redis_conn = Redis.from_url(settings.redis_url)

spec_queue = Queue('spec', connection=redis_conn)
codegen_queue = Queue('codegen', connection=redis_conn)
build_queue = Queue('build', connection=redis_conn)
sign_queue = Queue('sign', connection=redis_conn)


def enqueue_spec_job(job_id: str) -> str:
    from workers.spec_worker import generate_spec
    job = spec_queue.enqueue(generate_spec, job_id, job_timeout='10m')
    return job.id


def enqueue_codegen_job(job_id: str) -> str:
    from workers.codegen_worker import generate_code
    job = codegen_queue.enqueue(generate_code, job_id, job_timeout='10m')
    return job.id


def enqueue_build_job(job_id: str) -> str:
    from workers.build_worker import build_app
    job = build_queue.enqueue(build_app, job_id, job_timeout='30m')
    return job.id


def enqueue_sign_job(job_id: str) -> str:
    from workers.sign_worker import sign_artifacts
    job = sign_queue.enqueue(sign_artifacts, job_id, job_timeout='10m')
    return job.id
