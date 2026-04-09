from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from loguru import logger
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.__version__ import APP_DESCRIPTION, APP_NAME, APP_VERSION
from app.common.middlewares.exception_handler import ExceptionHandlerMiddleware
from app.depndencies.dependencies import get_app_configuration


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_config = await get_app_configuration()
    logger.info(
        f"Loaded app configuration with values: {app_config.get_configuration_values()}"
    )
    yield
    logger.info("App is shutting down")


app = FastAPI(
    version=APP_VERSION,
    title=APP_NAME,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ExceptionHandlerMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=100)


@app.get("/ping")
async def ping_server():
    return {"status": "ok", "message": "pong"}


@app.get("/", include_in_schema=False)
async def root_to_docs():
    return RedirectResponse("/docs")
