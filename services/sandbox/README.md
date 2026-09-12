# Sandbox execution boundary

Commands run through Bubblewrap in a separate mount, user and PID namespace.
Only the selected workspace is mounted writable from the service filesystem.
Runtime directories are read-only; temporary files and the root filesystem are
private to the command. `/proc` is empty and only null/zero/random devices are
available. The command cannot see the service source, service environment,
service-account token or another tenant's workspaces. Descendants are removed
when execution ends. Each command also has a private network namespace with no
egress, including service-loopback access. Network operations such as git clone
are unavailable until a separately reviewed, tenant-aware egress proxy is added.

The API derives a distinct workspace key per agent and conversation. File APIs
and execution take the same cross-process workspace lock so a running program
cannot race the file API's path checks. Binary files use `/v1/files/binary`, with
workspace authorization and a 10 MiB limit, rather than shell commands.

Run on Linux with unprivileged user namespaces enabled and Bubblewrap installed
(included in the Dockerfile). The service runs as UID/GID 1000, drops container
capabilities and disallows privilege escalation. It does not need a privileged
container or a Docker socket. Host runtime policies must permit the required
namespace operations. A startup self-test fails readiness if isolation cannot
be established; there is no unrestricted execution fallback. Programs that
require `/proc`, terminals or host filesystem access are intentionally unavailable.

From the repository root, validate the same image and constraints before rollout:

```sh
podman build -t localhost/synkora-sandbox-security-review services/sandbox
podman run --rm -i --cap-drop=ALL --security-opt=no-new-privileges \
  localhost/synkora-sandbox-security-review python - < services/sandbox/test_isolation.py
```

The test uses only synthetic data and checks successful owned-file operations,
denied foreign files and symlinks, hidden service state, bounded output, timeout
and descendant cleanup, workspace locking, FIFO rejection and binary round trips.
It also executes the readiness self-test and generates the service OpenAPI schema.

`SANDBOX_API_KEY` is mandatory and must be a random secret of at least 32 characters.
The API sends a 60-second HMAC capability bound to the tenant and conversation
workspace in `X-Sandbox-Key`; the service rejects the raw signing key, expired
capabilities and capabilities for other workspaces. Deploy API and sandbox together.
