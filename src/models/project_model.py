from sqlalchemy import func, select

from .base_data_model import BaseDataModel
from .db_schemes import Project


class ProjectModel(BaseDataModel):

    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client=db_client)
        return instance

    async def create_project(self, project:Project):
        async with self.db_client() as session:
            session.add(project)
            await session.commit()
            await session.refresh(project)
        return project
    
    async def get_project_or_create_one(self, project_id: str):
        async with self.db_client() as session:
            project = await session.get(Project, project_id)
            if project is None:
                project = Project(project_id=project_id)
                project = await self.create_project(project=project)
                return project
            return project

    
    async def get_all_projects(self, page: int=1, page_size: int=10):
        async with self.db_client() as session:
            stmt = select(func.count()).select_from(Project)
            result = await session.execute(stmt)
            total_documents = result.scalar_one()
            total_pages = total_documents // page_size
            if total_documents % page_size:
                total_pages += 1

            query = select(Project).offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(query)
            projects = result.scalars().all()

            return projects, total_pages
        