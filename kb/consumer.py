from config.logging import logger
from config.settings import loaded_config
from kb.dao import SourceItemDao, ChunkDao, IngestionRunDao, KnowledgeBaseDao, IngestionErrorDao
from kb.factory import KnowledgeBaseFactory
from kb.models import KBState, IntegrationType
from utils.connection_handler import ConnectionHandler
from utils.vector_db import ElasticSearchAdapter
from utils.vector_db.embeddings import EmbeddingGenerator
import os
from typing import Dict, List, Any


async def knowledge_base_consumer(message):
    logger.info(f"Processing knowledge base consumer: {message}")
    connection_handler = None
    extractor = None
    transformer = None
    loader = None
    ingestion_run_dao = None
    knowledge_base_dao = None
    payload_data = None
    ingestion_error_dao = None
    try:
        payload_data = message.get('payload', {}).get('payload', {})
        logger.info(f"Payload data in consumer: {payload_data}")

        extractor, transformer, loader = get_etl(payload_data)
        connection_handler = ConnectionHandler(connection_manager=loaded_config.connection_manager)
        session = connection_handler.session
        embedder = EmbeddingGenerator(api_key=loaded_config.openai_gpt4o_api_key)
        source_item_dao = SourceItemDao(session)
        chunk_dao = ChunkDao(session)
        ingestion_run_dao = IngestionRunDao(session)
        knowledge_base_dao = KnowledgeBaseDao(session)
        ingestion_error_dao = IngestionErrorDao(session)

        extracted_data = await extractor.extract()
        folder_structure = build_folder_structure_from_paths(extracted_data)
        await knowledge_base_dao.update_memory_key_by_id(
            kb_id=int(payload_data["knowledge_base_id"]),
            key="folder_structure",
            value=folder_structure,
            commit=True
        )
        source_items, updated_extracted_data = await convert_extracted_data_to_bulk_insert(
            extracted_data,
            int(payload_data["knowledge_base_id"]),
            payload_data["mode"],
            source_item_dao, chunk_dao, ElasticSearchAdapter(), "knowledge_base_index")

        await source_item_dao.bulk_insert(source_items)

        transformed_data = await transformer.transform(updated_extracted_data, embedder, knowledge_base_id=payload_data["knowledge_base_id"])
        await chunk_dao.bulk_insert(await convert_transformed_data_to_chunks_dicts(transformed_data))

        result = await loader.load({"index_name": "knowledge_base_index", "documents": transformed_data})
        logger.info(f"Load Result: {result}")

        if payload_data["mode"] == "ADD":
            await ingestion_run_dao.update_run_summary(
                run_id=payload_data["ingestion_run_id"],
                status="completed",
                total_source_item=len(extracted_data),
                total_chunks=len(transformed_data),
                failed_chunk_elastic_doc_id=result.get("failed", [])
            )
        else:  # UPDATE mode
            # Get all source items for this knowledge base
            source_items = await source_item_dao.get_all_by_kb_id(int(payload_data["knowledge_base_id"]))
            total_source_items = len(source_items)

            # Get source item IDs
            source_item_ids = [item.id for item in source_items]

            # Get total chunks for these source items
            total_chunks = await chunk_dao.get_count_by_source_item_ids(source_item_ids)

            await ingestion_run_dao.update_run_summary(
                run_id=payload_data["ingestion_run_id"],
                status="completed",
                total_source_item=total_source_items,
                total_chunks=total_chunks,
                failed_chunk_elastic_doc_id=result.get("failed", [])
            )
        logger.info(f"Updated ingestion run summary")

        await knowledge_base_dao.update_state_by_id(payload_data["knowledge_base_id"], KBState.ready, commit=True)
        logger.info(f"Updated knowledge base state")

    except Exception as e:
        logger.error(f"Error processing knowledge base consumer: {e}")
        if ingestion_error_dao:
            await ingestion_error_dao.create_ingestion_error(
                run_id=payload_data["ingestion_run_id"],
                error_message=str(e)
            )

        await ingestion_run_dao.update_run_summary(
            run_id=payload_data["ingestion_run_id"],
            status="failed",
            total_source_item=0,
            total_chunks=0,
            failed_chunk_elastic_doc_id=[]
        ) if ingestion_run_dao else None

        if knowledge_base_dao:
            await knowledge_base_dao.update_state_by_id(payload_data["knowledge_base_id"], KBState.error if payload_data["mode"] == "ADD" else KBState.update_error, commit=True)
        await connection_handler.session.rollback()
    finally:
        await connection_handler.session.close()


