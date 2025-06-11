from datetime import datetime

from fastapi import HTTPException, status
from starlette.requests import Request

from config.logging import logger
from config.settings import loaded_config
from utils.exceptions import SessionExpiredException
from clerk_integration.utils import UserData


async def get_user_data_from_request(request: Request):
    try:
        # user_data: UserData = await loaded_config.clerk_auth_helper.get_user_data_from_clerk(request)
        # return user_data
        return UserData(
            _id="user_2wD66rW2AmhN3RmnBgBei12129j", # user_2wD66rW2AmhN3RmnBgBei12129j user_2wAfohyRcJAYvyHN9iwoWMsniHP
            orgId="org_2wM6P0x3exs5fK4VVX4VY2EtqYA", # org_2wM6P0x3exs5fK4VVX4VY2EtqYA
            firstName="John",
            lastName="Doe",
            email="john.doe@example.com",
            username="johndoe",
            phoneNumber="1234567890",
            profilePicUrl="https://example.com/profile.jpg",
            active=True,
            roleIds=[1, 2],
            meta={"key": "value"},
            createdAt=datetime.now(),
            updatedAt=datetime.now(),
            workspace=[]
        )
    except Exception as e:
        try:
            user_data: UserData = request.state.user_data
            return user_data
        except Exception as e:
            logger.error("Invalid request headers: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": SessionExpiredException.DEFAULT_MESSAGE,
                    "message": str(e),
                    "code": SessionExpiredException.ERROR_CODE
                }
            ) from e
