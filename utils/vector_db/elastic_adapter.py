from elasticsearch import AsyncElasticsearch
from typing import Any, Dict, List, Optional
import asyncio

from code_indexing.serializers import VectorSearchRequest, KeywordSearchRequest
from etl.serializers import QueryRequest
from .base import VectorDBAdapter
from .embeddings import EmbeddingGenerator
from .exceptions import ConnectionError, SearchError
from config.settings import loaded_config
from elasticsearch.helpers import async_bulk
import os

class ElasticSearchAdapter(VectorDBAdapter):
    """Elasticsearch adapter for vector search operations."""

    INDEXING_DEFAULT_MAPPING ={
        "settings": {
            "number_of_shards": 3,
            "number_of_replicas": 1
        },
        "mappings": {
            "properties": {
                "description_vector": {
                    "type": "dense_vector",
                    "dims": 1536,
                    "index": True,
                    "similarity": "cosine"
                },
                "description": {"type": "text"},
                "source_code": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
                "path": {"type": "keyword"},
                "type": {"type": "keyword"},
                "graph_id": {"type": "keyword"},
                "created_by": {"type": "keyword"},
                "start_line": {"type": "integer"},
                "end_line": {"type": "integer"}
            }
        }
    }

    def __init__(self):
        self.client = None
        self.embedding_generator = EmbeddingGenerator(api_key=loaded_config.openai_gpt4o_api_key)

    async def connect(self, retries=3, delay=2) -> None:
        """Connect to Elasticsearch with retries."""
        for attempt in range(retries):
            try:
                self.client = AsyncElasticsearch(hosts=[loaded_config.elastic_search_url])
                await self.client.info()
                return
            except Exception as e:
                if attempt < retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise ConnectionError(f"Failed to connect to Elasticsearch: {str(e)}")

    async def close(self) -> None:
        if self.client:
            await self.client.close()

    async def create_index(self, index_name: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            if await self.client.indices.exists(index=index_name):
                print(f"⚠️ Index '{index_name}' already exists. Skipping creation.")
                return {"acknowledged": False, "message": "Index already exists"}

            return await self.client.indices.create(index=index_name, body=settings or self.INDEXING_DEFAULT_MAPPING)
        except Exception as e:
            raise SearchError(f"Failed to create index: {str(e)}")

    async def delete_index(self, index_name: str) -> Dict[str, Any]:
        try:
            return await self.client.indices.delete(index=index_name)
        except Exception as e:
            raise SearchError(f"Failed to delete index: {str(e)}")

    async def index_document(self, index_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Generate vector embedding asynchronously
            source_text = document.get("source_code", "")
            document["description_vector"] = await asyncio.to_thread(
                self.embedding_generator.generate_embedding, source_text
            )

            return await self.client.index(index=index_name, document=document)
        except Exception as e:
            raise SearchError(f"Failed to index document: {str(e)}")

    async def update_document_by_path(self, index_name: str, update_fields: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # Search for the document with the given file_path and graph_id
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"path": update_fields["path"]}},
                            {"term": {"graph_id": update_fields["graph_id"]}}
                        ]
                    }
                }
            }
            search_result = await self.client.search(index=index_name, body=query)

            if not search_result["hits"]["hits"]:
                return await self.index_document(index_name, update_fields)

            doc_id = search_result["hits"]["hits"][0]["_id"]

            # If source_code is in the update fields, generate a new vector embedding
            if "source_code" in update_fields:
                update_fields["description_vector"] = await self.embedding_generator.generate_embedding(update_fields["source_code"])

            # Update the document with new fields
            return await self.client.update(index=index_name, id=doc_id, body={"doc": update_fields})
        except Exception as e:
            raise SearchError(f"Failed to update document: {str(e)}")

    async def get_documents_by_path(self, index_name: str, path: str, graph_id: str) -> List[Dict[str, Any]]:
        try:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"prefix": {"path": path}},
                            {"term": {"graph_id": graph_id}}
                        ]
                    }
                }
            }
            search_result = await self.client.search(index=index_name, body=query, size=1000)  # Fetch up to 1000 results
            return search_result["hits"]["hits"]
        except Exception as e:
            raise SearchError(f"Failed to fetch documents: {str(e)}")

    async def delete_documents_by_path(self, index_name: str, path: str, graph_id: str) -> bool:
        try:
            documents = await self.get_documents_by_path(index_name, path, graph_id)
            if not documents:
                return False  # No matching documents found

            for doc in documents:
                await self.client.delete(index=index_name, id=doc["_id"])

            return True
        except Exception as e:
            raise SearchError(f"Failed to delete documents: {str(e)}")


    async def search(self, index_name: str, query: str, size: int = 5) -> Dict[str, Any]:
        query_vector = await self.embedding_generator.generate_embedding(query)
        search_query = {
            "size": size,
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'description_vector') + 1.0",
                        "params": {"query_vector": query_vector}
                    }
                }
            }
        }
        try:
            return await self.client.search(index=index_name, body=search_query)
        except Exception as e:
            raise SearchError(f"Failed to perform search: {str(e)}")

    async def keyword_search_source_code(self, request: KeywordSearchRequest, index: str) -> Dict[str, Any]:
        """
        Perform keyword-based search in Elasticsearch, filtering by graph_id and optional file/folder paths.
        Returns the top `max_results` results by default.
        """
        try:
            # If entire_workspace is False and both file_paths & folder_paths are empty, return an empty response
            if not request.entire_workspace and not request.file_paths and not request.folder_paths:
                return {"hits": {"total": 0, "hits": []}}

            # Create `should` clauses for matching keywords in "source_code"
            should_clauses = [{"match": {"source_code": keyword}} for keyword in request.keywords]

            # Construct the Elasticsearch query
            query = {
                "query": {
                    "bool": {
                        "should": should_clauses,
                        "minimum_should_match": 1,  # At least one keyword must match
                        "filter": [{"term": {"graph_id": request.graph_id}}],  # Exact match for graph_id
                    }
                },
                "size": request.max_results  # Return top `max_results` results
            }

            # Apply path-based filtering
            path_filters = []

            if not request.entire_workspace:
                if request.file_paths:
                    path_filters.append({"terms": {"path": request.file_paths}})  # Match any file path

                if request.folder_paths:
                    folder_conditions = [{"wildcard": {"path": folder_path + "*"}} for folder_path in
                                         request.folder_paths]
                    path_filters.append({"bool": {"should": folder_conditions}})

            # Add filters to the query
            if path_filters:
                query["query"]["bool"]["filter"].append({"bool": {"should": path_filters}})

            # Execute the search query
            response = await self.client.search(index=index, body=query)
            return response

        except Exception as e:
            raise SearchError(f"Failed to perform keyword search: {str(e)}")

    async def knn_similarity_search(self, request: VectorSearchRequest, index: str) -> Dict[str, Any]:
        """
        Perform a KNN similarity search with filtering for specific files, folders, or the entire workspace.
        """
        try:
            # If entire_workspace is False and both file_paths & folder_paths are empty, return an empty response
            if not request.entire_workspace and not request.file_paths and not request.folder_paths:
                return {"hits": {"total": 0, "hits": []}}

            # Generate query vector asynchronously
            query_vector = await asyncio.to_thread(self.embedding_generator.generate_embedding, request.query)

            # Dynamically set num_candidates based on max_results
            if request.max_results <= 10:
                num_candidates = request.max_results * 10
            elif request.max_results <= 25:
                num_candidates = request.max_results * 5
            else:
                num_candidates = max(100, request.max_results * 3)

            # Base search body
            body = {
                "size": request.max_results,
                "knn": {
                    "field": "description_vector",
                    "query_vector": query_vector,
                    "k": request.max_results,
                    "num_candidates": num_candidates,
                    "filter": [{"term": {"graph_id": request.graph_id}}]
                }
            }

            # Apply path-based filtering
            path_filters = []

            if not request.entire_workspace:
                if request.file_paths:
                    path_filters.append({"terms": {"path": request.file_paths}})  # Match any file path

                if request.folder_paths:
                    path_filters.extend(
                        [{"wildcard": {"path": folder_path + "*"}} for folder_path in request.folder_paths])

            # Add filters to the query
            if path_filters:
                body["knn"]["filter"].append({"bool": {"should": path_filters}})

            # Perform the search
            return await self.client.search(index=index, body=body)

        except Exception as e:
            raise SearchError(f"Failed to perform KNN similarity search: {str(e)}")

    async def bulk_insert(self, index_name: str, documents: list[dict], mapping: dict, actions: list):
        """Ensures index exists and inserts multiple documents into Elasticsearch using async bulk API."""

        await self.create_index(index_name=index_name, settings=mapping)

        # Perform bulk indexing asynchronously
        success, failed = await async_bulk(self.client, actions, raise_on_error=False)
        print(f"Bulk insert completed: {success} succeeded, {failed} failed")

        # Extract failed _id values
        failed_ids = [failure['index']['_id'] for failure in failed if 'index' in failure]
        print(f"Failed _ids: {failed_ids}")

        return {"success": success, "failed": failed_ids}

    async def search_and_fetch_content_xml(self, request: QueryRequest, index_name: str, source_str: str) -> List[dict]:
        """
        Perform a search query on Elasticsearch and return the entire document,
        sorted in descending order based on the matching score, with a filter based on `matching_percentage`.
        """
        try:
            # Generate query embedding
            query_vector = await asyncio.to_thread(self.embedding_generator.generate_embedding, request.query)

            if len(query_vector) != 1536:
                raise ValueError(f"Query vector has incorrect dimensions: {len(query_vector)} (Expected: 1536)")

            # Convert the user-defined matching percentage to a similarity threshold (range between 0 and 1)
            score_threshold = request.matching_percentage / 100.0  # Match percentage between 0 and 1

            # Build the search query
            search_query = {
                "size": request.top_answer_count,
                "min_score": score_threshold,
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"source": source_str}}
                        ],
                        "should": [
                            {
                                "script_score": {
                                    "query": {"match_all": {}},
                                    "script": {
                                        "source": """
                                            double cosineSim = cosineSimilarity(params.query_vector, 'embedding');
                                            return cosineSim >= params.threshold ? cosineSim : 0;
                                        """,
                                        "params": {
                                            "query_vector": query_vector,
                                            "threshold": score_threshold
                                        }
                                    }
                                }
                            }
                        ]
                    }
                },
                "_source": ["content_xml"],
                "stored_fields": ["_score"]
            }


            # Execute search
            response = await self.client.search(index=index_name, body=search_query)

            # Debugging: Print response if needed
            print(response)

            # Extract and return the entire document
            # results = [hit["_source"] for hit in response["hits"]["hits"]]
            results = []
            for hit in response["hits"]["hits"]:
                result = hit["_source"]
                result["_score"] = hit["_score"]  # Attach the similarity score
                results.append(result)
            return results

        except Exception as e:
            print(e)
            raise SearchError(f"Failed to perform search and fetch content: {str(e)}")

    async def delete_documents_by_source(self, index_name: str, source_str: str) -> dict:
        """
        Deletes all documents in the given Elasticsearch index where the `source` matches `source_str`.
        """
        try:
            # Elasticsearch delete-by-query request
            delete_query = {
                "query": {
                    "term": {"source": source_str}
                }
            }

            # Execute delete-by-query operation
            response = await self.client.delete_by_query(index=index_name, body=delete_query)

            # Debugging: Print response if needed
            print(response)

            return response

        except Exception as e:
            print(e)
            raise SearchError(f"Failed to delete documents: {str(e)}")


    async def get_file_content(self, index_name: str, file_path: str, graph_id: str) -> Optional[str]:
        try:

            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"path": file_path}},
                            {"term": {"graph_id": graph_id}},
                            {"term": {"type": "file"}}
                        ]
                    }
                },
                "_source": ["source_code"]
            }

            response = await self.client.search(index=index_name, body=query)

            if response['hits']['total']['value'] > 0:
                document = response['hits']['hits'][0]
                return document['_source'].get('source_code', None)
            else:
                return None
        except Exception as e:
            print(f"Error retrieving file content: {e}")
            return None

    async def get_folder_structure(self, index_name: str, graph_id: str, level: int = None) -> Dict[str, Any]:
        """
        Fetches folder structure for a given graph_id from Elasticsearch.
        """
        try:
            query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"graph_id": graph_id}},
                            {"term": {"type": "file"}}
                        ]
                    }
                },
                "_source": ["path"],
                "size": 10000  # Adjust based on expected file count
            }

            response = await self.client.search(index=index_name, body=query)

            if response["hits"]["total"]["value"] == 0:
                return {"success": False, "message": "No files found for this graph_id"}

            files = [hit["_source"]["path"] for hit in response["hits"]["hits"]]
            folder_tree = self._build_folder_structure(files, level)

            return {"success": True, "data": folder_tree}

        except Exception as e:
            return {"success": False, "error": str(e)}


    def _build_folder_structure(self, file_paths: List[str], level: int = None) -> Dict[str, Any]:
        """
        Builds a hierarchical folder structure from absolute file paths.

        - `level=None`: Return full depth.
        - `level=0`: Only top-level folders/files.
        - `level=1`: Include first level of subfolders.
        """
        folder_tree = {}

        # Extract common base path
        common_prefix = os.path.commonpath(file_paths)

        for file_path in file_paths:
            # Convert absolute to relative path
            rel_path = os.path.relpath(file_path, common_prefix)
            parts = rel_path.split(os.sep)

            # Limit depth based on level
            if level is not None and len(parts) > level + 1:
                parts = parts[: level + 1]  # Trim the path to the required depth

            current = folder_tree
            for i, part in enumerate(parts):
                # If it's the last part and it's a file, store it directly
                if i == len(parts) - 1 and "." in part:
                    current[part] = file_path  # Store the full path for files
                else:
                    # If it's a folder, ensure it exists
                    if part not in current:
                        current[part] = {}
                    current = current[part]

        return folder_tree
