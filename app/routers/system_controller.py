from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.depndencies.dependencies import get_logs_path

system_router = APIRouter(prefix="/system", tags=["system"])


@system_router.get("/logs", response_class=FileResponse)
async def get_logs(logs_path=Depends(get_logs_path)):
    """
    Returns app logs formed by loguru logs.
    """

    return FileResponse(
        path=logs_path,
        filename=f"chat-storage-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log",
    )
