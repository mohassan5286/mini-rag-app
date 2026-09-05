from pydantic import BaseModel


class PushRequest(BaseModel):
    do_reset: bool | None = True

class SearchRequest(BaseModel):
    text: str
    limit: int | None = 2