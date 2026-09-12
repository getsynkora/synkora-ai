from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.agents.internal_tools import storage_tools as tools
from src.services.security.tenant_storage import tenant_object_key


@pytest.fixture
def scope(monkeypatch):
    tenant = str(uuid4())
    store = MagicMock(bucket_name="bucket")
    store.download_file.return_value = b"own data"
    store.generate_presigned_url.return_value = "https://example.invalid/owned"
    store.get_file_metadata.return_value = {"size": 8}
    store.list_files.return_value = []
    monkeypatch.setattr(tools, "get_s3_storage", lambda: store)
    return tenant, SimpleNamespace(tenant_id=tenant), store


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        tools.internal_s3_download_file,
        tools.internal_s3_generate_presigned_url,
        tools.internal_s3_delete_file,
        tools.internal_s3_file_exists,
        tools.internal_s3_get_file_metadata,
        tools.internal_s3_list_files,
    ],
)
async def test_every_read_share_delete_and_list_rejects_foreign_scope(scope, method):
    tenant, context, store = scope
    for key in [
        f"tenants/{uuid4()}/private",
        f"data-uploads/{uuid4()}/private",
        f"s3://other/tenants/{tenant}/file",
        f"tenants/{tenant}/../victim",
        f"tenants/{tenant}%2f../victim",
        "tenants/",
        "data-uploads/",
    ]:
        result = await method(key, runtime_context=context)
        assert "error" in result
    store.assert_not_called()
    assert store.mock_calls == []
    assert "error" in await method("file")  # No trusted runtime identity.


@pytest.mark.asyncio
async def test_owned_keys_and_relative_names_work_consistently(scope):
    tenant, context, store = scope
    for key in [f"tenants/{tenant}/file", f"s3://bucket/tenants/{tenant}/file", "file"]:
        assert (await tools.internal_s3_download_file(key, runtime_context=context))["content"] == "own data"
        store.download_file.assert_called_with(f"tenants/{tenant}/file")
    assert (await tools.internal_s3_list_files(runtime_context=context))["success"]
    store.list_files.assert_called_once_with(prefix=f"tenants/{tenant}/", max_keys=1000)
    assert tenant_object_key(f"data-uploads/{tenant}/file", "bucket", tenant) == f"data-uploads/{tenant}/file"
    assert tenant_object_key(f"tenants/{tenant}", "bucket", tenant, prefix=True) == f"tenants/{tenant}/"


@pytest.mark.asyncio
async def test_uploads_cannot_overwrite_other_tenants_objects(scope, monkeypatch, tmp_path):
    tenant, context, store = scope
    monkeypatch.setattr(tools, "_get_workspace_path", lambda *args: str(tmp_path))
    path = tmp_path / "file.txt"
    path.write_text("own data")
    assert "error" in await tools.internal_s3_upload_file(str(path), f"tenants/{uuid4()}/file", runtime_context=context)
    assert "error" in await tools.internal_s3_upload_directory(
        str(tmp_path), "files", tenant_id=str(uuid4()), runtime_context=context
    )
    assert store.mock_calls == []
    store.upload_file.return_value = {
        "key": f"tenants/{tenant}/file.txt",
        "url": "s3://bucket/owned",
        "bucket": "bucket",
    }
    result = await tools.internal_s3_upload_file(str(path), runtime_context=context)
    assert result["success"]
    assert store.upload_file.call_args.kwargs["key"] == f"tenants/{tenant}/file.txt"
