import base64
import importlib.util
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.services.agents.internal_tools import browser_interactive
from src.services.security.workspace_files import read_workspace_file


@pytest.mark.asyncio
async def test_browser_upload_reads_only_owned_workspace_bytes(tmp_path, monkeypatch):
    workspace = tmp_path / "owned"
    workspace.mkdir()
    (workspace / "document.txt").write_bytes(b"allowed bytes")
    foreign = tmp_path / "foreign.txt"
    foreign.write_bytes(b"foreign marker")
    (workspace / "symlink.txt").symlink_to(foreign)
    context = SimpleNamespace(tenant_id=uuid.uuid4())
    config = {"_runtime_context": context, "workspace_path": str(workspace)}
    client = SimpleNamespace(browser_upload_file=AsyncMock(return_value={"success": True}))
    monkeypatch.setattr(browser_interactive, "_scraper", lambda: client)
    monkeypatch.setattr(browser_interactive, "_get_workspace_path", lambda config: str(workspace))
    monkeypatch.setattr("src.services.compute.resolver.get_compute_session_from_config", AsyncMock(return_value=None))
    for path in (str(foreign), "../foreign.txt", "symlink.txt"):
        result = await browser_interactive.internal_browser_upload_file("input", [path], config=config)
        assert not result["success"]
    client.browser_upload_file.assert_not_awaited()
    result = await browser_interactive.internal_browser_upload_file("input", ["document.txt"], config=config)
    assert result["success"]
    supplied = client.browser_upload_file.await_args.kwargs
    assert "file_paths" not in supplied
    assert base64.b64decode(supplied["files"][0]["content_base64"]) == b"allowed bytes"


def test_workspace_upload_rejects_symlinked_parent(tmp_path):
    own = tmp_path / "own"
    foreign = tmp_path / "foreign"
    own.mkdir()
    foreign.mkdir()
    (foreign / "file").write_text("foreign")
    (own / "link").symlink_to(foreign, target_is_directory=True)
    with pytest.raises(OSError):
        read_workspace_file(str(own), "link/file")


@pytest.fixture
def scraper(monkeypatch):
    root = Path(__file__).resolve().parents[5] / "services" / "scraper"
    monkeypatch.syspath_prepend(str(root))
    # Browser initialization is lazy; importing this module does not launch one.
    spec = importlib.util.spec_from_file_location("scraper_upload_security", root / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_scraper_rejects_server_paths_and_passes_bytes_to_playwright(scraper, monkeypatch):
    with pytest.raises(ValidationError):
        scraper.UploadFileRequest(file_ref="input", file_paths=["/etc/passwd"])
    locator = SimpleNamespace(set_input_files=AsyncMock())
    monkeypatch.setattr(
        scraper,
        "_get_session_and_page",
        AsyncMock(return_value=(SimpleNamespace(get_page_state=lambda page: None), object())),
    )
    monkeypatch.setattr(scraper, "_resolve_locator", lambda *args: locator)
    request = scraper.UploadFileRequest(
        file_ref="input", files=[{"name": "owned.txt", "content_base64": base64.b64encode(b"owned bytes").decode()}]
    )
    assert (await scraper.browser_upload_file(request))["success"]
    assert locator.set_input_files.await_args.args[0] == [
        {"name": "owned.txt", "mimeType": "application/octet-stream", "buffer": b"owned bytes"}
    ]
