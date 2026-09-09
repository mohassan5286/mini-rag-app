from celery import Celery
from celery.schedules import crontab
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from helpers.config import get_settings
from stores.llm.llm_provider_factory import LLMProviderFactory
from stores.llm.templates import TemplateParser
from stores.vectordb.vectordb_provider_factory import VectorDBProviderFactory

import logging

logger = logging.getLogger(__name__)

settings = get_settings()

async def get_setup_utils():
    DATABASE_URL = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    db_engine = create_async_engine(DATABASE_URL)
    db_client = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    llm_provider_factory = LLMProviderFactory(configs=settings)

    generation_client = llm_provider_factory.create_provider(settings.GENERATION_BACKEND)
    generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    embedding_client = llm_provider_factory.create_provider(settings.EMBEDDING_BACKEND)
    embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

    vectordb_provider_factory = VectorDBProviderFactory(configs=settings)
    vectordb_client = vectordb_provider_factory.create(settings.VECTOR_DB_BACKEND, db_client)
    await vectordb_client.connect()

    template_parser = TemplateParser(language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG)

    return (
        db_engine,
        db_client,
        generation_client,
        embedding_client,
        vectordb_client,
        template_parser
    )

celery_app = Celery(
    "mini-rag",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.file_processing", "tasks.data_indexing", "tasks.process_workflow", "tasks.maintenance"]
)

celery_app.conf.update(
    task_serializer=settings.CELERY_TASK_SERIALIZER,
    result_serializer=settings.CELERY_RESULT_SERIALIZER,
    accept_content=[settings.CELERY_TASK_SERIALIZER, settings.CELERY_RESULT_SERIALIZER],
    
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    task_reject_on_worker_lost=True,
    
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,

    task_ignore_result=False,
    result_expires=3600,

    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,

    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    task_routes={
        "tasks.file_processing.process_project_files": {"queue": "file_processing"},
        "tasks.data_indexing.index_data_content": {"queue": "data_indexing"}, 
        "tasks.process_workflow.process_and_push_workflow": {"queue": "file_processing"},
        "tasks.process_workflow.push_after_process_task": {"queue": "data_indexing"}
    },

    beat_schedule={
        "cleanup-stale-tasks-daily": {
            "task": "tasks.maintenance.cleanup_idempotency_tasks",
            "schedule": crontab(minute=0, hour=0),
        }
    },

    timezone="UTC"
)

celery_app.conf.task_default_queue = "default"
