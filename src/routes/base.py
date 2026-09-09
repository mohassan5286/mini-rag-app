from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from helpers.config import get_settings

router = APIRouter()


@router.get("/")
def welcome(settings=Depends(get_settings)):
    APP_NAME = settings.APP_NAME
    APP_VERSION = settings.APP_VERSION

    return {
        "message": "Welcome to the FastAPI application!",
        "App Name": APP_NAME,
        "App Version": APP_VERSION,
	    "current_time": datetime.now(timezone.utc),
    }
