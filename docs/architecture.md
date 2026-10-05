# Architecture

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
