import asyncio
from celery_app import celery_app
import logging


logger = logging.getLogger("celery.task")

@celery_app.task(bind = True, name="tasks.mail_service.send_email")
def send_email(self, wait_time:int):
    return asyncio.run(_send_email(self, wait_time))

async def _send_email(task_instance, wiat_time:int):
    for i in range(15):
        print(f"Sending email {i}")
        await asyncio.sleep(wiat_time)
        logger.warning(f"Sending email {i}")

    task_instance.update_state(state="SUCCESS")