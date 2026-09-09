import json
from logging import getLogger

from sqlalchemy import text as sql_text

from models.db_schemes import DocumentRetrived

from ..vectordb_enums import (
    DistanceMethodEnum,
    PgVectorDistanceMethodEnum,
    PgVectorIndexTypeEnum,
    PgVectorTableSchemeEnum,
)
from ..vectordb_interface import VectorDBInterface


class PGVectorProvider(VectorDBInterface):
    def __init__(self, db_client, distance_method: str, default_vector_size: int = 768, index_threshold: int = 100):
        self.db_client = db_client

        self.default_vector_size = default_vector_size

        if distance_method == DistanceMethodEnum.COSINE.value:
            self.distance_method = "<=>"
            self.index_op_class = PgVectorDistanceMethodEnum.COSINE.value
        else:
            self.distance_method = "<#>"
            self.index_op_class = PgVectorDistanceMethodEnum.DOT.value

        self.index_threshold = index_threshold

        self.pgvector_table_prefix = PgVectorTableSchemeEnum._PREFIX.value
        
        self.logger = getLogger("uvicorn")

        self.index_name = lambda collection_name: f"{collection_name}_vector_index"

    def create_table_name(self, collection_name: str) -> str:
        if collection_name.startswith(self.pgvector_table_prefix):
            return collection_name
        return f"{self.pgvector_table_prefix}{collection_name}"
    
    async def connect(self):
        async with self.db_client() as session, session.begin():
            stmt = sql_text("CREATE EXTENSION IF NOT EXISTS vector;")
            await session.execute(stmt)
                
    async def disconnect(self):
        pass

    async def is_collection_existed(self, collection_name: str) -> bool:
        collection_name = self.create_table_name(collection_name)
        async with self.db_client() as session, session.begin():
            stmt = sql_text("""
                    SELECT * 
                    FROM pg_tables 
                    WHERE tablename = :collection_name;
                """)

            results = await session.execute(stmt, {"collection_name": collection_name})
            record = results.scalar_one_or_none()

        return bool(record)

    async def list_all_collections(self) -> list:
        async with self.db_client() as session, session.begin():
            stmt = sql_text(f"""
                    SELECT tablename 
                    FROM pg_tables 
                    WHERE tablename LIKE '{self.pgvector_table_prefix}%';
                """)

            results = await session.execute(stmt)
            records = results.scalars().all()

        return records

    async def get_collection_info(self, collection_name: str) -> dict:
        collection_name = self.create_table_name(collection_name)
        async with self.db_client() as session, session.begin():
                
                table_info_sql = sql_text('''
                    SELECT schemaname, tablename, tableowner, tablespace, hasindexes 
                    FROM pg_tables 
                    WHERE tablename = :collection_name
                ''')


                table_info = await session.execute(table_info_sql, {"collection_name": collection_name})
                table_data = table_info.fetchone()
                if not table_data:
                    return None

                count_sql = sql_text(f'SELECT COUNT(*) FROM {collection_name}')
                record_count = await session.execute(count_sql)
                
                return {
                    "table_info": {
                        "schemaname": table_data[0],
                        "tablename" : table_data[1],
                        "tableowner": table_data[2],
                        "tablespace": table_data[3],
                        "hasindexes": table_data[4],
                    },
                    "record_count": record_count.scalar_one(),
                }

    async def delete_collection(self, collection_name: str):
        collection_name = self.create_table_name(collection_name)
        async with self.db_client() as session, session.begin():
            stmt = sql_text(f"DROP TABLE IF EXISTS {collection_name};")
            await session.execute(stmt)
                

    async def create_collection(self, collection_name: str, embedding_size: int,do_reset: bool = False):
        collection_name = self.create_table_name(collection_name)
        if await self.is_collection_existed(collection_name):
            if do_reset:
                await self.delete_collection(collection_name)
            else:
                self.logger.error(f"Collection {collection_name} already exists")
                return False

        async with self.db_client() as session, session.begin():
                stmt = sql_text(
                            f'CREATE TABLE {collection_name} ('
                                f'{PgVectorTableSchemeEnum.ID.value} bigserial PRIMARY KEY,'
                                f'{PgVectorTableSchemeEnum.TEXT.value} text, '
                                f'{PgVectorTableSchemeEnum.VECTOR.value} vector({embedding_size}), '
                                f'{PgVectorTableSchemeEnum.METADATA.value} jsonb DEFAULT \'{{}}\', '
                                f'{PgVectorTableSchemeEnum.CHUNK_ID.value} integer, '
                                f'FOREIGN KEY ({PgVectorTableSchemeEnum.CHUNK_ID.value}) REFERENCES chunks(chunk_id)'
                            ')'
                        )

                await session.execute(stmt)
                

        if await self.is_collection_existed(collection_name):
            self.logger.info(f"Collection {collection_name} created successfully")
            return True

        self.logger.error(f"Error while creating collection {collection_name}")
        return False
    

    async def insert_one(self, collection_name: str, text: str, vector: list, record_id: int, metadata: dict | None = None):
        collection_name = self.create_table_name(collection_name)
        is_collection_existed = await self.is_collection_existed(collection_name)
        if not is_collection_existed:
            self.logger.error(f"Collection {collection_name} does not exist")
            return False

        async with self.db_client() as session, session.begin():
                vector_str = "[" + ", ".join(str(v) for v in vector) + "]"
                metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata is not None else "{}"
                stmt = sql_text(f"INSERT INTO {collection_name} ({PgVectorTableSchemeEnum.TEXT.value}, {PgVectorTableSchemeEnum.VECTOR.value}, {PgVectorTableSchemeEnum.METADATA.value}, {PgVectorTableSchemeEnum.CHUNK_ID.value}) VALUES (:text, :vector, :metadata, :chunk_id)")
                await session.execute(stmt, {"text": text, "vector": vector_str, "metadata": metadata_json, "chunk_id": record_id})
                
                return True

        self.logger.info(f"Inserted record into collection {collection_name}")
        return True

    async def insert_many(self, collection_name: str, texts: list, vectors: list, record_ids: list, metadata: list | None = None, batch_size: int = 50):
        collection_name = self.create_table_name(collection_name)
        is_collection_existed = await self.is_collection_existed(collection_name)
        if not is_collection_existed:
            self.logger.error(f"Collection {collection_name} does not exist")
            return False

        async with self.db_client() as session, session.begin():
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i+batch_size]
                    batch_vectors = vectors[i:i+batch_size]
                    batch_metadata = metadata[i:i+batch_size] if metadata else [None] * len(batch_texts)
                    batch_record_ids = record_ids[i:i+batch_size]

                    values = []
                    for text, vector, meta, record_id in zip(batch_texts, batch_vectors, batch_metadata, batch_record_ids):
                        vector_str = "[" + ", ".join(str(v) for v in vector) + "]"
                        metadata_json = json.dumps(meta, ensure_ascii=False) if meta is not None else "{}"
                        values.append({"text": text, "vector": vector_str, "metadata": metadata_json, "chunk_id": record_id})

                    stmt = sql_text(f"INSERT INTO {collection_name} ({PgVectorTableSchemeEnum.TEXT.value}, {PgVectorTableSchemeEnum.VECTOR.value}, {PgVectorTableSchemeEnum.METADATA.value}, {PgVectorTableSchemeEnum.CHUNK_ID.value}) VALUES (:text, :vector, :metadata, :chunk_id)")
                    await session.execute(stmt, values)
                    

        await self.create_index(collection_name = collection_name)
        self.logger.info(f"Inserted {len(texts)} records into collection {collection_name}")
        return True
    
    async def search_by_vector(self, collection_name: str, vector: list, limit: int) -> list[DocumentRetrived]:
        collection_name = self.create_table_name(collection_name)
        is_collection_existed = await self.is_collection_existed(collection_name)
        if not is_collection_existed:
            self.logger.error(f"Collection {collection_name} does not exist")
            return False

        vector_str = "[" + ", ".join(str(v) for v in vector) + "]"

        async with self.db_client() as session, session.begin():
                stmt = sql_text(f"""
                    SELECT 
                        {PgVectorTableSchemeEnum.TEXT.value} AS text,
                        1 - ({PgVectorTableSchemeEnum.VECTOR.value} {self.distance_method} CAST(:query_vector AS vector)) AS score
                    FROM 
                        {collection_name} 
                    ORDER BY 
                        {PgVectorTableSchemeEnum.VECTOR.value} {self.distance_method} CAST(:query_vector AS vector)
                    LIMIT 
                        :limit;
                """)
                
                results = await session.execute(stmt, {
                    "query_vector": vector_str,
                    "limit": limit
                })
                
                records = results.fetchall()
                
                return [
                    DocumentRetrived(text = row.text, score = row.score)
                    for row in records
                ]

    async def delete_index(self, collection_name: str):
        collection_name = self.create_table_name(collection_name)
        if not await self.is_collection_existed(collection_name):
            self.logger.error(f"Collection {collection_name} does not exist")
            return False

        async with self.db_client() as session, session.begin():
                stmt = sql_text(f"DROP INDEX IF EXISTS {self.index_name(collection_name)};")
                await session.execute(stmt)
                

        self.logger.info(f"Index deleted for collection {collection_name}")
        return True

    async def create_index(self, collection_name: str, index_type: str = PgVectorIndexTypeEnum.HNSW.value):
        collection_name = self.create_table_name(collection_name)
        is_collection_existed = await self.is_collection_existed(collection_name)
        if not is_collection_existed:
            self.logger.error(f"Collection {collection_name} does not exist")
            return False
        
        async with self.db_client() as session, session.begin():
                count_sql = sql_text(f'SELECT COUNT(*) FROM {collection_name}')    
                record_count = await session.execute(count_sql)

                if record_count.scalar_one() < self.index_threshold:
                    self.logger.error(f"Collection {collection_name} has less than {self.index_threshold} records")
                    return False
                    
                stmt = sql_text(f"""
                    CREATE INDEX IF NOT EXISTS {self.index_name(collection_name)} 
                    ON {collection_name} 
                    USING {index_type} ({PgVectorTableSchemeEnum.VECTOR.value} {self.index_op_class});
                """)
                
                await session.execute(stmt)
                

        self.logger.info(f"Index created for collection {collection_name}")
        return True

    async def reset_vector_index(self, collection_name: str, index_type: str = PgVectorIndexTypeEnum.HNSW.value) -> bool:
        collection_name = self.create_table_name(collection_name)
        index_name = self.index_name(collection_name)
        async with self.db_client() as session, session.begin():
                drop_sql = sql_text(f'DROP INDEX IF EXISTS {index_name}')
                await session.execute(drop_sql)

        return await self.create_index(collection_name=collection_name, index_type=index_type)
    