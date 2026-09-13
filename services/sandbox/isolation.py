"""Linux execution boundary. Never fall back to an unrestricted subprocess."""

import shutil
import tempfile
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def runtime_config() -> Path:
    # Container runtimes mount hosts/resolv.conf with locked mount flags that
    # cannot be rebound read-only inside an unprivileged user namespace.
    # Copy only these nonsecret runtime files into a private, unmounted directory.
    directory = Path(tempfile.mkdtemp(prefix="sandbox-runtime-"))
    for name in (
        "resolv.conf",
        "hosts",
        "nsswitch.conf",
        "ld.so.cache",
        "passwd",
        "group",
    ):
        source = Path("/etc") / name
        if source.exists():
            shutil.copyfile(source, directory / name)
    return directory


def isolated_command(
    workspace: Path, cwd: Path, command: list[str], env: dict[str, str]
) -> list[str]:
    binary = shutil.which("bwrap", path="/usr/bin:/bin")
    if not binary:
        raise RuntimeError(
            "Sandbox execution requires bubblewrap and unprivileged Linux user namespaces"
        )
    if not command or not command[0] or any("\x00" in arg for arg in command):
        raise ValueError("A valid command is required")
    cwd.relative_to(workspace)
    args = [
        binary,
        "--unshare-all",
        "--unshare-user",
        "--die-with-parent",
        "--new-session",
        "--cap-drop",
        "ALL",
        "--clearenv",
    ]
    # Only immutable runtime files and this workspace are visible. In particular,
    # do not bind /, /app, /home, host /proc, /run, or the shared /workspaces root.
    for path in ("/usr", "/bin", "/sbin", "/lib", "/lib64"):
        if Path(path).exists():
            args += ["--ro-bind", path, path]
    if Path("/etc/ssl/certs").exists():
        args += ["--ro-bind", "/etc/ssl/certs", "/etc/ssl/certs"]
    for path in runtime_config().iterdir():
        args += ["--ro-bind", str(path), "/etc/" + path.name]
    args += ["--dir", "/proc", "--dir", "/dev"]
    # No terminal is exposed by this API. Bind only inert standard devices,
    # avoiding a devpts mount (and any host terminal or block device).
    for name in ("null", "zero", "random", "urandom"):
        args += ["--dev-bind", "/dev/" + name, "/dev/" + name]
    args += [
        "--tmpfs",
        "/tmp",
        "--bind",
        str(workspace),
        str(workspace),
        "--chdir",
        str(cwd),
    ]
    for key, value in env.items():
        if not key or "=" in key or "\x00" in key or "\x00" in value:
            raise ValueError("Invalid environment variable")
        args += ["--setenv", key, value]
    return [*args, "--", *command]


def launcher_env() -> dict[str, str]:
    # Caller-controlled LD_PRELOAD/PYTHONPATH/etc. must never affect bwrap itself.
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
