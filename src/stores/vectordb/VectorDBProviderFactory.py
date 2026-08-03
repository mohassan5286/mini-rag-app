from .providers.QdrantDBProvider import QdrantDBProvider
from .VectorDBEnums import VectorDBEnums
from controllers import BaseController

class VectorDBProviderFactory:
    def __init__(self, configs):
        self.configs = configs
        self.base_controller = BaseController()
   
    def create(self, provider:str):
        if provider == VectorDBEnums.QDRANT.value:
            database_path = self.base_controller.get_database_path(self.configs.VECTOR_DB_PATH)
            return QdrantDBProvider(db_path = database_path, distance_method = self.configs.VECTOR_DB_DISTANCE_METHOD)

        return None

        