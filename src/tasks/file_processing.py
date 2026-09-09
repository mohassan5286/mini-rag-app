import asyncio
import logging

from fastapi import APIRouter

from celery_app import celery_app, get_setup_utils
from controllers import (
    NLPController,
    ProcessController,
)
from models import AssetModel, ChunkModel, ProjectModel, ResponseEnum
from models.db_schemes import DataChunk
from models.enums import AssetTypeEnum
from utils.idempotency_manager import IdempotencyManager

logger = logging.getLogger(__name__)
data_router = APIRouter()

@celery_app.task(
    bind=True, 
    name="tasks.file_processing.process_project_files",
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60}
)
def process_project_files(self, project_id: int, file_id: str, chunk_size: int, overlap_size: int, do_reset: bool):
    return asyncio.run(_process_project_files(self, project_id, file_id, chunk_size, overlap_size, do_reset))

async def _process_project_files(task_instance, project_id: int, file_id: str, chunk_size: int, overlap_size: int, do_reset: bool):
    (db_engine, db_client, generation_client, embedding_client, vectordb_client, template_parser) = await get_setup_utils()

    try:
        task_record = None

        idempotency_manager = IdempotencyManager(db_client=db_client, db_engine=db_engine)
        
        task_name = "tasks.file_processing.process_project_files"
        task_args = {
            "project_id": project_id,
            "file_id": file_id,
            "chunk_size": chunk_size,
            "overlap_size": overlap_size,
            "do_reset": do_reset
        }

        should_execute, existing_task = await idempotency_manager.should_execute_task(
            task_name=task_name,
            task_args=task_args
        )

        if not should_execute:
            logger.warning(f"Can not handle the task | status: {existing_task.status}")
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

        project_model = await ProjectModel.create_instance(db_client=db_client)
        project = await project_model.get_project_or_create_one(project_id=project_id)

        nlp_controller = NLPController(
            vectordb_client=vectordb_client,
            generation_client=generation_client,
            embedding_client=embedding_client,
            template_parser=template_parser,
        )

        project_files_ids = {}
        asset_model = await AssetModel.create_instance(db_client=db_client)
        
        if file_id:
            asset_record = await asset_model.get_asset_record(asset_project_id=project.project_id, asset_name=file_id)
            if asset_record is None:
                task_instance.update_state(
                    state="FAILURE",
                    meta={
                        "signal": ResponseEnum.FILE_ID_ERROR.value,
                    }
                )

                await idempotency_manager.update_task_status(
                    execution_id=task_record.execution_id,
                    status='FAILURE',
                    result={"signal": ResponseEnum.FILE_ID_ERROR.value}
                )

                raise Exception(f"No assets for file: {file_id}")
            
            project_files_ids = {asset_record.asset_id: asset_record.asset_name}
        
        else:
            asset_records = await asset_model.get_all_assets(asset_project_id=project.project_id, asset_type=AssetTypeEnum.FILE.value)
            project_files_ids = {asset_record.asset_id: asset_record.asset_name for asset_record in asset_records}

        if not project_files_ids:
            task_instance.update_state(
                state="FAILURE",
                meta={
                    "signal": ResponseEnum.NO_FILES_ERROR.value,
                }
            )

            # Update task status to FAILURE
            await idempotency_manager.update_task_status(
                execution_id=task_record.execution_id,
                status='FAILURE',
                result={"signal": ResponseEnum.NO_FILES_ERROR.value,}
            )

            raise Exception(f"No files found for project_id: {project.project_id}")

        process_controller = ProcessController(project_id=project_id)

        no_records = 0
        no_processed_files = 0   

        chunk_model = await ChunkModel.create_instance(db_client=db_client)

        for asset_id, current_file_id in project_files_ids.items():
            file_content = process_controller.get_file_content(file_id=current_file_id)
            
            if file_content is None:
                logger.error(f"Error occurred while loading the file: {current_file_id}")
                continue

            file_chunks = process_controller.process_file_content(file_content=file_content, file_id=current_file_id, chunk_size=chunk_size, chunk_overlap=overlap_size)

            if not file_chunks:
                logger.error(f"No chunks for file_id: {current_file_id}")
                continue
            
            file_chunks_records = [
                DataChunk(
                    chunk_text = file_chunk.page_content,
                    chunk_metadata = file_chunk.metadata,
                    chunk_order = i+1,
                    chunk_project_id = project.project_id,
                    chunk_asset_id = asset_id
                )
                for i, file_chunk in enumerate(file_chunks) 
            ]

            no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records, batch_size=100)
            no_processed_files += 1

        task_instance.update_state(
            state="SUCCESS",
            meta={
                "signal": ResponseEnum.PROCESSING_SUCCESS.value,
            }
        )

        await idempotency_manager.update_task_status(
            execution_id=task_record.execution_id,
            status='SUCCESS',
            result={"signal": ResponseEnum.PROCESSING_SUCCESS.value}
        )
        
        return {
            "signal": ResponseEnum.PROCESSING_SUCCESS.value,
            "inserted_chunks": no_records,
            "processed_files": no_processed_files,
            "project_id": project_id,
            "do_reset": do_reset
        }

    except Exception as e:
        logger.error(f"Task failed: {e!s}")
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
            logger.error(f"Task failed while cleaning: {str(e)}")
