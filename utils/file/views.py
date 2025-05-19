from fastapi import Body
from utils.file.constants import SignMethod
from utils.file.services import FileService
from utils.serializers import ResponseData


def generate_signed_urls(sub_folder: str, sign_method: SignMethod, filenames: list[str] = Body(embed=True)):
    response_data = ResponseData.construct(success=False)
    file_service = FileService()
    response = file_service.generate_signed_urls(
        sub_folder=sub_folder,
        sign_method=sign_method,
        filenames=filenames
    )
    response_data.success = True
    response_data.data = response
    return response_data.dict()

