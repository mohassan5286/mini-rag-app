from pydantic import BaseModel
from typing import Optional

class PushRequest(BaseModel):
    do_reset: Optional[bool] = True

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 2