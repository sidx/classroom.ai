from typing import List, Tuple, Optional
from uuid import UUID

from fex_utilities.threads.services import ThreadService

from utils.base_view import BaseView
from utils.connection_handler import execute_read_db_operation


async def append_thread_data(threads, data):
    """
    Append thread data using a generic database operation.

    Args:
        threads (list): A list of thread information dictionaries.
        data (dict): The data structure to which thread messages will be appended.

    Returns:
        dict: The updated data with appended thread messages.
    """
    try:
        for thread in threads:
            thread_id = thread["uuid"]
            last_message_id = thread["last_message_id"]
            thread_messages = await get_current_thread_messages(thread_id=thread_id, last_message_id=last_message_id)
            # Append processed messages to data
            data["messages"] = thread_messages + data["messages"]

        return data
    except Exception as e:
        BaseView.construct_error_response(e)
        return data


async def append_thread_data_operation(connection_handler, thread_id: UUID) -> Tuple:
    """
    Operation to fetch thread messages for a specific thread ID.

    Args:
        connection_handler: The connection handler for database access.
        thread_id (str): The ID of the thread whose messages need to be fetched.

    Returns:
        List[dict]: A list of thread messages.
    """
    thread_service = ThreadService(connection_handler=connection_handler)
    thread = await thread_service.thread_dao.get_thread_by_id(thread_id)
    thread_messages = await thread_service.get_thread_messages(thread_id=thread_id)
    return thread_messages, thread


async def get_current_thread_messages(thread_id: UUID, last_message_id: Optional[int] = None, last_question_id: Optional[int] = None):
    thread_messages, thread = await execute_read_db_operation(append_thread_data_operation, thread_id)
    if last_question_id:
        latest_message_id = last_question_id
    elif last_message_id:
        latest_message_id = last_message_id
    else:
        latest_message_id = thread.last_message_id

    tree = ConversationTree()
    tree.current_conv_thread_id = thread_id
    tree.build_tree(thread_messages)

    if latest_message_id:
        path = tree.find_path_to_node(latest_message_id or 0)
        tree.process_conversation_message(path)
    else:
        tree.process_conversation_tree(0, 1)

    return tree.conv_messages


class ConversationTree:
    def __init__(self):
        self.conv_messages_tree = {}
        self.conv_messages = []
        self.current_conv_thread_id = 0

    # Python equivalent of buildTree
    def build_tree(self, messages):
        self.conv_messages_tree = dict()
        self.conv_messages_tree[0] = {"children": []}

        # First, create the structure for each message
        for message in messages:
            self.conv_messages_tree[message.id] = message.__dict__
            self.conv_messages_tree[message.id]["children"] = []

        # Then, associate each message with its parent
        for message in messages:
            parent_id = message.parent_message_id or 0
            self.conv_messages_tree[parent_id]["children"].append(self.conv_messages_tree[message.id])

    # Python equivalent of findPathToNode
    def find_path_to_node(self, target_id):
        # Helper function to recursively find the path
        def search_path(node_id, local_path):
            node = self.conv_messages_tree[node_id]  # Get the current node from the tree

            # Add current node to the path
            local_path.append(node)

            # If this is the target node, return the path
            if node.get("id") == target_id:
                return local_path

            # If the node has children, search each child recursively
            if node["children"]:
                for child in node["children"]:
                    result = search_path(child["id"], local_path.copy())  # Create a new path for each recursion
                    if result:
                        return result  # Return the found path

            # If the node is not found in this path, return None
            return None

        path = []
        path = search_path(0, path)
        self.conv_messages = []  # Resetting the conv_messages list as in the original
        return path

    def process_conversation_tree(self, current_node, first_revision):
        while current_node is not None:
            if not self.conv_messages_tree[current_node]["children"]:
                break
            message = self.conv_messages_tree[current_node]["children"][first_revision - 1]

            # Add user message to conversation messages
            self.conv_messages.append({
                "id": message["id"],
                "role": message["role"].value,
                "content": message["content"],
                "displayText": message["display_text"],
                "conversationId": self.current_conv_thread_id,
                "parentId": message["parent_message_id"],
                "isJson": message["is_json"],
                "questionConfig": message["question_config"],
                "isDisliked": message["is_disliked"],
                "prompt_details": message["prompt_details"] if "prompt_details" in message else {}
            })
            current_node = message["id"]
            first_revision = 1

    def process_conversation_message(self, conv_messages):
        for message in conv_messages:
            if 'id' not in message:
                continue
            self.conv_messages.append({
                "id": message["id"],
                "role": message["role"].value,
                "content": message["content"],
                "displayText": message["display_text"],
                "conversationId": self.current_conv_thread_id,
                "parentId": message["parent_message_id"],
                "isJson": message["is_json"],
                "questionConfig": message["question_config"],
                "isDisliked": message["is_disliked"],
                "prompt_details": message["prompt_details"] if "prompt_details" in message else {}
            })
