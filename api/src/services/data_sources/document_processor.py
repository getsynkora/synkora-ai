"""Document processor for data sources."""

import json
import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.data_source import DataSource, DataSourceDocument
from src.models.document import Document, DocumentStatus
from src.models.knowledge_base import KnowledgeBase
from src.services.document.image_extractor import ImageExtractor
from src.services.knowledge_base.embedding_service import EmbeddingService
from src.services.knowledge_base.providers.vector_db_factory import VectorDBProviderFactory
from src.services.knowledge_base.text_processor import TextProcessor
from src.services.storage.s3_storage import S3StorageService

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Process documents from data sources and store in knowledge base."""

    def __init__(self, db: AsyncSession):
        """Initialize document processor."""
        self.db = db
        self.text_processor = TextProcessor()
        self.s3_storage = S3StorageService()
        self.image_extractor = ImageExtractor(s3_service=self.s3_storage)
        # embedding_service will be created per knowledge base with its config
        self.embedding_service = None

    async def process_documents(self, data_source: DataSource, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Process documents and store in knowledge base.

        Args:
            data_source: Data source instance
            documents: List of documents to process

        Returns:
            Processing result dictionary
        """
        if not data_source.knowledge_base_id:
            logger.warning(
                f"Data source {data_source.name} is not linked to a knowledge base. "
                "Documents will be stored but not embedded."
            )
            return await self._store_documents_only(data_source, documents)

        # Get knowledge base
        result = await self.db.execute(select(KnowledgeBase).filter(KnowledgeBase.id == data_source.knowledge_base_id))
        kb = result.scalar_one_or_none()

        if not kb:
            logger.error(f"Knowledge base {data_source.knowledge_base_id} not found")
            return {"success": False, "error": "Knowledge base not found", "documents_processed": 0}

        return await self._process_and_embed(data_source, kb, documents)

    async def _store_documents_only(self, data_source: DataSource, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """Store documents without embedding."""
        stored_count = 0

        for doc in documents:
            try:
                # Check if document already exists
                result = await self.db.execute(
                    select(DataSourceDocument).filter(
                        DataSourceDocument.data_source_id == data_source.id,
                        DataSourceDocument.external_id == doc["id"],
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing document
                    existing.content = doc["text"]
                    existing.doc_metadata = doc.get("metadata", {})
                else:
                    # Create new document
                    ds_doc = DataSourceDocument(
                        data_source_id=data_source.id,
                        tenant_id=data_source.tenant_id,
                        external_id=doc["id"],
                        external_url=doc.get("metadata", {}).get("url"),
                        title=doc.get("metadata", {}).get("title"),
                        content=doc["text"],
                        content_type="text",
                        doc_metadata=doc.get("metadata", {}),
                        is_embedded=False,
                    )
                    self.db.add(ds_doc)

                stored_count += 1

            except Exception as e:
                logger.error(f"Error storing document {doc.get('id')}: {e}")
                continue

        await self.db.commit()

        return {"success": True, "documents_processed": stored_count, "documents_embedded": 0}

    async def _process_and_embed(
        self, data_source: DataSource, kb: KnowledgeBase, documents: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Process documents and store with embeddings."""
        try:
            # Initialize embedding service with KB's configuration
            # The embedding_config property automatically decrypts the API key
            embedding_config = kb.get_embedding_config_decrypted()
            logger.info(
                f"Initializing embedding service with provider: {kb.embedding_provider.value}, model: {kb.embedding_model}"
            )
            logger.debug(f"Embedding config keys: {list(embedding_config.keys())}")

            self.embedding_service = EmbeddingService(
                provider=kb.embedding_provider.value, model_name=kb.embedding_model, config=embedding_config
            )

            # Initialize vector DB provider
            from src.models.knowledge_base import VectorDBProvider

            # Convert string to enum if needed
            if isinstance(kb.vector_db_provider, str):
                provider_enum = VectorDBProvider(kb.vector_db_provider)
            else:
                provider_enum = kb.vector_db_provider

            # Get decrypted vector DB config
            vector_db_config = kb.get_vector_db_config_decrypted()

            vector_db = VectorDBProviderFactory.create(provider_type=provider_enum, config=vector_db_config)
            vector_db.connect()

            # Get collection/index name from vector_db_config
            # For Pinecone, this should be the index_name specified in the UI
            collection_name = (
                kb.vector_db_config.get("index_name") or kb.vector_db_config.get("collection_name") or f"kb-{kb.id}"
            )
            logger.info(f"Using collection/index name: '{collection_name}'")
            logger.info(f"Checking if collection '{collection_name}' exists...")

            exists = vector_db.collection_exists(collection_name)
            logger.info(f"Collection exists check result: {exists}")

            if not exists:
                # Get embedding dimension
                logger.info("Getting embedding dimension...")
                dimension = self.embedding_service.get_embedding_dimension()
                logger.info(f"Embedding dimension: {dimension}")

                logger.info(f"Creating collection '{collection_name}'...")
                vector_db.create_collection(
                    collection_name=collection_name, dimension=dimension, distance_metric="cosine"
                )
                logger.info(f"Created collection {collection_name} with dimension {dimension}")
            else:
                logger.info(f"Collection '{collection_name}' already exists, skipping creation")

            documents_processed = 0
            total_chunks = 0

            logger.info(f"Starting to process {len(documents)} documents...")

            for idx, doc in enumerate(documents):
                logger.info(f"Processing document {idx + 1}/{len(documents)}: {doc.get('id')}")
                try:
                    # Store document in data_source_documents
                    result = await self.db.execute(
                        select(DataSourceDocument).filter(
                            DataSourceDocument.data_source_id == data_source.id,
                            DataSourceDocument.external_id == doc["id"],
                        )
                    )
                    existing_ds_doc = result.scalar_one_or_none()

                    if existing_ds_doc:
                        ds_doc = existing_ds_doc
                        ds_doc.content = doc["text"]
                        ds_doc.doc_metadata = doc.get("metadata", {})
                    else:
                        ds_doc = DataSourceDocument(
                            data_source_id=data_source.id,
                            tenant_id=data_source.tenant_id,
                            external_id=doc["id"],
                            external_url=doc.get("metadata", {}).get("url"),
                            title=doc.get("metadata", {}).get("title"),
                            content=doc["text"],
                            content_type="text",
                            doc_metadata=doc.get("metadata", {}),
                            is_embedded=False,
                        )
                        self.db.add(ds_doc)

                    await self.db.flush()  # Get the ID

                    # Extract images if document has S3 URL and is a supported format
                    if ds_doc.external_url and ds_doc.external_url.startswith("s3://"):
                        await self._extract_and_store_images(ds_doc, kb)

                    # Chunk the text using configured strategy
                    logger.info(
                        f"Chunking text for document {doc['id']} (length: {len(doc['text'])} chars) using strategy: {kb.chunking_strategy.value}..."
                    )
                    chunks = self.text_processor.chunk_text(
                        text=doc["text"],
                        chunk_size=kb.chunk_size,
                        chunk_overlap=kb.chunk_overlap,
                        strategy=kb.chunking_strategy,
                        min_chunk_size=kb.min_chunk_size,
                        max_chunk_size=kb.max_chunk_size,
                        chunking_config=kb.chunking_config,
                        metadata=doc.get("metadata", {}),
                    )
                    logger.info(f"Generated {len(chunks)} chunks")

                    if not chunks:
                        logger.warning(f"No chunks generated for document {doc['id']}")
                        continue

                    # Extract chunk texts for embedding
                    chunk_texts = [chunk["text"] for chunk in chunks]

                    # Generate embeddings
                    logger.info(f"Generating embeddings for {len(chunk_texts)} chunks...")
                    embeddings = self.embedding_service.embed_texts(chunk_texts)
                    logger.info(f"Generated {len(embeddings)} embeddings")

                    # Generate document name from metadata or use external_id
                    doc_metadata = doc.get("metadata", {})
                    doc_name = (
                        doc_metadata.get("title")
                        or doc_metadata.get("channel_name")
                        or doc_metadata.get("subject")
                        or f"{data_source.name} - {doc['id']}"
                    )

                    # Upsert document: reuse stub created during upload if present
                    existing_kb_doc = None
                    existing_result = await self.db.execute(
                        select(Document).filter(
                            Document.knowledge_base_id == kb.id,
                            Document.external_id == doc["id"],
                        )
                    )
                    existing_kb_doc = existing_result.scalar_one_or_none()

                    if existing_kb_doc:
                        kb_doc = existing_kb_doc
                        kb_doc.data_source_id = data_source.id
                        kb_doc.name = doc_name
                        kb_doc.content = doc["text"]
                        kb_doc.word_count = len(doc["text"].split())
                        kb_doc.char_count = len(doc["text"])
                        kb_doc.has_images = doc_metadata.get("has_images", False)
                        kb_doc.image_count = doc_metadata.get("image_count", 0)
                        kb_doc.images = doc_metadata.get("images")
                        kb_doc.s3_url = doc_metadata.get("s3_url") or kb_doc.s3_url
                        kb_doc.file_size = doc_metadata.get("file_size") or kb_doc.file_size
                        kb_doc.mime_type = doc_metadata.get("mime_type") or kb_doc.mime_type
                        kb_doc.doc_metadata = doc_metadata
                    else:
                        # Create a new document record
                        kb_doc = Document(
                            tenant_id=data_source.tenant_id,
                            knowledge_base_id=kb.id,
                            data_source_id=data_source.id,
                            name=doc_name,
                            external_id=doc["id"],
                            external_url=doc_metadata.get("url"),
                            source_type=data_source.type.value,
                            content=doc["text"],
                            content_type="text",
                            doc_metadata=doc_metadata,
                            word_count=len(doc["text"].split()),
                            char_count=len(doc["text"]),
                            has_images=doc_metadata.get("has_images", False),
                            image_count=doc_metadata.get("image_count", 0),
                            images=doc_metadata.get("images"),
                            s3_url=doc_metadata.get("s3_url"),
                            file_size=doc_metadata.get("file_size"),
                            mime_type=doc_metadata.get("mime_type"),
                            original_filename=doc_metadata.get("original_filename"),
                            upload_source=doc_metadata.get("upload_source", "data_source"),
                        )
                        self.db.add(kb_doc)
                    await self.db.flush()  # Ensure kb_doc.id is available

                    # Import DocumentSegment model
                    from src.models.document_segment import DocumentSegment

                    # Prepare vectors for storage
                    vectors = []
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
                        chunk_text = chunk["text"]
                        chunk.get("metadata", {})

                        # Create DocumentSegment for each chunk
                        # dataset_id is nullable - we can get data source from document relationship
                        segment = DocumentSegment(
                            tenant_id=data_source.tenant_id,
                            dataset_id=None,  # Not using datasets in our simplified model
                            document_id=kb_doc.id,
                            position=i,
                            content=chunk_text,
                            word_count=len(chunk_text.split()),
                            tokens=len(chunk_text) // 4,  # Rough estimate
                            index_node_id=f"kb-{kb.id}-doc-{kb_doc.id}-seg-{i}",
                            index_node_hash=f"hash-{kb_doc.id}-{i}",
                            created_by=data_source.tenant_id,  # Use tenant_id as created_by
                        )
                        self.db.add(segment)
                        await self.db.flush()  # Get segment ID

                        # Prepare vector metadata
                        # Filter out None/null values from metadata for Pinecone
                        # Convert UUIDs to strings for Pinecone compatibility
                        metadata = {
                            "knowledge_base_id": kb.id,
                            "document_id": str(kb_doc.id),  # Convert UUID to string
                            "segment_id": str(segment.id),  # Add segment ID
                            "data_source_id": data_source.id,
                            "external_id": doc["id"],
                            "chunk_index": i,
                            "text": chunk_text,
                        }
                        # Add doc metadata, filtering out None values
                        for key, value in doc.get("metadata", {}).items():
                            if value is not None:
                                metadata[key] = value

                        # Check metadata size for Pinecone
                        if kb.vector_db_provider == VectorDBProvider.PINECONE:
                            metadata_json = json.dumps(metadata)
                            metadata_size = len(metadata_json.encode("utf-8"))

                            if metadata_size > 40960:  # 40KB limit
                                logger.warning("Metadata exceeds Pinecone limit!")
                                logger.warning(f"   Size: {metadata_size} bytes ({metadata_size / 1024:.2f} KB)")
                                logger.warning(f"   Document: {doc['id']}, Chunk: {i}")
                                logger.warning("   Metadata keys and sizes:")

                                # Log size of each field
                                for key, value in metadata.items():
                                    field_size = len(json.dumps({key: value}).encode("utf-8"))
                                    logger.warning(f"     - {key}: {field_size} bytes ({field_size / 1024:.2f} KB)")
                                    if field_size > 5000:  # Log large fields
                                        value_preview = str(value)[:200] if len(str(value)) > 200 else str(value)
                                        logger.warning(f"       Preview: {value_preview}...")

                                # Log the full metadata structure (keys only, not values)
                                logger.warning("   Full metadata structure:")
                                logger.warning(
                                    f"   {json.dumps({k: f'<{type(v).__name__}>' for k, v in metadata.items()}, indent=2)}"
                                )

                        vectors.append({"id": segment.index_node_id, "vector": embedding, "payload": metadata})

                    # Store vectors in vector DB with KB ID as namespace (for Pinecone)
                    namespace = str(kb.id)  # Use KB ID as namespace for multi-tenancy
                    vector_ids = vector_db.add_vectors(
                        collection_name=collection_name, vectors=vectors, namespace=namespace
                    )
                    logger.info(f"Stored {len(vector_ids)} vectors for document {doc['id']} in namespace {namespace}")

                    # Mark as embedded
                    ds_doc.is_embedded = True
                    ds_doc.embedding_id = vector_ids[0] if vector_ids else None

                    # Mark the KB document as fully processed
                    kb_doc.status = DocumentStatus.COMPLETED

                    # Commit after each document to avoid database locks
                    await self.db.commit()

                    documents_processed += 1
                    total_chunks += len(chunk_texts)

                    logger.info(
                        f"Completed document {idx + 1}/{len(documents)} - Total processed: {documents_processed}, Total chunks: {total_chunks}"
                    )

                except Exception as e:
                    logger.error(f"Error processing document {doc.get('id')}: {e}", exc_info=True)
                    await self.db.rollback()  # Rollback on error
                    # Refresh both kb and data_source — rollback expires all tracked objects,
                    # and accessing expired column attributes outside a greenlet_spawn context
                    # raises MissingGreenlet in SQLAlchemy async.
                    await self.db.refresh(kb)
                    await self.db.refresh(data_source)

                    # Mark the stub document as ERROR so the UI doesn't show it stuck
                    # as "Processing" forever. Do this in a new mini-transaction so the
                    # rollback above doesn't undo it.
                    try:
                        err_result = await self.db.execute(
                            select(Document).filter(
                                Document.knowledge_base_id == kb.id,
                                Document.external_id == doc["id"],
                            )
                        )
                        err_doc = err_result.scalar_one_or_none()
                        if err_doc and err_doc.status != DocumentStatus.COMPLETED:
                            err_doc.status = DocumentStatus.ERROR
                            err_doc.doc_metadata = {
                                **(err_doc.doc_metadata or {}),
                                "error": str(e)[:500],
                            }
                            await self.db.commit()
                    except Exception as mark_err:
                        logger.warning(f"Could not mark document as ERROR: {mark_err}")
                        await self.db.rollback()

                    continue

            # Update knowledge base stats
            logger.info("Updating knowledge base stats...")
            result = await self.db.execute(
                select(func.count()).select_from(Document).filter(Document.knowledge_base_id == kb.id)
            )
            kb.total_documents = result.scalar_one()
            kb.total_chunks = total_chunks
            logger.info(f"KB stats: {kb.total_documents} documents, {total_chunks} chunks")

            logger.info("Committing to database...")
            await self.db.commit()
            logger.info("Database commit successful")

            logger.info("Disconnecting from vector DB...")
            vector_db.disconnect()
            logger.info("Vector DB disconnected")

            logger.info(
                f"Processed {documents_processed} documents, "
                f"generated {total_chunks} chunks for knowledge base {kb.name}"
            )

            return {
                "success": True,
                "documents_processed": documents_processed,
                "documents_embedded": documents_processed,
                "total_chunks": total_chunks,
            }

        except Exception as e:
            logger.error(f"Error in document processing: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e), "documents_processed": 0}

    async def _extract_and_store_images(self, ds_doc: DataSourceDocument, kb: KnowledgeBase) -> None:
        """
        Extract images from document and store in S3.

        Args:
            ds_doc: Data source document instance
            kb: Knowledge base instance
        """
        try:
            # Check if document type supports image extraction
            supported_types = ["pdf", "docx", "html"]
            content_type = ds_doc.content_type.lower()

            if content_type not in supported_types:
                logger.debug(f"Document type {content_type} does not support image extraction")
                return

            # Download document from S3
            logger.info(f"Downloading document from S3: {ds_doc.external_url}")
            file_content = await self.s3_storage.download_file_content(ds_doc.external_url)

            # Extract images
            logger.info(f"Extracting images from document {ds_doc.external_id}")
            images = await self.image_extractor.extract_images(file_content=file_content, file_type=content_type)

            if not images:
                logger.info(f"No images found in document {ds_doc.external_id}")
                return

            logger.info(f"Found {len(images)} images in document {ds_doc.external_id}")

            # Upload images to S3 and collect metadata
            image_metadata = []
            for idx, image_data in enumerate(images):
                try:
                    # Generate S3 key for image
                    s3_key = f"knowledge-bases/kb-{kb.id}/documents/doc-{ds_doc.id}/images/image_{idx + 1}.{image_data['format'].lower()}"

                    # Upload image to S3
                    logger.info(f"Uploading image {idx + 1}/{len(images)} to S3: {s3_key}")
                    s3_url = await self.s3_storage.upload_file_content(
                        file_content=image_data["data"],
                        key=s3_key,
                        content_type=f"image/{image_data['format'].lower()}",
                        metadata={
                            "document_id": str(ds_doc.id),
                            "knowledge_base_id": str(kb.id),
                            "image_index": str(idx),
                        },
                    )

                    # Add image metadata
                    image_metadata.append(
                        {
                            "index": idx + 1,
                            "page": image_data.get("page"),
                            "s3_url": s3_url,
                            "s3_key": s3_key,
                            "width": image_data["width"],
                            "height": image_data["height"],
                            "format": image_data["format"],
                            "size_bytes": len(image_data["data"]),
                        }
                    )

                    logger.info(f"Uploaded image {idx + 1}/{len(images)}")

                except Exception as e:
                    logger.error(f"Error uploading image {idx + 1}: {e}")
                    continue

            # Update document with image metadata
            if image_metadata:
                ds_doc.doc_metadata = ds_doc.doc_metadata or {}
                ds_doc.doc_metadata["has_images"] = True
                ds_doc.doc_metadata["image_count"] = len(image_metadata)
                ds_doc.doc_metadata["images"] = image_metadata

                logger.info(f"Stored metadata for {len(image_metadata)} images in document {ds_doc.external_id}")

        except Exception as e:
            logger.error(f"Error extracting images from document {ds_doc.external_id}: {e}", exc_info=True)
            # Don't fail the entire document processing if image extraction fails
