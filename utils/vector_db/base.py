from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from code_indexing.serializers import VectorSearchRequest, KeywordSearchRequest
from etl.serializers import QueryRequest


class VectorDBAdapter(ABC):
    @abstractmethod
    async def connect(self) -> None:
        pass
    
    @abstractmethod
    async def close(self) -> None:
        pass
    
    @abstractmethod
    async def create_index(self, index_name: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def delete_index(self, index_name: str) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def index_document(self, index_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def update_document_by_path(self, index_name: str, update_fields: Dict[str, Any]) -> Dict[str, Any]:
        pass

    async def get_documents_by_path(self, index_name: str, path: str, graph_id: str) -> List[Dict[str, Any]]:
        pass

    async def delete_documents_by_path(self, index_name: str, path: str, graph_id: str) -> bool:
        pass

    @abstractmethod
    async def search(self, index_name: str, query: str, size: int = 5) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def keyword_search_source_code(self, request: KeywordSearchRequest, index: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def knn_similarity_search(self, request: VectorSearchRequest, index: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def bulk_insert(self, index_name: str, documents: list[dict], mapping: dict, actions: list):
        pass

    @abstractmethod
    async def search_and_fetch_content_xml(self, request: QueryRequest, index_name: str, source_str: str) -> List[str]:
        pass

    @abstractmethod
    async def get_file_content(self, index_name: str, file_path: str, graph_id: str) -> Optional[str]:
        pass

    @abstractmethod
    async def get_folder_structure(selfself, index_name: str, graph_id: str, level: int) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def delete_documents_by_source(self, index_name: str, source_str: str) -> dict:
        pass