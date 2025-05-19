from fastapi import APIRouter

from utils.file.views import generate_signed_urls

files_router_v1 = APIRouter()

files_router_v1.add_api_route("/files/signed_urls/{sub_folder}/{sign_method}", methods=["POST"],
                              operation_id="get_signed_urls",
                              endpoint=generate_signed_urls)
