"""The native FPK CLI uses the installed app without repairing shared Python."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "posix", reason="FnOS CLI requires bash and symlinks")
CLI = Path(__file__).resolve().parents[2] / "fnos" / "native" / "app" / "bin" / "octop-cli"


@pytest.mark.parametrize("has_package", [True, False])
def test_native_cli_from_shell(tmp_path: Path, has_package: bool) -> None:
    payload = tmp_path / "@appcenter" / "octop-native"
    (payload / "bin").mkdir(parents=True)
    (payload / "cmd").mkdir()
    package = payload / "site-packages" / "octop" / "cli"
    if has_package:
        package.mkdir(parents=True)
        (package.parent / "__init__.py").touch()
        (package / "__init__.py").touch()
        (package / "main.py").write_text('print("octop v1.0.3b4")\n', encoding="utf-8")

    python = tmp_path / "python3.12"
    python.write_text(
        '#!/bin/bash\nif [ "$*" = "-m octop.cli.main version" ]; then\n'
        f'    exec {shlex.quote(sys.executable)} "$@"\n'
        'fi\necho "unexpected Python invocation: $*" >&2\nexit 99\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    (payload / "cmd" / "common.sh").write_text(
        f"find_python312() {{ echo {shlex.quote(str(python))}; }}\n", encoding="utf-8"
    )

    launcher = payload / "bin" / "octop-cli"
    shutil.copy(CLI, launcher)
    shell_bin = tmp_path / "usr-local-bin"
    shell_bin.mkdir()
    command = shell_bin / "octop"
    command.symlink_to(launcher)
    data = tmp_path / "@appshare" / "octop-native" / "data"
    data.mkdir(parents=True)
    pkgvar = tmp_path / "var"
    pkgvar.mkdir()

    result = subprocess.run(
        ["bash", str(command), "version"],
        env={
            "PATH": os.defpath,
            "TRIM_PKGVAR": str(pkgvar),
            "TRIM_DATA_SHARE_PATHS": str(data),
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert "unexpected Python invocation:" not in result.stderr
    if has_package:
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "octop v1.0.3b4"
    else:
        assert result.returncode == 1
        assert str(payload / "site-packages") in result.stderr
        assert "应用中心" in result.stderr
