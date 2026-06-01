import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.depndencies.dependencies import (
    MONGO_ENV_VARS,
    get_logs_path,
    reinitialize_db_service,
)

system_router = APIRouter(prefix="/system", tags=["system"])

# TODO: Add admin authorization for all system endpoints


class EnvVarValue(BaseModel):
    value: str


@system_router.get("/logs", response_class=FileResponse)
async def get_logs(logs_path=Depends(get_logs_path)):
    """
    Returns app logs formed by loguru logs.
    """

    return FileResponse(
        path=logs_path,
        filename=f"chat-storage-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log",
    )


@system_router.get("/env")
async def get_all_env_vars():
    """
    Returns all current environment variables as a key-value mapping.
    """
    return dict(os.environ)


@system_router.patch("/env")
async def update_env_vars(variables: dict[str, str]):
    """
    Updates multiple environment variables at once.
    Body: {"KEY": "value", ...}
    Reinitializes the DB service if any MONGO_* variable is changed.
    """
    for key, value in variables.items():
        os.environ[key] = value
    if MONGO_ENV_VARS & variables.keys():
        await reinitialize_db_service()
    return {"updated": list(variables.keys())}


@system_router.get("/env/{key}")
async def get_env_var(key: str):
    """
    Returns the value of a specific environment variable by key.
    """
    value = os.environ.get(key)
    if value is None:
        raise HTTPException(
            status_code=404, detail=f"Environment variable '{key}' not found"
        )
    return {"key": key, "value": value}


@system_router.put("/env/{key}")
async def update_env_var(key: str, body: EnvVarValue):
    """
    Sets or updates the value of a specific environment variable.
    Body: {"value": "new_value"}
    Reinitializes the DB service if a MONGO_* variable is changed.
    """
    os.environ[key] = body.value
    if key in MONGO_ENV_VARS:
        await reinitialize_db_service()
    return {"key": key, "value": body.value}
