# Deployment Guide (Staging)

## 1. Start full stack locally

```bash
docker compose up --build
```

- Frontend: `http://localhost:3000`
- FastAPI v2: `http://localhost:5001`
- PostgreSQL: `localhost:5432`

## 2. Run DB migrations

```bash
cd server
alembic -c alembic.ini upgrade head
```

## 3. Health checks

- `GET http://localhost:5001/health`
- `GET http://localhost:5001/api/stats`

## 4. Staging checklist

- Confirm `DATABASE_URL` points to managed PostgreSQL.
- Keep `LLM_PROVIDER=mock` for deterministic demos.
- Enable log shipping for API container stdout.
- Run backend tests: `python -m pytest tests/test_api_v2.py -q`
- Run frontend tests: `npm test -- --watchAll=false --runTestsByPath src/components/TaskList.test.js`

## 5. Rollback steps

1. Roll API image tag back to previous stable revision.
2. Re-run migration rollback if schema changed:
   - `alembic -c alembic.ini downgrade -1`
3. Restart stack:
   - `docker compose up -d`
