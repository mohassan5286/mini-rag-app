import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from models.db_schemes.minirag.schemes.celery_task_execution import CeleryTaskExecution


class IdempotencyManager:
    def __init__(self, db_client, db_engine):
        self.db_client = db_client
        self.db_engine = db_engine


    def create_args_hash(self, task_name: str, task_args: dict):
        combined_data = {
            "task_name": task_name,
            **task_args
        }
        json_string = json.dumps(combined_data, sort_keys=True, default=str)
        return hashlib.sha256(json_string.encode()).hexdigest()


    async def create_task_record(self, task_name: str, task_args: dict, celery_task_id: str | None = None) -> CeleryTaskExecution:
        task_args_hash = self.create_args_hash(task_name, task_args)

        new_task = CeleryTaskExecution(
            task_name=task_name,
            task_args=task_args,
            task_args_hash=task_args_hash,
            celery_task_id=celery_task_id,
            status="PENDING"
        )

        async with self.db_client() as session:
            session.add(new_task)
            await session.commit()
            await session.refresh(new_task)
            return new_task


    async def update_task_status(self, execution_id: int, status: str, result: dict | None = None):
        async with self.db_client() as session:
            task_record = await session.get(CeleryTaskExecution, execution_id)
            if task_record:
                task_record.status = status
                if result:
                    task_record.result = result
                if status in ["SUCCESS", "FAILURE"]:
                    task_record.completed_at = datetime.now(timezone.utc)
                await session.commit()

    async def get_existing_task(self, task_name: str, task_args: dict) -> CeleryTaskExecution:
        task_args_hash = self.create_args_hash(task_name, task_args)
        async with self.db_client() as session:
            task_record = await session.execute(
                select(CeleryTaskExecution).where(
                    CeleryTaskExecution.task_name == task_name,
                    CeleryTaskExecution.task_args_hash == task_args_hash
                )
            )
    
            record = task_record.scalars().first()
            return record

    async def should_execute_task(self, task_name: str, task_args: dict, task_time_limit: int = 600) -> tuple[bool, CeleryTaskExecution | None]:
        existing_task = await self.get_existing_task(task_name, task_args)
        
        if not existing_task:
            return True, None

        if existing_task.status == "SUCCESS":
            return False, existing_task
            
        if existing_task.status == "FAILURE":
            return True, existing_task

        reference_time = existing_task.started_at or existing_task.created_at
        
        if reference_time:
            time_elapsed = (datetime.now(timezone.utc) - reference_time).total_seconds()
            
            if time_elapsed > task_time_limit:
                return True, existing_task
                
        return False, existing_task


    async def cleanup_old_tasks(self, time_retention: int = 86400) -> int:
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_retention)
        
        async with self.db_client() as session:
            stmt = delete(CeleryTaskExecution).where(
                CeleryTaskExecution.created_at < cutoff_time
            )
            
            result = await session.execute(stmt)
            await session.commit()
            
            return result.rowcount
        