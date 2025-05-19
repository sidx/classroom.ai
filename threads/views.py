import uuid

from fastapi import Depends, Path, Query
from fex_utilities.threads.serializers import CreateThreadRequest, CreateMessageRequest
from fex_utilities.threads.services import ThreadService

from threads.serializers import ThreadQueryParams
from threads.utils import get_current_thread_messages
from utils.base_view import BaseView
from utils.common import UserData, UserDataHandler
from utils.connection_handler import ConnectionHandler, get_connection_handler_for_app, \
    get_read_connection_handler_for_app
from threads.services import ThreadOwnershipService

THREAD_UUID_DESCRIPTION = "Thread UUID for which we are performing action"


# Common function to check thread ownership
async def check_thread_ownership(
    thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
    user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
    connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
):
    ownership_service = ThreadOwnershipService(connection_handler)
    return await ownership_service.check_ownership(thread_id, user_data)



class ThreadView(BaseView):
    SUCCESS_MESSAGE_THREAD_CREATED = "New Chat Thread Created!"
    SUCCESS_MESSAGE_THREAD_MESSAGE = "Thread message created successfully."
    ERROR_CODE_GET_THREADS = 4001
    ERROR_CODE_GET_MESSAGES = 7001

    QUERY_DESCRIPTION_USER_EMAIL = "The email of the user to filter projects by"
    QUERY_DESCRIPTION_PRODUCT = "The fynix product to filter the threads"

    # V1 API Methods
    @classmethod
    async def post_v1(
            cls,
            create_thread_request: CreateThreadRequest,
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            data = await cls._create_thread(thread_service, create_thread_request)
            await connection_handler.session.commit()
            return cls.construct_success_response(data=data, message=cls.SUCCESS_MESSAGE_THREAD_CREATED)
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def delete_v1(
            cls,
            thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            await cls._soft_delete_thread(thread_service, thread_id)
            await connection_handler.session.commit()
            return cls.construct_success_response(data={'thread_uuid': thread_id})
        except Exception as e:
            await connection_handler.session.rollback()
            return cls.construct_error_response(e)

    @classmethod
    async def get_v1(
            cls,
            user_email: str = Query(description=QUERY_DESCRIPTION_USER_EMAIL),
            product: str = Query(description=QUERY_DESCRIPTION_PRODUCT),
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            chat_threads = await cls._list_threads_by_email(thread_service, user_email, product)
            return cls.construct_success_response(data={'threads': chat_threads})
        except Exception as exp:
            return cls.construct_error_response(exp, code=cls.ERROR_CODE_GET_THREADS)

    # V2 API Methods
    @classmethod
    async def post_v2(
            cls,
            create_thread_request: CreateThreadRequest,
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=create_thread_request.requested_by)
        try:
            thread_service = cls._get_thread_service(connection_handler)
            data = await cls._create_thread(thread_service, create_thread_request)
            await connection_handler.session.commit()
            return cls.construct_success_response(data=data, message=cls.SUCCESS_MESSAGE_THREAD_CREATED)
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def delete_v2(
            cls,
            thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app),
            thread: object = Depends(check_thread_ownership)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            await cls._soft_delete_thread(thread_service, thread_id)
            await connection_handler.session.commit()
            return cls.construct_success_response(data={'thread_uuid': thread_id})
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)


    @classmethod
    async def get_v2(
            cls,
            thread_query_params: ThreadQueryParams = Depends(),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app)
    ):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=thread_query_params.user_email)
        try:
            thread_service = cls._get_thread_service(connection_handler)
            chat_threads = await cls._fetch_threads(thread_service, thread_query_params)
            return cls.construct_success_response(data={'threads': chat_threads.get("threads", [])})
        except Exception as exp:
            return cls.construct_error_response(exp)

    @classmethod
    async def get_v3(
            cls,
            thread_query_params: ThreadQueryParams = Depends(),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app)
    ):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=thread_query_params.user_email)
        try:
            thread_service = cls._get_thread_service(connection_handler)
            chat_threads = await cls._fetch_threads(thread_service, thread_query_params)
            return cls.construct_success_response(data=chat_threads)
        except Exception as exp:
            return cls.construct_error_response(exp)

    @staticmethod
    async def _fetch_threads(thread_service, thread_query_params):
        return await thread_service.get_threads_with_pagination(
            query=thread_query_params.search,
            user_email=thread_query_params.user_email,
            product=thread_query_params.product,
            page=thread_query_params.page,
            page_size=thread_query_params.page_size
        )

    # Static Methods
    @staticmethod
    def _get_thread_service(connection_handler):
        return ThreadService(connection_handler=connection_handler)

    @staticmethod
    async def _create_thread(thread_service, create_thread_request):
        return await thread_service.create_thread(create_thread_request=create_thread_request)

    @staticmethod
    async def _soft_delete_thread(thread_service, thread_id):
        await thread_service.soft_delete_thread(thread_id)

    @staticmethod
    async def _list_threads_by_email(thread_service, user_email, product):
        return await thread_service.list_threads_by_email(user_email, product=product)

