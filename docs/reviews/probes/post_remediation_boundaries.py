"""Offline review probe. Only reads/writes synthetic files in a temporary directory.

Run from api/ with the project Python environment.
"""
import asyncio
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

from dotenv import dotenv_values

for key, value in dotenv_values('.env.test').items():
    if value is not None:
        os.environ[key] = value

from src.services.database.duckdb_connector import DuckDBConnector
from src.services.database.sqlite_connector import SQLiteConnector
from src.services.newsletter.render_service import NewsletterRenderService
from src.services.email.email_template_apply_service import apply_template_to_html
from src.models.email_template import EmailTemplateType


async def main():
    evidence = {}
    with tempfile.TemporaryDirectory(prefix='synkora-review-') as directory:
        root = Path(directory)
        secret = root / 'synthetic-secret.txt'
        secret.write_text('SYNTHETIC_REVIEW_MARKER')
        # Python built-in access, without spawning a shell or reading real secrets.
        payload = "{{ cycler.__init__.__globals__.__builtins__.open(" + repr(str(secret)) + ").read() }}"
        rendered = NewsletterRenderService().render({}, custom_template_html=payload)
        evidence['newsletter_template_reads_file'] = rendered == secret.read_text()
        rendered, applied = await apply_template_to_html('', {'type': EmailTemplateType.CUSTOM_HTML, 'html_content': payload})
        evidence['email_template_reads_file'] = applied and rendered == secret.read_text()
        connector = DuckDBConnector(SimpleNamespace(database_path=':memory:', connection_params={}, password_encrypted=None))
        assert await connector.connect()
        result = await connector.execute_query(f"SELECT content FROM read_text('{secret}')")
        evidence['duckdb_reads_host_file'] = result['rows'] == [{'content': secret.read_text()}]
        output = root / 'duckdb-output.csv'
        result = await connector.execute_query(f"COPY (SELECT 'SYNTHETIC_WRITE' AS marker) TO '{output}' (HEADER)")
        evidence['duckdb_writes_host_file'] = result['success'] and 'SYNTHETIC_WRITE' in output.read_text()
        await connector.disconnect()
        foreign = root / 'other-tenant.sqlite'
        with sqlite3.connect(foreign) as db:
            db.execute('CREATE TABLE private_data (marker TEXT)')
            db.execute("INSERT INTO private_data VALUES ('FOREIGN_SYNTHETIC_MARKER')")
        sqlite = SQLiteConnector(database_path=str(foreign))
        assert await sqlite.connect()
        result = await sqlite.execute_query('SELECT marker FROM private_data')
        evidence['sqlite_reads_unscoped_database_path'] = result['rows'] == [{'marker': 'FOREIGN_SYNTHETIC_MARKER'}]
        await sqlite.disconnect()
    print(json.dumps(evidence, indent=2))
    assert all(evidence.values())


asyncio.run(main())
