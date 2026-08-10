import asyncio

from fastapi import APIRouter, Request, status
from .schema.nlp import PushRequest, SearchRequest
from controllers import NLPController
from models import ProjectModel, ChunkModel
from models.enums.ResponseEnums import ResponseEnums
from fastapi.responses import JSONResponse
from tqdm import tqdm

nlp_router = APIRouter()


@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: int, push_request: PushRequest):
    project_model = await ProjectModel.create_instance(request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    chunk_model = await ChunkModel.create_instance(request.app.db_client)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    collection_name = nlp_controller.create_collection_name(project_id=project.project_id)
    _ = await request.app.vectordb_client.create_collection(collection_name = collection_name, embedding_size=request.app.embedding_client.embedding_size, do_reset=push_request.do_reset)

    has_records = True
    page_no = 1
    inserted_items_count = 0
    idx = 0

    chunks_count = await chunk_model.get_project_chunks_count(project_id=project.project_id) 

    pbar = tqdm(total=chunks_count, desc="Indexing chunks", position=0)

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
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "signal": ResponseEnums.ERROR.value
                    }
                )
        else:
            has_records = False

        pbar.update(len(page_chunks))
        
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseEnums.SUCCESS.value,
            "inserted_items_count": inserted_items_count
        }
    )

@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: int):
    project_model = await ProjectModel.create_instance(request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)

    if collection_info:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "signal": ResponseEnums.SUCCESS.value,
                "collection_info": collection_info
            }
        )

    else:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseEnums.ERROR.value
            }
        )
    

@nlp_router.post("/index/search/{project_id}")
async def search_index(request: Request, project_id: int, search_request: SearchRequest):
    project_model = await ProjectModel.create_instance(request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    results = await nlp_controller.search_vector_db_collection(
        project=project, text=search_request.text, limit=search_request.limit
    )

    if not results:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseEnums.ERROR.value
                }
            )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseEnums.SUCCESS.value,
            "results": [result.model_dump() for result in results]
        }
    )

@nlp_router.post("/index/answer/{project_id}")
async def answer_rag(request: Request, project_id: int, search_request: SearchRequest):
    project_model = await ProjectModel.create_instance(request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    nlp_controller = NLPController(
        vectordb_client=request.app.vectordb_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    answer, full_prompt, chat_history = await nlp_controller.answer_rag_question(
        project=project, query=search_request.text, limit=search_request.limit
    )

    if not answer:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseEnums.ERROR.value
                }
            )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "signal": ResponseEnums.SUCCESS.value,
            "answer": answer,
            "full_prompt": full_prompt,
            "chat_history": chat_history
        }
    )

