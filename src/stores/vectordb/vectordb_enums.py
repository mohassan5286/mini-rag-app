from enum import Enum


class VectorDBEnum(Enum):
    QDRANT = "QDRANT"
    PGVECTOR = "PGVECTOR"

class DistanceMethodEnum(Enum):
    COSINE = "cosine"
    DOT = "dot"

class PgVectorTableSchemeEnum(Enum):
    ID = 'id'
    TEXT = 'text'
    VECTOR = 'vector'
    CHUNK_ID = 'chunk_id'
    METADATA = 'metadata'
    _PREFIX = 'pgvector_'

class PgVectorDistanceMethodEnum(Enum):
    COSINE = "vector_cosine_ops"
    DOT = "vector_ip_ops"

class PgVectorIndexTypeEnum(Enum):
    HNSW = "hnsw"
    IVFFLAT = "ivfflat"
    