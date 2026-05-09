"""Supabase connector using API keys via PostgREST REST API."""

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.models.database_connection import DatabaseConnection
from src.services.agents.security import decrypt_value

logger = logging.getLogger(__name__)


class SupabaseConnector:
    """
    Supabase connector authenticated via anon/service_role API keys.

    Communicates with Supabase through the PostgREST REST API instead of a
    direct PostgreSQL TCP connection.  This is the recommended integration
    pattern — no database password required, works with Row Level Security,
    and is compatible with Supabase's connection pooling limits.

    Connection fields (DatabaseConnection columns):
      host               → Project URL: https://<ref>.supabase.co
                           (https:// is added automatically if omitted)
      username           → Anon / publishable key  (sent as ``apikey`` header)
      password_encrypted → Service role / secret key (sent as Bearer token)
      connection_params:
        use_service_role → bool (default: true)
                           When true the service_role key is used as the Bearer
                           token, granting full access and bypassing RLS.
                           Set to false to use the anon key (respects RLS).

    Query format accepted by execute_query (JSON string):
      Table query:
        {"table": "users", "select": "id,name,email", "limit": 100}
        {"table": "orders", "select": "*", "eq": {"status": "active"}, "limit": 50}
        {"table": "logs", "select": "*", "order": "created_at.desc", "limit": 200}
      RPC call:
        {"rpc": "my_function", "params": {"arg1": "value"}}

    Supported PostgREST filter keys: eq, neq, gt, gte, lt, lte, like, ilike, is, in
    """

    _FILTER_OPS = frozenset({"eq", "neq", "gt", "gte", "lt", "lte", "like", "ilike", "is", "in"})

    def __init__(self, database_connection: DatabaseConnection, timeout: float = 30.0) -> None:
        self.database_connection = database_connection
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _base_url(self) -> str:
        host = self.database_connection.host or ""
        if host.startswith("http://") or host.startswith("https://"):
            return host.rstrip("/")
        return f"https://{host}".rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        anon_key = self.database_connection.username or ""
        service_role_key = ""
        if self.database_connection.password_encrypted:
            service_role_key = decrypt_value(self.database_connection.password_encrypted)

        params = self.database_connection.connection_params or {}
        use_service_role = params.get("use_service_role", True)

        # When using service_role, the secret key must be sent as BOTH the
        # apikey header and the Authorization Bearer token — Supabase rejects
        # requests where apikey is the anon key but Bearer is the service_role key.
        if use_service_role and service_role_key:
            api_key = service_role_key
            bearer = service_role_key
        else:
            api_key = anon_key
            bearer = anon_key

        return {
            "apikey": api_key,
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url(),
                headers=self._auth_headers(),
                timeout=self.timeout,
                follow_redirects=False,
            )
        return self._client

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        try:
            client = await self._ensure_client()
            response = await client.get("/rest/v1/")
            response.raise_for_status()
            logger.info("Connected to Supabase: %s", self._base_url())
            return True
        except Exception as e:
            logger.error("Failed to connect to Supabase: %s", e)
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Disconnected from Supabase")

    # ------------------------------------------------------------------
    # Connection test (called from the UI before saving the connection)
    # ------------------------------------------------------------------

    async def test_connection(self) -> dict[str, Any]:
        base_url = self._base_url()
        async with httpx.AsyncClient(
            base_url=base_url,
            headers=self._auth_headers(),
            timeout=self.timeout,
            follow_redirects=False,
        ) as client:
            try:
                response = await client.get("/rest/v1/")
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": f"Connected to Supabase ({base_url})",
                        "details": {
                            "url": base_url,
                            "database_type": "supabase",
                            "auth_method": "api_key",
                        },
                    }
                return {
                    "success": False,
                    "message": f"Connection failed: HTTP {response.status_code} — {response.text[:200]}",
                }
            except Exception as e:
                logger.error("Supabase connection test failed: %s", e)
                return {"success": False, "message": f"Connection failed: {e}"}

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    # Complex aggregate / expression patterns that PostgREST cannot translate
    _COMPLEX_EXPR_RE = re.compile(
        r"EXTRACT\s*\(|DATE_TRUNC\s*\(|CAST\s*\(|::|PERCENTILE|STDDEV|VARIANCE|MEDIAN"
        r"|\bCASE\b|\bCOALESCE\b|\bNULLIF\b",
        re.IGNORECASE,
    )

    # Matches NOW() - INTERVAL 'N unit'
    _NOW_INTERVAL_RE = re.compile(
        r"NOW\s*\(\s*\)\s*-\s*INTERVAL\s+'(\d+)\s+(hour|minute|day|week)s?'",
        re.IGNORECASE,
    )

    async def execute_query(self, query: str) -> dict[str, Any]:
        """
        Execute a PostgREST query.

        Args:
            query: JSON string or a simple SQL SELECT statement.

        Returns:
            {"success": bool, "rows": [...], "row_count": int, "columns": [...]}
        """
        try:
            # Try JSON first; fall back to SQL translation.
            try:
                q = json.loads(query)
            except json.JSONDecodeError:
                q = self._try_translate_sql(query)
                if q is None:
                    return {
                        "success": False,
                        "error": (
                            "Supabase (PostgREST) cannot execute this query because it contains "
                            "expressions that cannot be translated to the REST API "
                            "(e.g. EXTRACT, DATE_TRUNC, CAST, CASE, SUM(CASE WHEN ...), etc.).\n\n"
                            "Use one of these approaches instead:\n"
                            "1. Simple COUNT(*) GROUP BY (supported):\n"
                            "   SELECT status, COUNT(*) FROM my_table GROUP BY status\n"
                            "2. JSON table query with filters:\n"
                            '   {"table": "my_table", "select": "id,name,status", "eq": {"status": "active"}, "limit": 100}\n'
                            "3. RPC call to a pre-created PostgreSQL function:\n"
                            '   {"rpc": "my_aggregate_function", "params": {}}\n\n'
                            "For analytics requiring EXTRACT/CAST/CASE, ask the user to create "
                            "a database function (RPC) for the specific calculation needed."
                        ),
                        "rows": [],
                        "row_count": 0,
                        "columns": [],
                    }

            client = await self._ensure_client()

            if "rpc" in q:
                return await self._rpc(client, q)
            if "table" not in q:
                return {
                    "success": False,
                    "error": "Query must have a 'table' or 'rpc' key.",
                    "rows": [],
                    "row_count": 0,
                    "columns": [],
                }
            return await self._table_query(client, q)

        except Exception as e:
            logger.error("Supabase query failed: %s", e)
            return {"success": False, "error": str(e), "rows": [], "row_count": 0, "columns": []}

    # ------------------------------------------------------------------
    # SQL → PostgREST translation helpers
    # ------------------------------------------------------------------

    def _resolve_now_interval(self, sql: str) -> str:
        """Replace NOW() - INTERVAL 'N unit' with the computed ISO-8601 timestamp."""
        _unit_map = {"hour": 3600, "minute": 60, "day": 86400, "week": 604800}

        def _replace(m: re.Match) -> str:
            n = int(m.group(1))
            unit = m.group(2).lower()
            seconds = _unit_map.get(unit, 0) * n
            if not seconds:
                return m.group(0)
            ts = (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()
            return f"'{ts}'"

        return self._NOW_INTERVAL_RE.sub(_replace, sql)

    def _try_translate_sql(self, sql: str) -> dict[str, Any] | None:
        """
        Translate a simple SQL SELECT to a PostgREST query dict.

        Supports:
          - Plain SELECT: SELECT cols FROM table [WHERE …] [ORDER BY …] [LIMIT n]
          - Aggregate SELECT: SELECT col, COUNT(*) FROM table [WHERE …] GROUP BY col [ORDER BY …] [LIMIT n]
            → PostgREST: ?select=col,count()   (requires db-aggregates-enabled, default on Supabase)

        Returns None when the statement is too complex to translate reliably.
        """
        sql = sql.strip().rstrip(";")
        if not re.match(r"\s*SELECT\b", sql, re.IGNORECASE):
            return None

        # Reject complex expressions that PostgREST cannot handle in any form
        # (EXTRACT, DATE_TRUNC, CAST ::, CASE, SUM(CASE WHEN …), subqueries, etc.)
        if self._COMPLEX_EXPR_RE.search(sql):
            return None

        # Subquery guard: more than one FROM keyword means nested SELECT
        if len(re.findall(r"\bFROM\b", sql, re.IGNORECASE)) > 1:
            return None

        # Resolve NOW() - INTERVAL '...' → literal timestamp so we can use it in filters
        sql = self._resolve_now_interval(sql)

        # FROM table
        from_m = re.search(r"\bFROM\s+`?\"?(\w+)`?\"?", sql, re.IGNORECASE)
        if not from_m:
            return None
        table = from_m.group(1)

        # SELECT … FROM
        select_m = re.match(r"\s*SELECT\s+(.*?)\s+FROM\b", sql, re.IGNORECASE | re.DOTALL)
        if not select_m:
            return None
        select_raw = select_m.group(1).strip()

        select_str, alias_map = self._convert_select(select_raw)
        q: dict[str, Any] = {"table": table, "select": select_str}

        # WHERE clause (stop before GROUP BY / HAVING / ORDER BY / LIMIT)
        where_m = re.search(
            r"\bWHERE\s+(.*?)(?:\bGROUP\s+BY\b|\bHAVING\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
            sql,
            re.IGNORECASE | re.DOTALL,
        )
        if where_m:
            self._apply_where(q, where_m.group(1).strip())

        # ORDER BY (stop before LIMIT) — pass alias_map to resolve aggregate aliases
        order_m = re.search(r"\bORDER\s+BY\s+(.*?)(?:\bLIMIT\b|$)", sql, re.IGNORECASE | re.DOTALL)
        if order_m:
            q["order"] = self._convert_order(order_m.group(1).strip(), alias_map)

        # LIMIT / OFFSET
        limit_m = re.search(r"\bLIMIT\s+(\d+)", sql, re.IGNORECASE)
        if limit_m:
            q["limit"] = int(limit_m.group(1))
        offset_m = re.search(r"\bOFFSET\s+(\d+)", sql, re.IGNORECASE)
        if offset_m:
            q["offset"] = int(offset_m.group(1))

        logger.debug("SQL→PostgREST: %s", q)
        return q

    def _split_csv(self, s: str) -> list[str]:
        """Split comma-separated values, respecting parentheses."""
        parts: list[str] = []
        depth = 0
        buf: list[str] = []
        for ch in s:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
            buf.append(ch)
        if buf:
            parts.append("".join(buf).strip())
        return parts

    def _convert_select(self, select_raw: str) -> tuple[str, dict[str, str]]:
        """Translate a SQL SELECT column list to a PostgREST select string.

        Returns (select_string, alias_map) where alias_map maps SQL alias ->
        PostgREST expression, e.g. {"errors": "count()", "last_error": "completed_at.max()"}.
        Used by _convert_order to rewrite ORDER BY aliases to PostgREST expressions.
        """
        if select_raw.strip() == "*":
            return "*", {}

        parts: list[str] = []
        alias_map: dict[str, str] = {}

        for col in self._split_csv(select_raw):
            col = col.strip()

            # COUNT(*) [AS alias]
            m = re.match(r"COUNT\s*\(\s*\*\s*\)(?:\s+AS\s+(\w+))?$", col, re.IGNORECASE)
            if m:
                expr = "count()"
                parts.append(expr)
                if m.group(1):
                    alias_map[m.group(1).lower()] = expr
                continue

            # COUNT(col) [AS alias]
            m = re.match(r"COUNT\s*\(\s*\w+\s*\)(?:\s+AS\s+(\w+))?$", col, re.IGNORECASE)
            if m:
                expr = "count()"
                parts.append(expr)
                if m.group(1):
                    alias_map[m.group(1).lower()] = expr
                continue

            # SUM/AVG/MAX/MIN(col) [AS alias]
            m = re.match(r"(SUM|AVG|MAX|MIN)\s*\(\s*(\w+)\s*\)(?:\s+AS\s+(\w+))?$", col, re.IGNORECASE)
            if m:
                expr = f"{m.group(2)}.{m.group(1).lower()}()"
                parts.append(expr)
                if m.group(3):
                    alias_map[m.group(3).lower()] = expr
                continue

            # plain col [AS alias] — keep only the column name
            m = re.match(r"(\w+)(?:\s+AS\s+\w+)?$", col, re.IGNORECASE)
            if m:
                parts.append(m.group(1))
                continue

            # Unrecognised expression — include as-is
            parts.append(col)

        return (",".join(parts) if parts else "*"), alias_map

    def _apply_where(self, q: dict[str, Any], where: str) -> None:
        """Parse a simple WHERE clause and add PostgREST filter keys to q."""
        for cond in re.split(r"\bAND\b", where, flags=re.IGNORECASE):
            cond = cond.strip().strip("()")
            if not cond:
                continue

            # IS NOT NULL
            m = re.match(r"(\w+)\s+IS\s+NOT\s+NULL$", cond, re.IGNORECASE)
            if m:
                q.setdefault("neq", {})[m.group(1)] = "null"
                continue

            # IS NULL
            m = re.match(r"(\w+)\s+IS\s+NULL$", cond, re.IGNORECASE)
            if m:
                q.setdefault("is", {})[m.group(1)] = "null"
                continue

            # LIKE / ILIKE
            m = re.match(r"(\w+)\s+(I?LIKE)\s+'(.+?)'$", cond, re.IGNORECASE)
            if m:
                op = m.group(2).lower()
                q.setdefault(op, {})[m.group(1)] = m.group(3)
                continue

            # IN (…)
            m = re.match(r"(\w+)\s+IN\s*\((.+?)\)$", cond, re.IGNORECASE)
            if m:
                vals = ",".join(v.strip().strip("'\"") for v in m.group(2).split(","))
                q.setdefault("in", {})[m.group(1)] = vals
                continue

            # != / <>
            m = re.match(r"(\w+)\s*(?:!=|<>)\s*'?([^']+?)'?$", cond, re.IGNORECASE)
            if m:
                q.setdefault("neq", {})[m.group(1)] = m.group(2).strip("'")
                continue

            # >= / <= / > / <  (order matters — check two-char ops first)
            for op_sql, op_pg in [(">=", "gte"), ("<=", "lte"), (">", "gt"), ("<", "lt")]:
                m = re.match(rf"(\w+)\s*{re.escape(op_sql)}\s*'?([^']+?)'?$", cond, re.IGNORECASE)
                if m:
                    q.setdefault(op_pg, {})[m.group(1)] = m.group(2).strip("'")
                    break
            else:
                # = (quoted or unquoted value)
                m = re.match(r"(\w+)\s*=\s*'(.+?)'$", cond, re.IGNORECASE) or re.match(
                    r"(\w+)\s*=\s*(\S+)$", cond, re.IGNORECASE
                )
                if m:
                    q.setdefault("eq", {})[m.group(1)] = m.group(2)
                    continue

                logger.debug("Supabase SQL translator: skipping unrecognised WHERE condition: %s", cond)

    def _convert_order(self, order_raw: str, alias_map: dict[str, str] | None = None) -> str:
        """Translate a SQL ORDER BY clause to a PostgREST order string.

        alias_map resolves SELECT aliases to PostgREST aggregate expressions so that
        e.g. ORDER BY errors DESC (where errors = COUNT(*)) becomes count().desc
        instead of the invalid errors.desc.
        """
        alias_map = alias_map or {}
        parts: list[str] = []
        for col in self._split_csv(order_raw):
            col = col.strip()
            m = re.match(r"(\w+)(?:\s+(ASC|DESC))?$", col, re.IGNORECASE)
            if m:
                direction = (m.group(2) or "asc").lower()
                name = m.group(1)
                # Resolve alias to its PostgREST aggregate expression if present
                expr = alias_map.get(name.lower(), name)
                parts.append(f"{expr}.{direction}")
            else:
                parts.append(col)
        return ",".join(parts)

    async def _table_query(self, client: httpx.AsyncClient, q: dict[str, Any]) -> dict[str, Any]:
        table = q["table"]
        params: dict[str, str] = {"select": q.get("select", "*")}

        limit = min(int(q.get("limit", 100)), 1000)
        params["limit"] = str(limit)
        if q.get("offset"):
            params["offset"] = str(int(q["offset"]))
        if q.get("order"):
            params["order"] = q["order"]

        # PostgREST filter operators: field=op.value
        for op in self._FILTER_OPS:
            if op in q:
                for field, value in q[op].items():
                    params[field] = f"{op}.{value}"

        response = await client.get(f"/rest/v1/{table}", params=params)
        if response.status_code not in (200, 206):
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:400]}",
                "rows": [],
                "row_count": 0,
                "columns": [],
            }

        rows = response.json()
        if not isinstance(rows, list):
            rows = [rows] if rows else []
        columns = list(rows[0].keys()) if rows else []
        return {"success": True, "rows": rows, "row_count": len(rows), "columns": columns}

    async def _rpc(self, client: httpx.AsyncClient, q: dict[str, Any]) -> dict[str, Any]:
        fn = q["rpc"]
        params = q.get("params", {})
        response = await client.post(f"/rest/v1/rpc/{fn}", json=params)
        if response.status_code not in (200, 201):
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text[:400]}",
                "rows": [],
                "row_count": 0,
                "columns": [],
            }

        data = response.json()
        rows = data if isinstance(data, list) else [{"result": data}]
        columns = list(rows[0].keys()) if rows else []
        return {"success": True, "rows": rows, "row_count": len(rows), "columns": columns}

    # ------------------------------------------------------------------
    # Schema introspection
    # ------------------------------------------------------------------

    async def get_schema(self) -> dict[str, Any]:
        """Return table/column schema parsed from the PostgREST OpenAPI spec."""
        try:
            client = await self._ensure_client()
            response = await client.get("/rest/v1/")
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text[:200]}", "tables": []}

            tables = self._parse_openapi(response.json())
            return {"success": True, "tables": tables}
        except Exception as e:
            logger.error("Supabase schema fetch failed: %s", e)
            return {"success": False, "error": str(e), "tables": []}

    def _parse_openapi(self, spec: dict[str, Any]) -> list[dict[str, Any]]:
        tables = []
        for table_name, definition in (spec.get("definitions") or {}).items():
            required = set(definition.get("required") or [])
            columns = []
            for col_name, col_def in (definition.get("properties") or {}).items():
                col_type = col_def.get("type") or col_def.get("format", "unknown")
                if isinstance(col_type, list):
                    col_type = next((t for t in col_type if t != "null"), "unknown")
                columns.append(
                    {
                        "name": col_name,
                        "type": col_type,
                        "nullable": col_name not in required,
                        "description": col_def.get("description", ""),
                    }
                )
            tables.append({"name": table_name, "columns": columns, "column_count": len(columns)})
        return sorted(tables, key=lambda t: t["name"])

    async def get_tables(self) -> list[str]:
        result = await self.get_schema()
        return [t["name"] for t in result.get("tables", [])]

    async def get_table_info(self, table: str) -> dict[str, Any]:
        result = await self.get_schema()
        for t in result.get("tables", []):
            if t["name"] == table:
                return t
        return {"name": table, "columns": [], "error": "Table not found"}
