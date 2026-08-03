from ..LLMInterface import LLMInterface
from ..LLMEnums import CoHereEnums, DocumentTypeEnums
import cohere
import logging

class CoHereProvider(LLMInterface):
    def __init__(self, api_key: str, default_input_max_characters: int = 1000, default_output_max_characters: int = 1000, default_generation_temperature: float = 0.1):
        self.api_key = api_key
        
        self.default_input_max_characters = default_input_max_characters
        self.default_output_max_characters = default_output_max_characters
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        self.enums = CoHereEnums

        self.client = cohere.Client(self.api_key)
        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def generate_text(self, prompt: str, chat_history: list = [], max_output_tokens: int = None, temperature: float = None):
        if not self.client:
            self.logger.error("CoHere client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for CoHere was not set")
            return None
        
        max_output_tokens = max_output_tokens if max_output_tokens else self.default_output_max_characters
        temperature = temperature if temperature else self.default_generation_temperature

        response = self.client.chat(
            model=self.generation_model_id,
            chat_history=chat_history,
            message=self.process_text(prompt),
            temperature=temperature,
            max_tokens=max_output_tokens
        )

        if not response or not response.text:
            self.logger.error("Error while generating text with CoHere")
            return None
        
        return response.text

    def embed_text(self, text: str, document_type: str = None):
        if not self.client:
            self.logger.error("CoHere client was not set")
            return None 

        if not self.embedding_model_id:
            self.logger.error("Embedding model for CoHere was not set")
            return None

        input_type = self.enums.DOCUMENT.value if hasattr(self.enums.DOCUMENT, 'value') else self.enums.DOCUMENT
        if document_type == DocumentTypeEnums.QUERY.value:
            input_type = self.enums.QUERY.value if hasattr(self.enums.QUERY, 'value') else self.enums.QUERY

        response = self.client.embed(
            model=self.embedding_model_id,
            texts=[self.process_text(text)],
            input_type=input_type,
            embedding_types=['float']
        )

        if not response or not response.embeddings or not response.embeddings.float:
            self.logger.error("Error while embedding text with CoHere")
            return None

        return response.embeddings.float[0]
    
    def process_text(self, text: str):
        return text[:self.default_input_max_characters].strip()


    def construct_prompt(self, prompt: str, role: str):
        return {"role": role, "message": self.process_text(prompt)}