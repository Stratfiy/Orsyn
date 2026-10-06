# Architecture

## Naming
- `orsyn` is the permanent internal codename and stays: AWS resource names and tags (`project=orsyn`), S3 bucket and RDS identifiers, `ORSYN_*` env vars, repo and package names, log names.
- The customer-facing brand is not final. Brand strings live only in `apps/web/lib/messages.ts` (and future email/WhatsApp templates); never hard-code the brand elsewhere.
- Brand-bound setup (domain, SES sending domain/DKIM, WhatsApp Business display name) waits until the brand is final.

## Stack
As in `CLAUDE.md`: Python 3.12 + FastAPI + Pydantic v2 + PostgreSQL 16 with pgvector; Next.js 15 (App Router, TypeScript strict); AWS ap-south-1 (ECS Fargate, RDS single-AZ, private S3, SQS and EventBridge Scheduler, Secrets Manager).

## ORM and migrations
SQLAlchemy 2 + Alembic, unless changed here.

## IaC
TBD (E0 Q1).

## Environments
- local
- dev (not yet)
- prod (not yet)
