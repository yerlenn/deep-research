# Deep Research Starter

A starter Deep Research chat app with Vite React, FastAPI, Postgres, Docker Compose, and Clerk.

The AI agent is mocked for now. Users submit a research request, review a generated plan, approve it, then see a compact research status row and a full process log on demand.

## Local Setup

1. Start Postgres:

```bash
docker compose up -d postgres
```

2. Configure the backend:

```bash
cp backend/.env.example backend/.env
```

3. Configure the frontend:

```bash
cp frontend/.env.example frontend/.env
```

4. Install and run the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

5. Install and run the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Auth

Clerk handles sign-in/sign-up and session management. The backend verifies Clerk JWTs on protected endpoints.

For local UI development without Clerk, set `VITE_AUTH_DISABLED=true` in `frontend/.env` and `AUTH_DISABLED=true` in `backend/.env`. Do not use those settings in production.

## Production Direction

- Frontend: Vercel or S3 + CloudFront.
- API: FastAPI container on ECS/Fargate behind an Application Load Balancer.
- Future agent workers: separate ECS/Fargate services.
- Database: RDS Postgres.
- Future queue: SQS.
- Future realtime coordination: Redis/ElastiCache.
- Files: S3.
