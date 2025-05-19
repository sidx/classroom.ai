import typing
from datetime import datetime

from fastapi import HTTPException
from pydantic import Field, BaseModel
from starlette.requests import Request


class UserData(BaseModel):
    userId: int = Field(..., alias="_id")
    orgId: int
    firstName: typing.Optional[str]
    lastName: typing.Optional[str]
    email: typing.Optional[str]
    username: typing.Optional[str]
    phoneNumber: typing.Optional[str]
    profilePicUrl: typing.Optional[str]
    active: typing.Optional[bool]
    roleIds: typing.Optional[list[int]]
    meta: typing.Optional[dict]
    createdAt: typing.Optional[datetime]
    updatedAt: typing.Optional[datetime]
    workspace: typing.List[typing.Dict]


async def get_user_data_from_request(request: Request):
    try:
        user_data: UserData = request.state.user_data
        return user_data
    except Exception as e:
        raise HTTPException(status_code=403, detail="Invalid request headers") from e
