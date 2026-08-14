from fastapi import FastAPI
from routes.base import router
from routes.data import data_router
from routes.nlp import nlp_router
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from helpers.config import get_settings

from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory

from stores.llm.templates import TemplateParser

from utils.metrics import setup_metrics

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    DATABASE_URL = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.db_engine = create_async_engine(DATABASE_URL)

    app.db_client = async_sessionmaker(app.db_engine, class_=AsyncSession, expire_on_commit=False)

    llm_provider_factory = LLMProviderFactory(configs = settings)

    app.generation_client = llm_provider_factory.create_provider(settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    app.embedding_client = llm_provider_factory.create_provider(settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

    vectordb_provider_factory = VectorDBProviderFactory(configs = settings)
    app.vectordb_client = vectordb_provider_factory.create(settings.VECTOR_DB_BACKEND, app.db_client)
    await app.vectordb_client.connect()

    app.template_parser = TemplateParser(language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG)

    yield 

    await app.db_engine.dispose()
    await app.vectordb_client.disconnect()

app = FastAPI(lifespan=lifespan)

setup_metrics(app)

app.include_router(router)
app.include_router(data_router)
app.include_router(nlp_router)