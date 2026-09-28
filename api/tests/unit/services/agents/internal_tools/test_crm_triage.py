"""Unit tests for TypeSafe triage in Freshdesk, HubSpot, and Salesforce tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.agents.internal_tools.issue_triage import MIN_ISSUES_TO_TRIAGE


def _make_raw_freshdesk_tickets(n: int) -> list[dict]:
    """Raw Freshdesk API response format (what _make_freshdesk_request returns)."""
    return [
        {
            "id": i,
            "subject": f"Ticket {i}",
            "description_text": f"Description {i}",
            "status": 2,
            "priority": 1,
            "tags": [],
            "created_at": None,
            "updated_at": None,
            "requester_id": None,
            "responder_id": None,
        }
        for i in range(n)
    ]


def _make_raw_hubspot_tickets(n: int) -> list[dict]:
    """Raw HubSpot API response format (what _make_hubspot_request returns inside 'results')."""
    return [
        {
            "id": str(i),
            "properties": {
                "subject": f"Issue {i}",
                "content": f"Content {i}",
                "hs_pipeline_stage": "1",
                "hs_ticket_priority": "MEDIUM",
                "createdate": None,
                "hs_lastmodifieddate": None,
            },
        }
        for i in range(n)
    ]


def _make_raw_salesforce_records(n: int) -> list[dict]:
    """Raw Salesforce SOQL record format (what _soql returns)."""
    return [
        {
            "Id": f"case{i}",
            "CaseNumber": f"0000{i}",
            "Subject": f"Case {i}",
            "Description": f"Desc {i}",
            "Status": "New",
            "Priority": "Medium",
            "Origin": "Chat",
            "ContactId": None,
            "CreatedDate": None,
        }
        for i in range(n)
    ]


class TestFreshdesktriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_result(self):
        """triage key present in result (applied=False for too few tickets)."""
        raw_tickets = _make_raw_freshdesk_tickets(MIN_ISSUES_TO_TRIAGE - 1)

        with (
            patch(
                "src.services.agents.internal_tools.freshdesk_tools._get_freshdesk_credentials",
                AsyncMock(return_value={"subdomain": "test", "api_key": "key"}),
            ),
            patch(
                "src.services.agents.internal_tools.freshdesk_tools._make_freshdesk_request",
                AsyncMock(return_value=raw_tickets),
            ),
            patch(
                "src.services.agents.internal_tools.freshdesk_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
        ):
            from src.services.agents.internal_tools.freshdesk_tools import internal_list_freshdesk_tickets

            result = await internal_list_freshdesk_tickets(runtime_context=MagicMock())

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False

    @pytest.mark.asyncio
    async def test_triage_filters_tickets(self):
        """When triage runs, tickets are filtered."""
        n = MIN_ISSUES_TO_TRIAGE + 2
        raw_tickets = _make_raw_freshdesk_tickets(n)
        # The formatted tickets after _format_ticket will have id 0..n-1
        # Keep only the first two (id 0, 1)
        kept_ids = {0, 1}

        from src.services.agents.internal_tools.issue_triage import IssueTriageNote

        kept_note = IssueTriageNote(applied=True, total=n, scored=n, kept=2)
        # _triage_items built from formatted tickets; keep items with _id in kept_ids
        kept_triage_items = [
            {"title": f"Ticket {i}", "summary": f"Description {i}", "_id": i} for i in range(n) if i in kept_ids
        ]

        with (
            patch(
                "src.services.agents.internal_tools.freshdesk_tools._get_freshdesk_credentials",
                AsyncMock(return_value={"subdomain": "test", "api_key": "key"}),
            ),
            patch(
                "src.services.agents.internal_tools.freshdesk_tools._make_freshdesk_request",
                AsyncMock(return_value=raw_tickets),
            ),
            patch(
                "src.services.agents.internal_tools.freshdesk_tools._get_typesafe_client",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "src.services.agents.internal_tools.issue_triage.triage_issues",
                AsyncMock(return_value=(kept_triage_items, kept_note)),
            ),
        ):
            from src.services.agents.internal_tools.freshdesk_tools import internal_list_freshdesk_tickets

            result = await internal_list_freshdesk_tickets(runtime_context=MagicMock())

        assert result["success"] is True
        assert result["total"] == 2
        assert result["triage"]["applied"] is True


class TestHubSpotTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_result(self):
        """triage key present in result (applied=False for too few tickets)."""
        raw_tickets = _make_raw_hubspot_tickets(MIN_ISSUES_TO_TRIAGE - 1)

        with (
            patch(
                "src.services.agents.internal_tools.hubspot_tools._get_hubspot_credentials",
                AsyncMock(return_value={"access_token": "token"}),
            ),
            patch(
                "src.services.agents.internal_tools.hubspot_tools._make_hubspot_request",
                AsyncMock(return_value={"results": raw_tickets, "total": len(raw_tickets)}),
            ),
            patch(
                "src.services.agents.internal_tools.hubspot_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
        ):
            from src.services.agents.internal_tools.hubspot_tools import internal_list_hubspot_tickets

            result = await internal_list_hubspot_tickets(runtime_context=MagicMock())

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False

    @pytest.mark.asyncio
    async def test_triage_filters_tickets(self):
        """When triage runs, HubSpot tickets are filtered."""
        n = MIN_ISSUES_TO_TRIAGE + 2
        raw_tickets = _make_raw_hubspot_tickets(n)
        kept_ids = {"0", "1"}

        from src.services.agents.internal_tools.issue_triage import IssueTriageNote

        kept_note = IssueTriageNote(applied=True, total=n, scored=n, kept=2)
        kept_triage_items = [
            {"title": f"Issue {i}", "summary": f"Content {i}", "_id": str(i)} for i in range(n) if str(i) in kept_ids
        ]

        with (
            patch(
                "src.services.agents.internal_tools.hubspot_tools._get_hubspot_credentials",
                AsyncMock(return_value={"access_token": "token"}),
            ),
            patch(
                "src.services.agents.internal_tools.hubspot_tools._make_hubspot_request",
                AsyncMock(return_value={"results": raw_tickets, "total": n}),
            ),
            patch(
                "src.services.agents.internal_tools.hubspot_tools._get_typesafe_client",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "src.services.agents.internal_tools.issue_triage.triage_issues",
                AsyncMock(return_value=(kept_triage_items, kept_note)),
            ),
        ):
            from src.services.agents.internal_tools.hubspot_tools import internal_list_hubspot_tickets

            result = await internal_list_hubspot_tickets(runtime_context=MagicMock())

        assert result["success"] is True
        assert result["total"] == 2
        assert result["triage"]["applied"] is True


class TestSalesforceTriage:
    @pytest.mark.asyncio
    async def test_triage_note_in_result(self):
        """triage key present in result (applied=False for too few cases)."""
        raw_records = _make_raw_salesforce_records(MIN_ISSUES_TO_TRIAGE - 1)

        with (
            patch(
                "src.services.agents.internal_tools.salesforce_tools._get_salesforce_credentials",
                AsyncMock(return_value={"instance_url": "https://test.salesforce.com", "access_token": "tok"}),
            ),
            patch(
                "src.services.agents.internal_tools.salesforce_tools._soql",
                AsyncMock(return_value=raw_records),
            ),
            patch(
                "src.services.agents.internal_tools.salesforce_tools._get_typesafe_client",
                AsyncMock(return_value=None),
            ),
        ):
            from src.services.agents.internal_tools.salesforce_tools import internal_list_salesforce_cases

            result = await internal_list_salesforce_cases(runtime_context=MagicMock())

        assert result["success"] is True
        assert "triage" in result
        assert result["triage"]["applied"] is False

    @pytest.mark.asyncio
    async def test_triage_filters_cases(self):
        """When triage runs, Salesforce cases are filtered."""
        n = MIN_ISSUES_TO_TRIAGE + 2
        raw_records = _make_raw_salesforce_records(n)
        kept_ids = {"case0", "case1"}

        from src.services.agents.internal_tools.issue_triage import IssueTriageNote

        kept_note = IssueTriageNote(applied=True, total=n, scored=n, kept=2)
        kept_triage_items = [
            {
                "title": f"Case 0000{i}: Case {i}",
                "summary": f"Desc {i}",
                "_id": f"case{i}",
            }
            for i in range(n)
            if f"case{i}" in kept_ids
        ]

        with (
            patch(
                "src.services.agents.internal_tools.salesforce_tools._get_salesforce_credentials",
                AsyncMock(return_value={"instance_url": "https://test.salesforce.com", "access_token": "tok"}),
            ),
            patch(
                "src.services.agents.internal_tools.salesforce_tools._soql",
                AsyncMock(return_value=raw_records),
            ),
            patch(
                "src.services.agents.internal_tools.salesforce_tools._get_typesafe_client",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "src.services.agents.internal_tools.issue_triage.triage_issues",
                AsyncMock(return_value=(kept_triage_items, kept_note)),
            ),
        ):
            from src.services.agents.internal_tools.salesforce_tools import internal_list_salesforce_cases

            result = await internal_list_salesforce_cases(runtime_context=MagicMock())

        assert result["success"] is True
        assert result["total"] == 2
        assert result["triage"]["applied"] is True
