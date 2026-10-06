from fastapi import FastAPI

from app.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    docs = cfg.docs_enabled
    app = FastAPI(
        title="Orsyn API",
        version=cfg.git_sha,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": cfg.git_sha, "env": cfg.env}

    return app


app = create_app()