class ThreadMessageView(BaseView):
    # V1 API Methods
    @classmethod
    async def post_v1(
            cls,
            create_message_request: CreateMessageRequest,
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            thread_message = await cls._create_thread_message(thread_service, create_message_request)
            await connection_handler.session.commit()
            await cls._update_thread_last_message(thread_service, create_message_request.thread_id, thread_message.id)
            await connection_handler.session.commit()
            return cls.construct_success_response(data={'thread_message': thread_message})
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def put_v1(
            cls,
            update_message_request: CreateMessageRequest,
            thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            thread_message = await cls._update_thread_message(thread_service, thread_id, update_message_request)
            await connection_handler.session.commit()
            return cls.construct_success_response(data={'thread_message': thread_message})
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def get_v1(
            cls,
            thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            thread_messages = await cls._get_thread_messages(thread_service, thread_id)
            return cls.construct_success_response(data={'thread_messages': thread_messages})
        except Exception as exp:
            return cls.construct_error_response(exp, code=cls.ERROR_CODE_GET_MESSAGES)

    @classmethod
    async def search_messages_v1(
            cls,
            query: str,
            email: str,
            product: str,
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app)
    ):
        try:
            thread_service = cls._get_thread_service(connection_handler)
            threads = await cls._search_thread_by_content(thread_service, query, email, product)
            return cls.construct_success_response(data={'threads': threads})
        except Exception as exp:
            return cls.construct_error_response(exp)

    # V2 API Methods
    @classmethod
    async def post_v2(
            cls,
            create_message_request: CreateMessageRequest,
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=create_message_request.requested_by)
        try:
            thread_service = cls._get_thread_service(connection_handler)
            thread_message = await cls._create_thread_message(thread_service, create_message_request)
            await connection_handler.session.commit()
            await cls._update_thread_last_message(thread_service, create_message_request.thread_id, thread_message.id)
            await connection_handler.session.commit()
            return cls.construct_success_response(data={'thread_message': thread_message})
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def put_v2(
            cls,
            update_message_request: CreateMessageRequest,
            thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_connection_handler_for_app)
    ):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=update_message_request.requested_by)
        try:
            thread_service = cls._get_thread_service(connection_handler)
            thread_message = await cls._update_thread_message(thread_service, thread_id, update_message_request)
            await connection_handler.session.commit()
            return cls.construct_success_response(data={'thread_message': thread_message})
        except Exception as exp:
            await connection_handler.session.rollback()
            return cls.construct_error_response(exp)

    @classmethod
    async def get_v2(
            cls,
            thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
            thread: object = Depends(check_thread_ownership),
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app),
            last_message_id: int = None
    ):
        try:
            if last_message_id:
                thread_messages = await get_current_thread_messages(thread_id=thread_id, last_message_id=last_message_id)
                for index, message in enumerate(thread_messages):
                    thread_messages[index] = {
                        "id": message["id"],
                        "role": message["role"],
                        "content": message["content"],
                        "display_text": message["displayText"],
                        "thread_uuid": thread_id,
                        "parent_message_id": message["parentId"],
                        "is_json": message["isJson"],
                        "question_config": message["questionConfig"],
                        "is_disliked": message["isDisliked"],
                        "prompt_details": message["prompt_details"] if "prompt_details" in message else {}
                    }
            else:
                thread_service = ThreadService(connection_handler=connection_handler)
                thread_messages = await thread_service.get_thread_messages(thread_id)

            return cls.construct_success_response(data={'thread_messages': thread_messages})
        except Exception as exp:
            return cls.construct_error_response(exp)

    @classmethod
    async def get_v3(
            cls,
            thread_id: uuid.UUID = Path(description=THREAD_UUID_DESCRIPTION),
            thread: object = Depends(check_thread_ownership),
            last_message_id: int = None
    ):
        try:
            thread_messages = await get_current_thread_messages(thread_id=thread_id,
                                                                last_message_id=last_message_id)
            for index, message in enumerate(thread_messages):
                thread_messages[index] = {
                    "id": message["id"],
                    "role": message["role"],
                    "content": message["content"],
                    "display_text": message["displayText"],
                    "thread_uuid": thread_id,
                    "parent_message_id": message["parentId"],
                    "is_json": message["isJson"],
                    "question_config": message["questionConfig"],
                    "is_disliked": message["isDisliked"],
                    "prompt_details": message["prompt_details"] if "prompt_details" in message else {}
                }

            return cls.construct_success_response(data={'thread_messages': thread_messages})
        except Exception as exp:
            return cls.construct_error_response(exp)

    @classmethod
    async def search_messages_v2(
            cls,
            query: str,
            email: str,
            product: str,
            user_data: UserData = Depends(UserDataHandler.get_user_data_from_request),
            connection_handler: ConnectionHandler = Depends(get_read_connection_handler_for_app)
    ):
        UserDataHandler.validate_email_match(user_email=user_data.email, requested_by=email)
        try:
            thread_service = cls._get_thread_service(connection_handler)
            threads = await cls._search_thread_by_content(thread_service, query, email, product)
            return cls.construct_success_response(data={'threads': threads})
        except Exception as exp:
            return cls.construct_error_response(exp)

    # Static Methods
    @staticmethod
    def _get_thread_service(connection_handler):
        return ThreadService(connection_handler=connection_handler)

    @staticmethod
    async def _create_thread_message(thread_service, create_message_request):
        return await thread_service.create_thread_message(
            create_message_request=create_message_request,
            user_email=create_message_request.requested_by,
        )

    @staticmethod
    async def _update_thread_last_message(thread_service, thread_id, last_message_id):
        await thread_service.thread_dao.update_thread(thread_id, {"last_message_id": last_message_id})

    @staticmethod
    async def _update_thread_message(thread_service, thread_id, update_message_request):
        return await thread_service.update_thread_message(
            thread_id=thread_id,
            update_message_request=update_message_request
        )

    @staticmethod
    async def _get_thread_messages(thread_service, thread_id):
        return await thread_service.get_thread_messages(thread_id=thread_id)

    @staticmethod
    async def _search_thread_by_content(thread_service, query, email, product):
        return await thread_service.search_thread_by_content(query, email, product)
