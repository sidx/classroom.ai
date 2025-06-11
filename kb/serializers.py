from pydantic.class_validators import root_validator
from pydantic.main import BaseModel
from typing import Optional, Dict, List, Any

from kb.models import IntegrationType

class UpdateKB(BaseModel):
    kb_id: int
    name: Optional[str] = None
    pat: Optional[str] = None
    url: Optional[str] = None
    branch_name: Optional[str] = None

class GetKbRequest(BaseModel):
    search_term: Optional[str] = None  # search in kb name and source_identifier
    team_ids: List[Optional[str]] = None
    org_ids: List[Optional[str]] = None
    page: int = 1
    size: int = 10
    state: Optional[str] = None


class ShareKnowledgeBaseRequest(BaseModel):
    kb_ids: List[int]
    team_id: Optional[List[str]] = []
    user_id: Optional[List[str]] = []
    org_id: Optional[List[str]] = []

class LocalFileContext(BaseModel):
    kb_id: Optional[str] = ""
    path: str
    content: str
    provider: IntegrationType
    kb_name: Optional[str] = None

class ProviderContext(BaseModel):
    kb_id: str
    provider: IntegrationType
    credentials: Optional[Dict[str, Any]] = None
    kb_name: Optional[str] = None
    is_updatable: Optional[bool] = False

    @root_validator(pre=True)
    def clean_github_url(cls, values):
        provider = values.get("provider")
        credentials = values.get("credentials", {})
        if not credentials:
            return values

        if provider == IntegrationType.github.value or provider == IntegrationType.gitlab.value:
            url = credentials.get("url")
            if isinstance(url, str) and url.endswith(".git"):
                credentials["url"] = url[:-4]  # Remove ".git"
                values["credentials"] = credentials

        return values

class KnowledgeBaseRequest(BaseModel):
    add_context_through_local_files: Optional[LocalFileContext] = None
    add_context_through_provider: Optional[ProviderContext] = None
    team_id: Optional[str] = None
    context: str   # "add_context_through_provider" or "add_context_through_local_files"

class GetKBStatusRequest(BaseModel):
    team_id: Optional[str] = None
    kb_ids: Optional[List[int]] = None

class DeleteKnowledgeBasesRequest(BaseModel):
    kb_ids: List[int]

class GetVectorSearchRequest(BaseModel):
    query: str
    knowledge_base_id: list[int]
    matching_percentage: float
    top_answer_count: int
    team_id: Optional[str] = ""
    user_id: Optional[str] = ""
    org_id: Optional[str] = ""