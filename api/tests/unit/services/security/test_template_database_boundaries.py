import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import duckdb
import pytest
from jinja2.exceptions import SecurityError

from src.models.email_template import EmailTemplateType
from src.services.database.duckdb_connector import DuckDBConnector
from src.services.database.sqlite_connector import SQLiteConnector
from src.services.email.email_template_apply_service import apply_template_to_html
from src.services.newsletter.render_service import NewsletterRenderService
from src.services.security.custom_templates import render_custom_template
from src.services.security.local_databases import local_database_path


@pytest.mark.parametrize(
    "payload",
    [
        "{{ cycler.__init__.__globals__.__builtins__.open('/synthetic').read() }}",
        "{{ ''.__class__.__mro__ }}",
        "{{ body.upper() }}",
        "{{ 'x' * 1000000000 }}",
        "{{ 10 ** 10000000 }}",
        "{% for x in range(99999999) %}x{% endfor %}",
        "{% macro x() %}{{ x() }}{% endmacro %}{{ x() }}",
        "{% include '/synthetic' %}",
    ],
)
@pytest.mark.asyncio
async def test_both_render_paths_reject_executable_templates(payload):
    with pytest.raises(SecurityError):
        NewsletterRenderService().render({}, custom_template_html=payload)
    result, applied = await apply_template_to_html(
        "original",
        {
            "type": EmailTemplateType.CUSTOM_HTML,
            "html_content": payload,
        },
    )
    assert (result, applied) == ("original", False)


@pytest.mark.asyncio
async def test_supported_templates():
    assert (
        render_custom_template(
            "{% if items %}{% for item in items %}{{ item.title|upper }}{% endfor %}{% endif %}",
            {"items": [{"title": "<news>"}]},
        )
        == "&lt;NEWS&gt;"
    )
    result, applied = await apply_template_to_html(
        "<p>Hello</p>",
        {
            "type": EmailTemplateType.CUSTOM_HTML,
            "html_content": "<main>{{ body }}</main>",
        },
    )
    assert applied and result == "<main><p>Hello</p></main>"
    assert "Hello" in NewsletterRenderService().render({"hackernews": [{"title": "Hello"}]})


def test_template_limits_and_objects():
    for context in ({"x": object()}, {"x": list(range(101))}, {"x": "x" * 600000}):
        with pytest.raises(SecurityError):
            render_custom_template("{{ x }}", context)
    with pytest.raises(SecurityError):
        render_custom_template("{% for x in items %}{{ text }}{% endfor %}", {"items": [1] * 100, "text": "x" * 20000})


def test_empty_loops_cannot_iterate_large_strings():
    with pytest.raises(SecurityError):
        render_custom_template(
            "{% for x in text %}{% for y in text %}{% endfor %}{% endfor %}",
            {"text": "x" * 100000},
        )


@pytest.fixture
def assets(tmp_path, monkeypatch):
    tenant = uuid4()
    monkeypatch.setenv("LOCAL_DATABASE_ROOT", str(tmp_path))
    folder = tmp_path / str(tenant)
    folder.mkdir()
    with sqlite3.connect(folder / "sample.sqlite") as db:
        db.execute("CREATE TABLE records (value TEXT)")
        db.execute("INSERT INTO records VALUES ('tenant data')")
    with duckdb.connect(str(folder / "sample.duckdb")) as db:
        db.execute("CREATE TABLE records AS SELECT 'tenant data' AS value")
    return tenant, folder


def model(tenant, path=":memory:", params=None):
    return SimpleNamespace(tenant_id=tenant, database_path=path, connection_params=params or {})


@pytest.mark.parametrize(
    "path", ["../sample.sqlite", "/tmp/sample.sqlite", "file:test?mode=ro", "a/b", "a\\b", "..", ""]
)
def test_reject_unscoped_paths(assets, path):
    with pytest.raises(ValueError):
        local_database_path(path, assets[0])


def test_foreign_symlink_and_missing_tenant(assets):
    tenant, folder = assets
    with pytest.raises(ValueError):
        local_database_path("sample.sqlite", uuid4())
    with pytest.raises(ValueError):
        local_database_path(":memory:", None, memory=True)
    (folder / "link.sqlite").symlink_to(folder / "sample.sqlite")
    with pytest.raises(ValueError):
        local_database_path("link.sqlite", tenant)


@pytest.mark.asyncio
async def test_sqlite_readonly_and_no_attach(assets):
    tenant, folder = assets
    connector = SQLiteConnector("sample.sqlite", tenant_id=tenant)
    assert await connector.connect()
    try:
        result = await connector.execute_query("SELECT * FROM records")
        assert result["rows"] == [{"value": "tenant data"}]
        for query in (
            f"ATTACH DATABASE '{folder / 'sample.sqlite'}' AS foreign_db",
            f"VACUUM INTO '{folder / 'leak.sqlite'}'",
            "PRAGMA writable_schema=ON",
            "PRAGMA temp_store_directory='/tmp'",
            "SELECT load_extension('/synthetic')",
            "DELETE FROM records",
            "CREATE TEMP TABLE leak AS SELECT * FROM records",
        ):
            assert not (await connector.execute_query(query))["success"], query
        assert (await connector.execute_query("PRAGMA table_info(records)"))["success"]
        assert not (folder / "leak.sqlite").exists()
    finally:
        await connector.disconnect()


@pytest.mark.asyncio
async def test_duckdb_blocks_external_access_and_reconfiguration(assets):
    tenant, folder = assets
    connector = DuckDBConnector(model(tenant))
    assert await connector.connect()
    try:
        assert (await connector.execute_query("SELECT 42 AS answer"))["rows"] == [{"answer": 42}]
        for query in (
            f"SELECT * FROM read_text('{folder / 'sample.sqlite'}')",
            f"COPY (SELECT 1) TO '{folder / 'leak.csv'}'",
            f"ATTACH '{folder / 'sample.duckdb'}' AS foreign_db",
            "INSTALL httpfs",
            "LOAD httpfs",
            "SET enable_external_access=true",
            "SET lock_configuration=false",
            "SET allowed_paths=['/tmp']",
            "SELECT * FROM read_csv('http://127.0.0.1/private.csv')",
        ):
            assert not (await connector.execute_query(query))["success"], query
        assert not (folder / "leak.csv").exists()
    finally:
        await connector.disconnect()
    connector = DuckDBConnector(model(tenant, "sample.duckdb"))
    assert await connector.connect()
    try:
        assert (await connector.execute_query("SELECT * FROM records"))["rows"] == [{"value": "tenant data"}]
        assert not (await connector.execute_query("DELETE FROM records"))["success"]
    finally:
        await connector.disconnect()
    assert not await DuckDBConnector(model(tenant, params={"extensions": ["httpfs"]})).connect()


@pytest.mark.asyncio
async def test_duckdb_timeout_and_result_limit(assets):
    connector = DuckDBConnector(model(assets[0]), timeout=0.01)
    assert await connector.connect()
    try:
        assert not (await connector.execute_query("SELECT sum(a.i*b.i) FROM range(1000000) a(i), range(1000000) b(i)"))[
            "success"
        ]
        assert (await connector.execute_query("SELECT 1"))["success"]
        assert not (await connector.execute_query("SELECT * FROM range(10001)"))["success"]
    finally:
        await connector.disconnect()
