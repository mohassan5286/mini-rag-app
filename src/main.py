from contextlib import asynccontextmanager

from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from helpers.config import get_settings
from routes.base import router
from routes.data import data_router
from routes.nlp import nlp_router
from stores.llm.llm_provider_factory import LLMProviderFactory
from stores.vectordb.vector_db_provider_factory import VectorDBProviderFactory
from stores.llm.templates import TemplateParser


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    app.db_client = AsyncIOMotorClient(settings.MONGODB_URL)
    app.mongodb = app.db_client[settings.MONGODB_DATABASE]

    llm_provider_factory = LLMProviderFactory(configs = settings)

    app.generation_client = llm_provider_factory.create_provider(settings.GENERATION_BACKEND)
    app.generation_client.set_generation_model(settings.GENERATION_MODEL_ID)

    app.embedding_client = llm_provider_factory.create_provider(settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)

    vectordb_provider_factory = VectorDBProviderFactory(configs = settings)
    app.vectordb_client = vectordb_provider_factory.create(settings.VECTOR_DB_BACKEND)
    app.vectordb_client.connect()

    app.template_parser = TemplateParser(language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG)

    yield 

    app.db_client.close()
    app.vectordb_client.disconnect()

app = FastAPI(lifespan=lifespan)

app.include_router(router)
app.include_router(data_router)
app.include_router(nlp_router)
