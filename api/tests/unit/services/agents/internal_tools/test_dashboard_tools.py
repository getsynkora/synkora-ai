from unittest.mock import MagicMock, patch

import pytest

SAMPLE_DATA = [
    {"region": "North", "revenue": 12000},
    {"region": "South", "revenue": 8500},
]
SAMPLE_SECTIONS = [
    {"type": "kpi_row", "kpis": [{"label": "Revenue", "column": "revenue", "agg": "sum"}]},
    {"type": "chart", "chart_type": "bar", "title": "By Region", "x": "region", "y": "revenue"},
]


@pytest.fixture
def mock_s3():
    with patch("src.services.agents.internal_tools.dashboard_tools.get_s3_storage") as mock_get:
        s3 = MagicMock()
        s3.upload_file.return_value = {"key": "dashboards/t1/abc.html"}
        s3.generate_presigned_url.return_value = "https://example.com/presigned?sig=abc"
        s3.public_endpoint_url = None
        s3.internal_endpoint_url = "http://localhost:9000"
        s3.bucket_name = "synkora"
        mock_get.return_value = s3
        yield s3


class TestInternalGenerateDashboard:
    @pytest.mark.asyncio
    async def test_presigned_url_returned(self, mock_s3):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        result = await internal_generate_dashboard(
            title="Sales Report",
            sections=SAMPLE_SECTIONS,
            data=SAMPLE_DATA,
            config={"tenant_id": "t1"},
        )
        assert result["success"] is True
        assert result["url"] == "https://example.com/presigned?sig=abc"
        assert "expires_at" in result
        assert result["visibility"] == "presigned"
        mock_s3.upload_file.assert_called_once()
        mock_s3.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_presigned_expiry_is_7_days(self, mock_s3):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        await internal_generate_dashboard(
            title="Sales", sections=SAMPLE_SECTIONS, data=SAMPLE_DATA, config={"tenant_id": "t1"}
        )
        call_kwargs = mock_s3.generate_presigned_url.call_args
        assert call_kwargs.kwargs.get("expiration") == 604800

    @pytest.mark.asyncio
    async def test_public_url_uses_endpoint_and_bucket(self, mock_s3):
        mock_s3.public_endpoint_url = "https://public.minio.example.com"
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        result = await internal_generate_dashboard(
            title="Public",
            sections=SAMPLE_SECTIONS,
            data=SAMPLE_DATA,
            visibility="public",
            config={"tenant_id": "t1"},
        )
        assert result["success"] is True
        assert "public.minio.example.com" in result["url"]
        assert "synkora" in result["url"]
        assert result["visibility"] == "public"
        # generate_presigned_url should NOT be called for public
        mock_s3.generate_presigned_url.assert_not_called()

    @pytest.mark.asyncio
    async def test_s3_key_includes_tenant_and_html(self, mock_s3):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        await internal_generate_dashboard(
            title="T", sections=SAMPLE_SECTIONS, data=SAMPLE_DATA, config={"tenant_id": "my-tenant"}
        )
        key = mock_s3.upload_file.call_args.kwargs["key"]
        assert "dashboards/my-tenant/" in key
        assert key.endswith(".html")

    @pytest.mark.asyncio
    async def test_content_type_is_text_html(self, mock_s3):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        await internal_generate_dashboard(
            title="T", sections=SAMPLE_SECTIONS, data=SAMPLE_DATA, config={"tenant_id": "t1"}
        )
        ct = mock_s3.upload_file.call_args.kwargs["content_type"]
        assert ct == "text/html"

    @pytest.mark.asyncio
    async def test_empty_title_returns_error(self):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        result = await internal_generate_dashboard(title="", sections=SAMPLE_SECTIONS, data=SAMPLE_DATA)
        assert result["success"] is False
        assert "title" in result["error"]

    @pytest.mark.asyncio
    async def test_whitespace_only_title_returns_error(self):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        result = await internal_generate_dashboard(title="   ", sections=SAMPLE_SECTIONS, data=SAMPLE_DATA)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_empty_sections_returns_error(self):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        result = await internal_generate_dashboard(title="X", sections=[], data=SAMPLE_DATA)
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_invalid_visibility_returns_error(self):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        result = await internal_generate_dashboard(
            title="X", sections=SAMPLE_SECTIONS, data=SAMPLE_DATA, visibility="secret"
        )
        assert result["success"] is False
        assert "visibility" in result["error"]

    @pytest.mark.asyncio
    async def test_s3_upload_failure_returns_error(self, mock_s3):
        mock_s3.upload_file.side_effect = Exception("Connection refused")
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        result = await internal_generate_dashboard(
            title="Sales", sections=SAMPLE_SECTIONS, data=SAMPLE_DATA, config={"tenant_id": "t1"}
        )
        assert result["success"] is False
        assert "Upload failed" in result["error"]

    @pytest.mark.asyncio
    async def test_renderer_warnings_included_in_result(self, mock_s3):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        sections_with_unknown = SAMPLE_SECTIONS + [{"type": "unknown_section"}]
        result = await internal_generate_dashboard(
            title="W", sections=sections_with_unknown, data=SAMPLE_DATA, config={"tenant_id": "t1"}
        )
        assert result["success"] is True
        assert "warnings" in result
        assert any("unknown_section" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_data_exceeds_row_limit_returns_error(self):
        from src.services.agents.internal_tools.dashboard_tools import (
            internal_generate_dashboard,
        )

        large_data = [{"x": i} for i in range(50_001)]
        result = await internal_generate_dashboard(title="X", sections=SAMPLE_SECTIONS, data=large_data)
        assert result["success"] is False
        assert "50" in result["error"]  # mentions the limit
