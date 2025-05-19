from typing import List, Dict
from uuid import uuid4

from pydantic.fields import Field
from pydantic.main import BaseModel


class ResponseData(BaseModel):
    identifier: str = Field(default_factory=lambda: str(uuid4()))
    success: bool
    message: str
    errors: List = Field(default_factory=list)
    data: List | Dict = Field(default_factory=list)

    def dict(self, *args, **kwargs):
        return super().dict(*args, **kwargs)
