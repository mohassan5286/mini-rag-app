import logging
import os

import aiofiles
from fastapi import APIRouter, Depends, Request, UploadFile, status
from fastapi.responses import JSONResponse

from controllers import DataController, ProcessController
from helpers.config import get_settings
from models import AssetModel, ChunkModel, ProjectModel, ResponseEnum
from models.db_schemes import Asset, DataChunk
from models.enums import AssetTypeEnum

from .schema import ProcessRequest

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter()

@data_router.post("/upload/{project_id}")
async def upload_file(request: Request, project_id: str, file: UploadFile, settings=Depends(get_settings)):

    project_model = await ProjectModel.create_instance(db_client=request.app.mongodb)  
    project = await project_model.get_project_or_create_one(project_id=project_id)

    data_controller = DataController()

    is_validate, results_signal = data_controller.validate_file(file)

    if not is_validate:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"signal": results_signal}
        )

    file_path, file_id = data_controller.generate_unique_filepath(file.filename, project_id)

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)

    except Exception as e:
        logger.error(f"Error occurred while saving the file: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"signal": ResponseEnum.FILE_UPLOAD_FAILED.value}
        )

    asset_model = await AssetModel.create_instance(db_client=request.app.mongodb)
    
    asset_resource = Asset(
        asset_project_id = project.id,
        asset_type = AssetTypeEnum.FILE.value,
        asset_name = file_id,
        asset_size = os.path.getsize(file_path),
    )

    asset_record = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(
        content={"signal": ResponseEnum.FILE_UPLOAD_SUCCESS.value, "file_id": str(asset_record.id)},
    )

@data_router.post('/process/{project_id}')
async def process_endpoint(request: Request, project_id: str, process_request: ProcessRequest):
    project_model = await ProjectModel.create_instance(db_client=request.app.mongodb)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    project_files_ids = {}
    asset_model = await AssetModel.create_instance(db_client=request.app.mongodb)
    
    if file_id:
        asset_record = await asset_model.get_asset_record(asset_project_id=project.id, asset_name=file_id)
        if asset_record is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseEnum.FILE_ID_ERROR.value}
            )
        
        project_files_ids = {asset_record.id: asset_record.asset_name}

    else:
        asset_records = await asset_model.get_all_assets(asset_project_id=project.id, asset_type=AssetTypeEnum.FILE.value)
        project_files_ids = {asset_record.id: asset_record.asset_name for asset_record in asset_records}

    if not project_files_ids:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": ResponseEnum.NO_FILES_ERROR.value}
        )

    process_controller = ProcessController(project_id=project_id)

    no_records = 0
    no_processed_files = 0   

    chunk_model = await ChunkModel.create_instance(db_client=request.app.mongodb)
    if do_reset:
        await chunk_model.delete_chunks_by_project_id(project_id=project.id)

    for asset_id, file_id in project_files_ids.items():
        file_content = process_controller.get_file_content(file_id=file_id)
        
        if file_content is None:
            logger.error(f"Error occurred while loading the file: {file_id}")
            continue

        file_chunks = process_controller.process_file_content(file_content=file_content, file_id=file_id, chunk_size=chunk_size, chunk_overlap=overlap_size)

        if not file_chunks:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": ResponseEnum.PROCESSING_FAILED.value}
            )
        
        file_chunks_records = [
            DataChunk(
                chunk_text = file_chunk.page_content,
                chunk_metadata = file_chunk.metadata,
                chunk_order = i+1,
                chunk_project_id = project.id,
                chunk_asset_id = asset_id
            )

            for i, file_chunk in enumerate(file_chunks) 
        ]

        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records, batch_size=100)
        no_processed_files += 1

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseEnum.PROCESSING_SUCCESS.value,
            "no-records": no_records,
            "no-processed-files": no_processed_files
        }
    )
