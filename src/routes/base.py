from fastapi import APIRouter, Depends
from helpers.config import get_settings
from datetime import datetime, timezone
from tasks.mail_service import send_email


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

@router.get("/send_email")
async def trigger_email():
    task = send_email.delay(wait_time=5)
    return {
        "state": "success",
        "task_id": task.id
        }

