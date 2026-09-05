import asyncio
import logging

from fastapi.responses import JSONResponse
from celery_app import celery_app, get_setup_utils
from fastapi import APIRouter
from celery.exceptions import Ignore

from controllers import NLPController
from models import ResponseEnums, ProjectModel, ChunkModel

logger = logging.getLogger(__name__)
data_router = APIRouter()

@celery_app.task(bind=True, name="tasks.data_indexing.index_data_content")
def index_data_content(self, project_id: int, do_reset: bool):
    return asyncio.run(_index_data_content(self, project_id, do_reset))


async def _index_data_content(task_instance, project_id: int, do_reset: bool):
    (db_engine, db_client, generation_client, embedding_client, vectordb_client, template_parser) = await get_setup_utils()
    try:
        project_model = await ProjectModel.create_instance(db_client)
        project = await project_model.get_project_or_create_one(project_id=project_id)    
    
        chunk_model = await ChunkModel.create_instance(db_client)
    
        nlp_controller = NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser
        )
    
        collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
        _ = await vectordb_client.create_collection(
            collection_name=collection_name, 
            embedding_size=embedding_client.embedding_size, 
            do_reset=do_reset
        )
    
        has_records = True
        page_no = 1
        inserted_items_count = 0
        idx = 0
    
        chunks_count = await chunk_model.get_project_chunks_count(project_id=project.project_id) 
    
        while has_records:
            page_chunks = await chunk_model.get_project_chunks(project_id=project.project_id, page_no=page_no)
            
            if len(page_chunks):
                page_no += 1
                inserted_items_count += len(page_chunks)
    
                chunks_ids = [chunk.chunk_id for chunk in page_chunks]
                idx += len(page_chunks)
    
                is_inserted = await nlp_controller.index_into_vector_db(
                    project=project,
                    chunks=page_chunks,
                    chunks_ids=chunks_ids
                )
    
                if not is_inserted:
                    task_instance.update_state(
                        state="FAILURE",
                        meta={
                            "signal": ResponseEnums.ERROR.value,
                            "error": "Failed to insert chunks into the vector database."
                        }
                    )
                    raise Ignore()
                    
            else:
                has_records = False

        task_instance.update_state(
            state="SUCCESS",
            meta={
                "signal": ResponseEnums.SUCCESS.value,
                "inserted_items_count": inserted_items_count
            }
        )

        return {
            "signal": ResponseEnums.SUCCESS.value,
            "inserted_items_count": inserted_items_count
        }

    except Ignore:
        raise

    except Exception as e:
        logger.error(f"Error occurred while processing the project: {e}")
        task_instance.update_state(
            state="FAILURE",
            meta={
                "error": f"Error occurred while processing the project: {e}",
                "signal": ResponseEnums.ERROR.value
            }
        )
        raise Ignore()
        
    finally:
        await db_engine.dispose()