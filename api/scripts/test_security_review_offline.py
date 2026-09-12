"""Run focused security regression tests without DNS or IP network access.

Use an existing environment containing the project's test dependencies; this
script never installs packages. ASGI tests execute in-process, without a server.
"""

import os
import socket
import sys
from pathlib import Path


def deny_network(event, args):
    if event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
        raise socket.gaierror("DNS disabled by the offline security test runner")
    if event in {"socket.connect", "socket.bind", "socket.sendto"} and args[0].family in {
        socket.AF_INET,
        socket.AF_INET6,
    }:
        raise OSError("IP networking disabled by the offline security test runner")


sys.addaudithook(deny_network)
os.chdir(Path(__file__).resolve().parents[1])
sys.path.insert(0, str(Path.cwd()))

import pytest  # noqa: E402

DEFAULT_TESTS = [
    "tests/unit/services/security/test_ten_finding_remediation.py",
    "tests/unit/services/agents/internal_tools/test_command_tools.py",
    "tests/unit/services/agents/internal_tools/test_file_tools.py",
    "tests/unit/services/activity/test_activity_log_service.py",
    "tests/unit/services/compute/backends/test_sandbox_backend.py",
    "tests/unit/controllers/test_social_auth.py",
    "tests/unit/controllers/test_social_auth_config.py",
]

if __name__ == "__main__":
    sys.exit(pytest.main(["-q", "-o", "addopts=", *(sys.argv[1:] or DEFAULT_TESTS)]))
