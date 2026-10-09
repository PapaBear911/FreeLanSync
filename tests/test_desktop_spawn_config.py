"""Guard for TD-021: desktop spawn host comes from config, not a literal."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_JS = ROOT / "desktop-app" / "main.js"
README = ROOT / "README.md"


def test_spawn_host_is_config_driven():
    src = MAIN_JS.read_text(encoding="utf-8")
    # No hardcoded literal in the uvicorn spawn args...
    assert "'--host', '0.0.0.0'" not in src, (
        "TD-021: uvicorn spawn hardcodes --host 0.0.0.0 again"
    )
    # ...the host variable reads the same env the server defines.
    assert "process.env.FREELANSYNC_HOST || process.env.PHOTOSYNC_HOST || '0.0.0.0'" in src
    assert "'--host', serverHost" in src


def test_readme_documents_lan_bind_threat_model():
    src = README.read_text(encoding="utf-8")
    assert "## Network binding & threat model" in src
    assert "FREELANSYNC_HOST" in src
    assert "127.0.0.1" in src
    # Unauthenticated-by-design routes are called out (TD-008 closure reference).
    assert "Unauthenticated by design" in src
