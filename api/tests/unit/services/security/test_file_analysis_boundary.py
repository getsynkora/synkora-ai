from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.services.agents.internal_tools.file_analysis_tools import (
    _query_local_dataset,
    _run_duckdb_query,
    _validate_query,
)


def test_real_duckdb_reads_only_staged_dataset(tmp_path):
    pytest.importorskip("duckdb")
    allowed = tmp_path / "dataset.csv"
    allowed.write_text("amount\n10\n20\n")
    private = tmp_path / "private.csv"
    private.write_text("secret\nsynthetic-private-marker\n")
    url = "s3://bucket/tenants/test/data.csv"
    query = f"SELECT SUM(amount) AS total FROM read_csv_auto('{url}')"
    assert _query_local_dataset(query, url, str(allowed)).iloc[0]["total"] == 30
    for query in [
        f"SELECT * FROM read_csv_auto('{private}')",
        "SELECT * FROM read_csv_auto('http://127.0.0.1/private')",
        "SET enable_external_access=true; SELECT 1",
        "INSTALL httpfs",
        "SELECT 1; SELECT 2",
    ]:
        with pytest.raises(Exception):
            _query_local_dataset(query, url, str(allowed))
    assert _validate_query(f"SELECT 1 /* read_csv_auto('{url}') */", url) is not None


@pytest.mark.asyncio
async def test_other_tenant_or_bucket_rejected_before_storage_access(monkeypatch):
    tenant = uuid4()
    storage = SimpleNamespace(bucket_name="bucket", s3_client=MagicMock())
    monkeypatch.setattr("src.services.storage.s3_storage.get_s3_storage", lambda: storage)
    for url in [
        f"s3://bucket/tenants/{uuid4()}/private.csv",
        f"s3://other/tenants/{tenant}/data.csv",
        f"s3://bucket/data-uploads/{tenant}-other/data.csv",
    ]:
        with pytest.raises(ValueError, match="current tenant"):
            await _run_duckdb_query("SELECT 1", url, tenant)
    storage.s3_client.get_object.assert_not_called()
