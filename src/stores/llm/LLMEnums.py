from enum import Enum

class LLMEnums(Enum):
    
    OPENAI = "OPENAI"
    COHERE = "COHERE"

class OpenAIEnums(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class CoHereEnums(Enum):
    SYSTEM = "System"
    USER = "User"
    ASSISTANT = "Chatbot"

    DOCUMENT = "search_document"
    QUERY = "search_query"

class DocumentTypeEnums(Enum):
    DOCUMENT = "DOCUMENT"
    QUERY = "QUERY"