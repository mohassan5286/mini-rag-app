import asyncio
import logging

from fastapi import APIRouter

from celery_app import celery_app, get_setup_utils
from controllers import NLPController
from models import ChunkModel, ProjectModel, ResponseEnum
from utils.idempotency_manager import IdempotencyManager

logger = logging.getLogger(__name__)
data_router = APIRouter()

@celery_app.task(bind=True, name="tasks.data_indexing.index_data_content")
def index_data_content(self, project_id: int, do_reset: bool):
    return asyncio.run(_index_data_content(self, project_id, do_reset))

async def _index_data_content(task_instance, project_id: int, do_reset: bool):
    (db_engine, db_client, generation_client, embedding_client, vectordb_client, template_parser) = await get_setup_utils()
    
    try:
        task_record = None
        idempotency_manager = IdempotencyManager(db_client=db_client, db_engine=db_engine)
        
        task_name = "tasks.data_indexing.index_data_content"
        task_args = {
            "project_id": project_id,
            "do_reset": do_reset
        }

        should_execute, existing_task = await idempotency_manager.should_execute_task(
            task_name=task_name,
            task_args=task_args
        )

        if not should_execute:
            logger.warning(f"Cannot handle the task | status: {existing_task.status}")
            return existing_task.result

        if existing_task:
            task_record = existing_task
            await idempotency_manager.update_task_status(execution_id=task_record.execution_id, status="PENDING")
        else:
            task_record = await idempotency_manager.create_task_record(
                task_name=task_name,
                task_args=task_args,
                celery_task_id=task_instance.request.id
            )

        project_model = await ProjectModel.create_instance(db_client)
        project = await project_model.get_project_or_create_one(project_id=project_id)    

        if not project:
            task_instance.update_state(
                state="FAILURE",
                meta={
                    "signal": ResponseEnum.PROJECT_NOT_FOUND_ERROR.value
                }
            )
            await idempotency_manager.update_task_status(
                execution_id=task_record.execution_id, 
                status="FAILURE", 
                result={"signal": ResponseEnum.PROJECT_NOT_FOUND_ERROR.value}
            )
            raise Exception(f"No project found for project_id: {project_id}")

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
            embedding_size=vectordb_client.default_vector_size,
            do_reset=do_reset
        )
    
        has_records = True
        page_no = 1
        inserted_items_count = 0
    
        total_chunks = await chunk_model.get_project_chunks_count(project_id=project.project_id) 
    
        while has_records:
            page_chunks = await chunk_model.get_project_chunks(project_id=project.project_id, page_no=page_no)
            
            if len(page_chunks):
                page_no += 1
                inserted_items_count += len(page_chunks)
    
                chunks_ids = [chunk.chunk_id for chunk in page_chunks]
    
                is_inserted = await nlp_controller.index_into_vector_db(
                    project=project,
                    chunks=page_chunks,
                    chunks_ids=chunks_ids
                )
                
                if not is_inserted:
                    task_instance.update_state(
                        state="FAILURE",
                        meta={
                            "signal": ResponseEnum.INSERT_INTO_VECTORDB_ERROR.value
                        }
                    )
                    raise Exception(f"Failed to insert chunks on page {page_no - 1}")   
            
            else:
                has_records = False
                
        task_instance.update_state(
            state="SUCCESS",
            meta={
                "signal": ResponseEnum.INSERT_INTO_VECTORDB_SUCCESS.value,
            }
        )
        
        await idempotency_manager.update_task_status(
            execution_id=task_record.execution_id,
            status='SUCCESS',
            result={"signal": ResponseEnum.INSERT_INTO_VECTORDB_SUCCESS.value}
        )

        return {
                "signal": ResponseEnum.INSERT_INTO_VECTORDB_SUCCESS.value,
                "inserted_items_count": inserted_items_count,
                "total_expected_chunks": total_chunks
        }

    except Exception as e:
        logger.error(f"Error occurred while processing the project: {e}")
        if task_record:
            await idempotency_manager.update_task_status(
                execution_id=task_record.execution_id, 
                status="FAILURE", 
                result={
                    "error": str(e),
                }
            )
        raise
        
    finally:
        try:
            if db_engine:
                await db_engine.dispose()
            
            if vectordb_client:
                await vectordb_client.disconnect()
        
        except Exception as e:
            logger.error(f"Task failed while cleaning: {e!s}")
            