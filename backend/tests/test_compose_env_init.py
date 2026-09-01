import base64
import os
import stat
import subprocess
import sys
from pathlib import Path

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_initialization_creates_private_consistent_environment_without_overwrite(
    tmp_path: Path,
) -> None:
    target = tmp_path / ".env"
    command = [sys.executable, str(ROOT / "scripts/init_env.py"), "--output", str(target)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    settings = Settings(_env_file=target)  # pyright: ignore[reportCallIssue]
    assert settings.secret_encryption_key is not None
    key = settings.secret_encryption_key.get_secret_value()
    assert len(base64.urlsafe_b64decode(key)) == 32
    assert key not in result.stdout
    assert settings.auth_signing_key is not None
    assert settings.refresh_token_pepper is not None
    assert settings.auth_signing_key != settings.refresh_token_pepper
    assert settings.default_admin_password is not None
    assert settings.default_admin_password.get_secret_value() not in result.stdout
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    original = target.read_bytes()
    duplicate = subprocess.run(command, capture_output=True, text=True, check=False)
    assert duplicate.returncode != 0
    assert target.read_bytes() == original


def test_production_initialization_does_not_create_a_default_admin(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/init_env.py"),
            "--production",
            "--output",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    text = target.read_text()
    assert "ENV='production'" in text
    assert "DEFAULT_ADMIN_EMAIL=''" in text
    assert "DEFAULT_ADMIN_PASSWORD=''" in text
    assert "MCP_RUNTIME_IMAGE=''" in text
