from config.settings import loaded_config
from utils.file.constants import SignMethod, sign_method_signed_url_expiry_mapping


class FileService:

    def __init__(self):
        self.cloud_storage_util = loaded_config.cloud_storage_util

    def generate_signed_urls(self, sub_folder: str, sign_method: SignMethod, filenames: list[str]):
        resource_urls = self.get_resource_urls(sub_folder=sub_folder, filenames=filenames)
        expiration_time = sign_method_signed_url_expiry_mapping.get(sign_method)
        signed_urls = self.cloud_storage_util.generate_signed_urls(
            resource_urls=resource_urls,
            expiration_time=expiration_time,
            sign_method=sign_method
        )
        return {filename: signed_url for filename, signed_url in zip(filenames, signed_urls)}

    def get_resource_urls(self, sub_folder: str, filenames: list[str]):
        return [
            self.cloud_storage_util.get_file_path(
                filename=filename,
                sub_path=f"{sub_folder}/original"
            )
            for filename in filenames
        ]