async def convert_transformed_data_to_chunks_dicts(
    transformed_data: list
) -> list[dict]:
    chunks = []

    for doc in transformed_data:
        metadata = doc.get("metadata") or {}
        chunk_dict = {
            "source_item_id": doc.get("id").split("#")[0],
            "chunk_index": metadata.get("chunk_number", 1),
            "es_doc_id": doc.get("id"),
            "start_offset": metadata.get("start_line"),
            "end_offset":  metadata.get("end_line"),
            "metadata_json": metadata or {}
        }
        chunks.append(chunk_dict)

    return chunks

async def convert_extracted_data_to_bulk_insert(
    extracted_data: list[dict],
    knowledge_base_id: int,
    mode: str,
    source_item_dao: SourceItemDao,
    chunk_dao: ChunkDao,
    elastic_adapter,
    index_name: str,
) -> tuple[list[dict], list[dict]]:
    source_items = []
    updated_extracted_data = []

    # Fetch existing source items
    existing_source_items = await source_item_dao.get_all_by_kb_id(knowledge_base_id)
    existing_items_dict = {item.logical_path: item for item in existing_source_items}

    # Process files based on mode
    if mode == "ADD":
        # For "ADD" mode, directly prepare extracted data for insertion
        source_items = [prepare_source_item(record, knowledge_base_id) for record in extracted_data]
        updated_extracted_data = extracted_data

    elif mode == "UPDATE":
        # Separate extracted data into files to add, update, or delete
        files_to_add = []
        files_to_update = []
        files_to_delete = []

        # Classify extracted data
        for record in extracted_data:
            logical_path = record.get("path")
            checksum = record.get("checksum")
            existing_source_item = existing_items_dict.get(logical_path)

            if existing_source_item:
                if existing_source_item.checksum != checksum:
                    files_to_update.append(record)  # Files with checksum mismatch
            else:
                files_to_add.append(record)  # New files to be added

        # Determine files to delete (not in extracted data but in DB)
        files_to_delete = list(existing_items_dict.keys() - {record.get("path") for record in extracted_data})

        # Prepare files for bulk insert and deletion
        source_items.extend([prepare_source_item(record, knowledge_base_id) for record in files_to_add])
        updated_extracted_data.extend(files_to_add)

        # Handle file updates (delete old, insert new)
        for record in files_to_update:
            logical_path = record.get("path")
            existing_source_item = existing_items_dict[logical_path]
            await source_item_dao.delete_by_id(existing_source_item.id)
            await elastic_adapter.delete_document_by_id_prefix(index_name, f"{existing_source_item.id}#")
            source_items.append(prepare_source_item(record, knowledge_base_id))
            updated_extracted_data.append(record)

        # Handle file deletions
        for logical_path in files_to_delete:
            existing_source_item = existing_items_dict[logical_path]
            await source_item_dao.delete_by_id(existing_source_item.id)
            await elastic_adapter.delete_document_by_id_prefix(index_name, f"{existing_source_item.id}#")

    return source_items, updated_extracted_data

def prepare_source_item(record: dict, knowledge_base_id: int) -> dict:
    return {
        "kb_id": knowledge_base_id,
        "provider_item_id": record.get("provider_item_id"),
        "kind": record.get("kind"),
        "logical_path": record.get("path"),
        "version_tag": str(record.get("version_tag")),
        "checksum": record.get("checksum"),
        "metadata_json": {},
        "id": record.get('uuid')
    }

def build_folder_structure_from_paths(file_records: List[dict]) -> Dict[str, Any]:
    folder_tree = {}
    for record in file_records:
        path = record["path"]
        parts = path.split(os.sep)

        current = folder_tree
        for i, part in enumerate(parts):
            is_file = "." in part and i == len(parts) - 1
            if is_file:
                current[part] = None
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

    return folder_tree


def get_etl(payload: dict):
    provider = payload.get("provider")

    if provider == "azure_devops" or provider == "github" or provider == "gitlab":
        repo_url = payload.get("url")
        branch = payload.get("branch_name")
        pat = payload.get("pat")

        extractor = KnowledgeBaseFactory.get_extractor( provider, repo_url=repo_url, branch_name=branch, pat=pat)
        transformer = KnowledgeBaseFactory.get_transformer("repo_transformer")
        loader = KnowledgeBaseFactory.get_loader("elasticsearch", db_adapter=ElasticSearchAdapter())
        return extractor, transformer, loader

    elif provider == "quip":
        pat = payload.get("pat")
        urls = payload.get("urls", [])

        extractor = KnowledgeBaseFactory.get_extractor(provider, pat=pat, urls=urls, max_docs_per_kb=int(loaded_config.max_docs_per_kb))
        transformer = KnowledgeBaseFactory.get_transformer("quip_transformer")
        loader = KnowledgeBaseFactory.get_loader("elasticsearch", db_adapter=ElasticSearchAdapter())
        return extractor, transformer, loader

    raise ValueError(f"Unsupported provider: {provider}")