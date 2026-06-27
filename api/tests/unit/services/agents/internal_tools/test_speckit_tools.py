import pytest
from unittest.mock import AsyncMock, MagicMock, patch


SPEC_CONTENT = "# My Feature\n\n## Overview\nSome overview.\n\n## User Stories\n- As a user..."
PLAN_CONTENT = "# Plan\n\n## Approaches Considered\n### Option A..."
TASKS_CONTENT = "# Tasks\n\n## TASK-001\n**Title:** Set up model\n**Dependencies:** none\n**Parallelizable:** false"


def _make_runtime_context(tenant_id="tenant-abc"):
    rc = MagicMock()
    rc.tenant_id = tenant_id
    return rc


def _make_config(tenant_id="tenant-abc"):
    return {"_runtime_context": _make_runtime_context(tenant_id)}


class TestSpeckitSpecify:
    @pytest.mark.asyncio
    async def test_uploads_to_correct_s3_key(self):
        mock_s3 = MagicMock()
        mock_s3.upload_file.return_value = {"key": "speckit/tenant-abc/FEAT-0001/spec.md", "url": "s3://bucket/speckit/tenant-abc/FEAT-0001/spec.md", "bucket": "test-bucket"}
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/speckit/tenant-abc/FEAT-0001/spec.md?sig=xxx"

        with patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_specify
            result = await internal_speckit_specify(
                feature_id="FEAT-0001",
                spec_content=SPEC_CONTENT,
                config=_make_config(),
            )

        mock_s3.upload_file.assert_called_once()
        call_kwargs = mock_s3.upload_file.call_args
        assert call_kwargs.kwargs["key"] == "speckit/tenant-abc/FEAT-0001/spec.md"
        assert call_kwargs.kwargs["content_type"] == "text/markdown"
        assert result["filename"] == "spec.md"
        assert result["feature_id"] == "FEAT-0001"
        assert "s3_url" in result
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_presigned_url_uses_7_day_expiry(self):
        mock_s3 = MagicMock()
        mock_s3.upload_file.return_value = {"key": "k", "url": "s3://b/k", "bucket": "b"}
        mock_s3.generate_presigned_url.return_value = "https://url"

        with patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_specify
            await internal_speckit_specify(
                feature_id="FEAT-0001",
                spec_content=SPEC_CONTENT,
                config=_make_config(),
            )

        mock_s3.generate_presigned_url.assert_called_once_with(
            key="speckit/tenant-abc/FEAT-0001/spec.md",
            expiration=86400 * 7,
        )

    @pytest.mark.asyncio
    async def test_missing_spec_content_returns_error(self):
        from src.services.agents.internal_tools.speckit_tools import internal_speckit_specify
        result = await internal_speckit_specify(
            feature_id="FEAT-0001",
            spec_content="",
            config=_make_config(),
        )
        assert "error" in result
        assert "spec_content" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_s3_failure_returns_content_and_flag(self):
        mock_s3 = MagicMock()
        mock_s3.upload_file.side_effect = Exception("S3 unavailable")

        with patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_specify
            result = await internal_speckit_specify(
                feature_id="FEAT-0001",
                spec_content=SPEC_CONTENT,
                config=_make_config(),
            )

        assert result["filename"] == "spec.md"
        assert result["feature_id"] == "FEAT-0001"
        assert result["content"] == SPEC_CONTENT
        assert result["storage_error"] is True
        assert "s3_url" not in result

    @pytest.mark.asyncio
    async def test_no_runtime_context_uses_unknown_tenant(self):
        mock_s3 = MagicMock()
        mock_s3.upload_file.return_value = {"key": "k", "url": "s3://b/k", "bucket": "b"}
        mock_s3.generate_presigned_url.return_value = "https://url"

        with patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_specify
            result = await internal_speckit_specify(
                feature_id="FEAT-0001",
                spec_content=SPEC_CONTENT,
                config=None,
            )

        call_kwargs = mock_s3.upload_file.call_args
        assert "unknown" in call_kwargs.kwargs["key"]
        assert "error" not in result


class TestSpeckitPlan:
    @pytest.mark.asyncio
    async def test_uploads_plan_to_correct_key(self):
        mock_s3 = MagicMock()
        mock_s3.upload_file.return_value = {"key": "speckit/tenant-abc/FEAT-0001/plan.md", "url": "s3://b/k", "bucket": "b"}
        mock_s3.generate_presigned_url.return_value = "https://plan-url"

        with patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_plan
            result = await internal_speckit_plan(
                feature_id="FEAT-0001",
                plan_content=PLAN_CONTENT,
                config=_make_config(),
            )

        call_kwargs = mock_s3.upload_file.call_args
        assert call_kwargs.kwargs["key"] == "speckit/tenant-abc/FEAT-0001/plan.md"
        assert result["filename"] == "plan.md"
        assert result["feature_id"] == "FEAT-0001"
        assert "s3_url" in result

    @pytest.mark.asyncio
    async def test_missing_plan_content_returns_error(self):
        from src.services.agents.internal_tools.speckit_tools import internal_speckit_plan
        result = await internal_speckit_plan(
            feature_id="FEAT-0001",
            plan_content="",
            config=_make_config(),
        )
        assert "error" in result


