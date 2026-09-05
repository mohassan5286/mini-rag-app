import os

import aiofiles
from fastapi import APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse

from helpers.config import get_settings
from controllers import DataController, ProjectController, ProcessController, NLPController
from models.db_schemes import Asset
from models.enums import AssetTypeEnum
from .schema import ProcessRequest
from models import AssetModel, ResponseEnums

from models import ProjectModel, ChunkModel
from models.db_schemes import DataChunk

from tasks.file_processing import process_project_files

import logging


logger = logging.getLogger("uvicorn.error")

data_router = APIRouter()

@data_router.post("/upload/{project_id}")
async def upload_file(
    request: Request, project_id: int, file: UploadFile, settings=Depends(get_settings)
):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)  
    project = await project_model.get_project_or_create_one(project_id=project_id)

    data_controller = DataController()

    is_validate, results_signal = data_controller.validate_file(file)

    if not is_validate:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"signal": results_signal}
        )

    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    file_path, file_id = data_controller.generate_unique_filepath(file.filename, project_id)

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)

    except Exception as e:
        logger.error(f"Error occurred while saving the file: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"signal": results_signal}
        )

    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    
    asset_resource = Asset(
        asset_project_id = project.project_id,
        asset_type = AssetTypeEnum.FILE.value,
        asset_name = file_id,
        asset_size = os.path.getsize(file_path),
    )

    asset_record = await asset_model.create_asset(asset=asset_resource)

    return JSONResponse(
        content={"signal": results_signal, "file_id": str(asset_record.asset_id)},
    )


@data_router.post('/process/{project_id}')
async def process_endpoint(request: Request, project_id: int, process_request: ProcessRequest):
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    task = process_project_files.delay(
        project_id=project_id,
        file_id=file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseEnums.SUCCESS.value,
            "task_id": task.id
        }
    )

@data_router.post("/process-and-push/{project_id}")
async def process_and_push_endpoint(request: Request, project_id: int, process_request: ProcessRequest):
    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    task = process_project_files.delay(
        project_id=project_id,
        file_id=file_id,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        do_reset=do_reset,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseEnums.SUCCESS.value,
            "task_id": task.id
        }
    )
