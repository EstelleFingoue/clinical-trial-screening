from __future__ import annotations

import shutil
import subprocess

import pytest


@pytest.mark.docker
def test_compose_configuration_is_valid():
    if shutil.which("docker") is None:
        pytest.skip("Docker indisponible")
    subprocess.run(
        ["docker", "compose", "config", "--quiet"],
        check=True,
        capture_output=True,
        text=True,
    )