class TestSpeckitTasks:
    @pytest.mark.asyncio
    async def test_uploads_tasks_to_correct_key(self):
        mock_s3 = MagicMock()
        mock_s3.upload_file.return_value = {"key": "speckit/tenant-abc/FEAT-0001/tasks.md", "url": "s3://b/k", "bucket": "b"}
        mock_s3.generate_presigned_url.return_value = "https://tasks-url"

        with patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_tasks
            result = await internal_speckit_tasks(
                feature_id="FEAT-0001",
                tasks_content=TASKS_CONTENT,
                config=_make_config(),
            )

        call_kwargs = mock_s3.upload_file.call_args
        assert call_kwargs.kwargs["key"] == "speckit/tenant-abc/FEAT-0001/tasks.md"
        assert result["filename"] == "tasks.md"
        assert result["feature_id"] == "FEAT-0001"

    @pytest.mark.asyncio
    async def test_missing_tasks_content_returns_error(self):
        from src.services.agents.internal_tools.speckit_tools import internal_speckit_tasks
        result = await internal_speckit_tasks(
            feature_id="FEAT-0001",
            tasks_content="",
            config=_make_config(),
        )
        assert "error" in result


class TestSpeckitCommit:
    def _make_config(self, tenant_id="tenant-abc"):
        rc = MagicMock()
        rc.tenant_id = tenant_id
        return {"_runtime_context": rc}

    @pytest.mark.asyncio
    async def test_missing_repo_returns_error(self):
        from src.services.agents.internal_tools.speckit_tools import internal_speckit_commit
        result = await internal_speckit_commit(
            filename="spec.md",
            s3_key="speckit/t/FEAT-0001/spec.md",
            repo="invalid-no-slash",
            config=self._make_config(),
        )
        assert "error" in result
        assert "owner/repo" in result["error"]

    @pytest.mark.asyncio
    async def test_no_github_token_returns_error(self):
        with patch("src.services.agents.internal_tools.speckit_tools.get_github_token_from_context", new_callable=AsyncMock, return_value=None):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_commit
            result = await internal_speckit_commit(
                filename="spec.md",
                s3_key="speckit/t/FEAT-0001/spec.md",
                repo="acme/project",
                config=self._make_config(),
            )
        assert "error" in result
        assert "GitHub OAuth" in result["error"] or "OAuth" in result["error"]

    @pytest.mark.asyncio
    async def test_s3_read_failure_returns_error(self):
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = Exception("S3 down")

        with (
            patch("src.services.agents.internal_tools.speckit_tools.get_github_token_from_context", new_callable=AsyncMock, return_value="ghp_token"),
            patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3),
        ):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_commit
            result = await internal_speckit_commit(
                filename="spec.md",
                s3_key="speckit/t/FEAT-0001/spec.md",
                repo="acme/project",
                config=self._make_config(),
            )
        assert "error" in result
        assert "S3" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_commit_new_branch(self):
        mock_s3 = MagicMock()
        mock_s3.download_file.return_value = b"# Spec content"
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/spec.md"

        branch_not_found = MagicMock(status_code=404)
        repo_info = MagicMock(status_code=200)
        repo_info.json.return_value = {"default_branch": "main"}
        sha_resp = MagicMock(status_code=200)
        sha_resp.json.return_value = {"object": {"sha": "abc123"}}
        create_branch_resp = MagicMock(status_code=201)
        file_not_found = MagicMock(status_code=404)
        put_resp = MagicMock(status_code=201)
        put_resp.json.return_value = {
            "commit": {"html_url": "https://github.com/acme/project/commit/xyz"},
            "content": {"html_url": "https://github.com/acme/project/blob/specs/specs/FEAT-0001/spec.md"},
        }

        async def mock_get(url, **kwargs):
            if "git/ref/heads/specs" in url and "main" not in url:
                return branch_not_found
            if "git/ref/heads/main" in url:
                return sha_resp
            if url == "https://api.github.com/repos/acme/project":
                return repo_info
            if "contents/" in url:
                return file_not_found
            return MagicMock(status_code=200)

        async def mock_post(url, **kwargs):
            return create_branch_resp

        async def mock_put(url, **kwargs):
            return put_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get
        mock_client.post = mock_post
        mock_client.put = mock_put

        with (
            patch("src.services.agents.internal_tools.speckit_tools.get_github_token_from_context", new_callable=AsyncMock, return_value="ghp_token"),
            patch("src.services.agents.internal_tools.speckit_tools.get_s3_storage", return_value=mock_s3),
            patch("src.services.agents.internal_tools.speckit_tools.httpx.AsyncClient", return_value=mock_client),
        ):
            from src.services.agents.internal_tools.speckit_tools import internal_speckit_commit
            result = await internal_speckit_commit(
                filename="spec.md",
                s3_key="speckit/tenant-abc/FEAT-0001/spec.md",
                repo="acme/project",
                config=self._make_config(),
            )

        assert "error" not in result
        assert "commit_url" in result
        assert "file_url" in result
        assert "s3_url" in result
