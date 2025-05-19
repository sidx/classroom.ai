import uuid

from fastapi import HTTPException
from fex_utilities.threads.services import ThreadService
from fex_utilities.threads.dao import ThreadMessageSummaryDao

from utils.common import UserData
from utils.connection_handler import ConnectionHandler


class ThreadOwnershipService:
    def __init__(self, connection_handler: ConnectionHandler):
        self.thread_service = ThreadService(connection_handler=connection_handler)

    async def check_ownership(self, thread_id: uuid.UUID, user_data: UserData):
        if not user_data:
            raise HTTPException(status_code=403, detail="Unauthorized access to this thread.")

        thread = await self.thread_service.thread_dao.get_thread_by_id(thread_id)

        if not thread or not self._is_user_authorized(thread, user_data):
            raise HTTPException(status_code=403, detail="Unauthorized access to this thread.")

        return thread

    @staticmethod
    def _is_user_authorized(thread, user_data):
        return thread.user_email == user_data.email


class ThreadMessageSummaryService:
    def __init__(self, connection_handler: ConnectionHandler):
        self.summary_dao = ThreadMessageSummaryDao(session=connection_handler.session)

    async def save_summary(self, thread_id, thread_message_id, summary: str):
        await self.summary_dao.create_summary(
            thread_uuid=thread_id, thread_message_id=thread_message_id, summary_text=summary
        )



