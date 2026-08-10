from qdrant_client import models, QdrantClient

from models.db_schemes import DocumentRetrived
from ..VectorDBInterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums
from typing import List
from logging import getLogger


class QdrantDBProvider(VectorDBInterface):
    
    def __init__(self, db_client, distance_method: str, default_vector_size: int = 786, index_threshold: int = 100):
        self.client = None
        self.db_client = db_client

        self.logger = getLogger(__name__)

        if distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT

        elif distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE

        else:
            self.logger.error(f"Invalid distance method: {self.distance_method}")
            raise ValueError(f"Invalid distance method: {self.distance_method}")


        self.default_vector_size = default_vector_size
        self.index_threshold = index_threshold

    async def connect(self):
        self.client = QdrantClient(path=self.db_client)

    async def disconnect(self):
        self.client = False

    async def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name)

    async def list_all_collections(self) -> List  :
        return self.client.get_collections()

    async def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name)

    async def delete_collection(self, collection_name: str):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False

        return self.client.delete_collection(collection_name)

    async def create_collection(self, collection_name: str, embedding_size: int,do_reset: bool = False):
        if self.is_collection_existed(collection_name):
            if do_reset:
                _ = self.delete_collection(collection_name)
            else:
                self.logger.error(f"Collection {collection_name} already exists")
                return False

        return self.client.create_collection(collection_name, vectors_config = models.VectorParams(size = embedding_size,distance = self.distance_method))

    async def insert_one(self, collection_name: str, text: str, vector: list, record_id: int, metadata: dict = None):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False

        try:
            _ = self.client.upload_records(
                collection_name=collection_name,
                records=[
                    models.Record(
                        id=record_id,
                        vector=vector,
                        payload = {
                            "text": text,
                            "metadata": metadata
                        }
                    )
                ]
            )

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return False

        return True

    async def insert_many(self, collection_name: str, texts: list, vectors: list, record_ids: list, metadata: list = None, batch_size: int = 50):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False

        if metadata is None:
            metadata = [None] * len(texts)

        try:
            for i in range(0, len(texts), batch_size):
                _ = self.client.upload_records(
                    collection_name=collection_name,
                    records=[
                        models.Record(
                            id = record_id,
                            vector=vector,
                            payload = {
                                "text": text,
                                "metadata": metadata
                            }
                        )
                        for record_id, text, vector, metadata in zip(record_ids[i:i+batch_size], texts[i:i+batch_size], vectors[i:i+batch_size], metadata[i:i+batch_size])
                    ]
                )

        except Exception as e:
            self.logger.error(f"Error: {e}")
            return False

        return True

    async def search_by_vector(self, collection_name: str, vector: list, limit: int):
        if not self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False
        
        results = self.client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=limit
        )

        return [DocumentRetrived(text = result.payload['text'], score = result.score) for result in results]
    