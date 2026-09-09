import asyncio
import logging

from celery_app import celery_app, get_setup_utils
from utils.idempotency_manager import IdempotencyManager

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.maintenance.cleanup_idempotency_tasks")
def cleanup_idempotency_tasks():
    return asyncio.run(_cleanup_idempotency_tasks())

async def _cleanup_idempotency_tasks():
    (db_engine, db_client, _, _, _, _) = await get_setup_utils()
    
    try:
        idempotency_manager = IdempotencyManager(db_client=db_client, db_engine=db_engine)

        deleted_count = await idempotency_manager.cleanup_old_tasks(time_retention=10)
        
        logger.info(f"Successfully cleaned up {deleted_count} stale idempotency tasks.")
        return {"signal": "success", "deleted_records": deleted_count}
        
    except Exception as e:
        logger.error(f"Failed to clean up old tasks: {e}")
        raise
        
    finally:
        try:
            if db_engine:
                await db_engine.dispose()
        
        except Exception as e:
            logger.error(f"Task failed while cleaning DB connection: {str(e)}")
