from src.models.knowledge_base import IngestionMode, KnowledgeBase


def test_ingestion_mode_enum_values():
    assert IngestionMode.STANDARD.value == "standard"
    assert IngestionMode.ADVANCED.value == "advanced"


def test_knowledge_base_defaults_to_standard_ingestion_mode():
    kb = KnowledgeBase(
        name="Test KB",
        tenant_id="00000000-0000-0000-0000-000000000000",
        vector_db_provider="QDRANT",
        embedding_provider="SENTENCE_TRANSFORMERS",
        embedding_model="all-MiniLM-L6-v2",
    )
    assert kb.ingestion_mode == IngestionMode.STANDARD
