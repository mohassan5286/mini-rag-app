import json

from models.db_schemes import DataChunk, Project
from stores.llm.llm_enums import DocumentTypeEnum

from .base_controller import BaseController


class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, embedding_client, template_parser):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_name_{project_id}_{self.vectordb_client.default_vector_size}"

    async def reset_vector_db_collection(self, project: Project):
        if not project:
            return False
        
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vectordb_client.delete_collection(collection_name = collection_name)

    async def get_vector_db_collection_info(self, project: Project):
        if not project:
            return False

        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vectordb_client.get_collection_info(collection_name = collection_name)

        return json.loads(json.dumps(collection_info, default=lambda x: x.__dict__))

    async def index_into_vector_db(self, project: Project, chunks: list[DataChunk], chunks_ids: list[int]):    
        if not project:
            return False

        collection_name = self.create_collection_name(project_id=project.project_id)
        
        chunks_text = [chunk.chunk_text for chunk in chunks]
        chunks_metadata = [chunk.chunk_metadata for chunk in chunks]
        chunks_vector = self.embedding_client.embed_text(text=chunks_text, document_type=DocumentTypeEnum.DOCUMENT.value)
    

        return await self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=chunks_text,
            vectors=chunks_vector,
            record_ids=chunks_ids,
            metadata=chunks_metadata,
            batch_size=50
        )


    async def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):
        if not project:
            return False

        vector = self.embedding_client.embed_text(text=text, document_type=DocumentTypeEnum.QUERY.value)
        if not vector:
            return False

        query_vector = vector[0]

        collection_name = self.create_collection_name(project_id=project.project_id)
        results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=query_vector,
            limit=limit
        )

        return results

    async def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        answer, full_prompt, chat_history = None, None, None
        
        retrieved_documents = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history

        system_prompt = self.template_parser.get(group = "rag", key = "system_prompt")
        document_prompt = "\n".join([self.template_parser.get(group = "rag", key = "document_prompt", vars = {"doc_num": idx + 1, "chunk_text": self.generation_client.process_text(retrieved_document.text)} ) for idx, retrieved_document in enumerate(retrieved_documents)])
        footer_prompt = self.template_parser.get(group = "rag", key = "footer_prompt", vars = {"query": query})
        
        full_prompt = f"{document_prompt}\n\n{footer_prompt}"

        chat_history = [self.generation_client.construct_prompt(prompt=system_prompt, role=self.generation_client.enums.SYSTEM.value)]

        answer = self.generation_client.generate_text(
            prompt = full_prompt,
            chat_history = chat_history,

        )

        return answer, full_prompt, chat_history
    