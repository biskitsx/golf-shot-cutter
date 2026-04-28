from fastapi import FastAPI


def create_app(env: str = "production") -> FastAPI:
    app = FastAPI(title="golf-shot-cutter API", version="0.2.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()  # uvicorn entry point
