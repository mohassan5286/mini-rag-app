from .BaseController import BaseController
from .ProjectController import ProjectController

from models import ProcessEnums

from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader

from typing import List
from dataclasses import dataclass

import os

@dataclass
class Retrived:
    page_content: str
    metadata: dict

class ProcessController(BaseController):
    def __init__(self, project_id: str):
        super().__init__()

        self.project_path = ProjectController().get_project_path(project_id=project_id)

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1]
    
    def get_file_loader(self, file_id: str):
        file_extension = self.get_file_extension(file_id=file_id)
        file_path = os.path.join(self.project_path, file_id)
 
        if not os.path.exists(file_path):
            return None

        if file_extension == ProcessEnums.TEXT.value:
            return TextLoader(file_path, encoding="utf-8")
    
        elif file_extension == ProcessEnums.PDF.value:
            return PyMuPDFLoader(file_path)
    
        return None

    def get_file_content(self, file_id: str):
        loader = self.get_file_loader(file_id=file_id)
        if loader is not None:
            return loader.load()
        
        return None
    
    def process_file_content(self, file_content:list, file_id: str, chunk_size:int=100, chunk_overlap:int=20):
        file_content_texts = [rec.page_content for rec in file_content]
        file_content_metadata = [rec.metadata for rec in file_content]

        chunks = self.process_simpler_splitter(texts=file_content_texts, metadatas=file_content_metadata, chunk_size=chunk_size, text_splitter=".")

        return chunks

    def process_simpler_splitter(self, texts: List[str], metadatas: List[dict], chunk_size: int=100, text_splitter: str = "."):
        full_text = " ".join(texts)
        sentences = [docs.strip() for docs in full_text.split(text_splitter) if len(docs.strip()) > 1]

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            current_chunk += sentence + text_splitter
            if len(current_chunk) >= chunk_size:
                chunks.append(
                    Retrived(
                        page_content=current_chunk.strip(),
                        metadata={}
                    )
                )
                current_chunk = ""
        
        if current_chunk:
            chunks.append(
                Retrived(
                    page_content=current_chunk.strip(),
                    metadata={}
                )
            )

        return chunks
