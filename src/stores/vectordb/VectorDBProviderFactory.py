from .providers import QdrantDBProvider, PGVectorProvider
from .VectorDBEnums import VectorDBEnums
from controllers import BaseController
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

class VectorDBProviderFactory:
    def __init__(self, configs):
        self.configs = configs
        self.base_controller = BaseController()
   
    def create(self, provider:str, db_client: async_sessionmaker[AsyncSession]):
        if provider == VectorDBEnums.QDRANT.value:
            database_path = self.base_controller.get_database_path(self.configs.VECTOR_DB_CLIENT)
            return QdrantDBProvider(db_client = database_path, distance_method = self.configs.VECTOR_DB_DISTANCE_METHOD, default_vector_size = self.configs.EMBEDDING_MODEL_SIZE, index_threshold = self.configs.VECTOR_DB_PGVEC_INDEX_THRESHOLD)

        if provider == VectorDBEnums.PGVECTOR.value:

            return PGVectorProvider(db_client = db_client, distance_method = self.configs.VECTOR_DB_DISTANCE_METHOD, )
        
        return None
