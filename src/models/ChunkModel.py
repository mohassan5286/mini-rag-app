from bson import ObjectId

from .db_schemes import DataChunk, Project
from .BaseDataModel import BaseDataModel
from sqlalchemy import delete, insert, select, func
from sqlalchemy import text as sql_text

class ChunkModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client=db_client)
        return instance

    async def create_chunk(self, chunk:DataChunk):
        async with self.db_client() as session:
            session.add(chunk)
            await session.commit()
            await session.refresh(chunk)
        return chunk
    
    async def get_chunk(self, chunk_id:str):
        async with self.db_client() as session:
            chunk = await session.get(DataChunk, chunk_id)
        return chunk
    
    async def insert_many_chunks(self, chunks:list, batch_size:int = 100):
        async with self.db_client() as session:
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i+batch_size]
                batch_dicts = [
                    {k: v for k, v in chunk.__dict__.items() if not k.startswith('_')}
                    for chunk in batch
                ]
                stmt = insert(DataChunk).values(batch_dicts)
                await session.execute(stmt)
                await session.commit()
        return len(chunks)

    async def delete_chunks_by_project_id(self, project_id:ObjectId, collection_name:str):
        async with self.db_client() as session:
            drop_stmt = sql_text(f"DROP TABLE IF EXISTS {collection_name} CASCADE;")
            await session.execute(drop_stmt)
            
            stmt = delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
            result = await session.execute(stmt)
            deleted_count = result.rowcount
            await session.commit()
        return deleted_count

    async def get_project_chunks(self, project_id:ObjectId, page_no:int=1, page_size:int=50):
        async with self.db_client() as session:
            stmt = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset((page_no-1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            chunks = result.scalars().all()
        return chunks

    async def get_project_chunks_count(self, project_id:ObjectId):
        async with self.db_client() as session:
            stmt = select(func.count(DataChunk.chunk_id)).where(DataChunk.chunk_project_id == project_id)
            result = await session.execute(stmt)
            count = result.scalars().all()[0]
        return count
    