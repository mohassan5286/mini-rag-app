from .BaseController import BaseController
from models.db_schemes import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnums
from typing import List
import json

class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, embedding_client, template_parser):
        super().__init__()
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_name_{project_id}"

    def reset_vector_db_collection(self, project: Project):
        if not project:
            return False
        
        collection_name = self.create_collection_name(project_id=project.project_id)
        return self.vectordb_client.delete_collection(collection_name = collection_name)

    def get_vector_db_collection_info(self, project: Project):
        if not project:
            return False

        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = self.vectordb_client.get_collection_info(collection_name = collection_name)

        return json.loads(json.dumps(collection_info, default=lambda x: x.__dict__))

    def index_into_vector_db(self, project: Project, chunks: List[DataChunk], chunks_ids: List[int]):    
        if not project:
            return False

        collection_name = self.create_collection_name(project_id=project.project_id)

        chunks_text = [chunk.chunk_text for chunk in chunks]
        chunks_metadata = [chunk.chunk_metadata for chunk in chunks]
        chunks_vector = [self.embedding_client.embed_text(text=chunk_text, document_type=DocumentTypeEnums.DOCUMENT.value) for chunk_text in chunks_text]
    

        return self.vectordb_client.insert_many(
            collection_name=collection_name,
            texts=chunks_text,
            vectors=chunks_vector,
            record_ids=chunks_ids,
            metadata=chunks_metadata,
            batch_size=50
        )


    def search_vector_db_collection(self, project: Project, text: str, limit: int = 10):
        if not project:
            return False

        collection_name = self.create_collection_name(project_id=project.project_id)
        results =  self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=self.embedding_client.embed_text(text=text, document_type=DocumentTypeEnums.QUERY.value),
            limit=limit
        )

        return results

    def answer_rag_question(self, project: Project, query: str, limit: int = 10):
        answer, full_prompt, chat_history = None, None, None
        
        retrieved_documents =  self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history

        system_prompt = self.template_parser.get(group = "rag", key = "system_prompt")
        document_prompt = "\n".join([self.template_parser.get(group = "rag", key = "document_prompt", vars = {"doc_num": idx + 1, "chunk_text": retrieved_document.text} ) for idx, retrieved_document in enumerate(retrieved_documents)])
        footer_prompt = self.template_parser.get(group = "rag", key = "footer_prompt", vars = {"query": query})
        
        full_prompt = "\n\n".join([document_prompt, footer_prompt])

        chat_history = [self.generation_client.construct_prompt(prompt=system_prompt, role=self.generation_client.enums.SYSTEM.value)]

        answer = self.generation_client.generate_text(
            prompt = full_prompt,
            chat_history = chat_history,

        )

        return answer, full_prompt, chat_history
    