# NL2Build Cloud

Transform natural language into production-ready Android apps.

## Quick Start

1. Copy `.env.example` to `.env` and fill in values (OPENAI_API_KEY optional).
2. Run `docker-compose up -d`
3. Visit http://localhost:3000

Services:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

See inline comments in each file for details on the build pipeline
(spec generation -> codegen -> build -> sign).
