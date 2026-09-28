"""Unit tests for TypeSafe triage in ClickUp, Intercom, and Zoho CRM tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.issue_triage import MIN_ISSUES_TO_TRIAGE


class TestClickUpTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_result(self):
        """triage key present in search result."""
        # Raw ClickUp API task format — _make_clickup_request returns {"tasks": [...]};
        # internal_search_clickup_tasks formats these with task["status"]["status"]
        tasks = [
            {
                "id": f"task{i}",
                "name": f"Task {i}",
                "description": "",
                "status": {"status": "open"},
                "priority": None,
                "url": f"https://cu/{i}",
                "assignees": [],
                "tags": [],
            }
            for i in range(MIN_ISSUES_TO_TRIAGE - 1)
        ]

        with patch(
            "src.services.agents.internal_tools.clickup_tools._get_clickup_token",
            AsyncMock(return_value="token"),
        ), patch(
            "src.services.agents.internal_tools.clickup_tools._make_clickup_request",
            AsyncMock(return_value={"tasks": tasks}),
        ), patch(
            "src.services.agents.internal_tools.clickup_tools._get_typesafe_client",
            AsyncMock(return_value=None),
        ):
            from src.services.agents.internal_tools.clickup_tools import internal_search_clickup_tasks

            result = await internal_search_clickup_tasks(
                list_id="list1", query="bug", runtime_context=MagicMock()
            )

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False


class TestIntercomTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_result(self):
        """triage key present in conversations result."""
        # _make_intercom_request returns raw Intercom API data; _format_conversation is applied
        raw_convs = [
            {
                "id": f"conv{i}",
                "title": f"Conversation {i}",
                "state": "open",
                "open": True,
                "created_at": 0,
                "updated_at": 0,
            }
            for i in range(MIN_ISSUES_TO_TRIAGE - 1)
        ]

        with patch(
            "src.services.agents.internal_tools.intercom_tools._get_intercom_credentials",
            AsyncMock(return_value={"access_token": "token"}),
        ), patch(
            "src.services.agents.internal_tools.intercom_tools._make_intercom_request",
            AsyncMock(return_value={"conversations": raw_convs, "total_count": len(raw_convs)}),
        ), patch(
            "src.services.agents.internal_tools.intercom_tools._get_typesafe_client",
            AsyncMock(return_value=None),
        ):
            from src.services.agents.internal_tools.intercom_tools import internal_list_intercom_conversations

            result = await internal_list_intercom_conversations(runtime_context=MagicMock())

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False


class TestZohoCRMTriage:
    @pytest.mark.asyncio
    async def test_search_triage_note_in_result(self):
        """triage key present in search result."""
        # Provide raw Zoho CRM record format — _format_record will be applied on these
        raw_records = [
            {
                "id": f"rec{i}",
                "Full_Name": f"Record {i}",
                "Email": f"r{i}@example.com",
                "Phone": None,
                "Owner": None,
                "Created_Time": None,
                "Modified_Time": None,
            }
            for i in range(MIN_ISSUES_TO_TRIAGE - 1)
        ]

        with patch(
            "src.services.agents.internal_tools.zoho_crm_tools._get_zoho_crm_credentials",
            AsyncMock(
                return_value={"access_token": "tok", "api_domain": "https://www.zohoapis.com"}
            ),
        ), patch(
            "src.services.agents.internal_tools.zoho_crm_tools._make_zoho_request",
            AsyncMock(return_value={"data": raw_records}),
        ), patch(
            "src.services.agents.internal_tools.zoho_crm_tools._get_typesafe_client",
            AsyncMock(return_value=None),
        ):
            from src.services.agents.internal_tools.zoho_crm_tools import internal_search_zoho_crm_records

            result = await internal_search_zoho_crm_records(
                module="Leads", query="acme", runtime_context=MagicMock()
            )

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False

    @pytest.mark.asyncio
    async def test_list_triage_note_in_result(self):
        """triage key present in list result."""
        raw_records = [
            {
                "id": f"rec{i}",
                "Full_Name": f"Record {i}",
                "Email": None,
                "Phone": None,
                "Owner": None,
                "Created_Time": None,
                "Modified_Time": None,
            }
            for i in range(MIN_ISSUES_TO_TRIAGE - 1)
        ]

        with patch(
            "src.services.agents.internal_tools.zoho_crm_tools._get_zoho_crm_credentials",
            AsyncMock(
                return_value={"access_token": "tok", "api_domain": "https://www.zohoapis.com"}
            ),
        ), patch(
            "src.services.agents.internal_tools.zoho_crm_tools._make_zoho_request",
            AsyncMock(return_value={"data": raw_records}),
        ), patch(
            "src.services.agents.internal_tools.zoho_crm_tools._get_typesafe_client",
            AsyncMock(return_value=None),
        ):
            from src.services.agents.internal_tools.zoho_crm_tools import internal_list_zoho_crm_records

            result = await internal_list_zoho_crm_records(module="Contacts", runtime_context=MagicMock())

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False
