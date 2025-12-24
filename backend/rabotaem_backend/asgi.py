import os
from pathlib import Path

from django.core.asgi import get_asgi_application

def load_env_fallback(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


base_dir = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(base_dir / ".env")
else:
    load_env_fallback(base_dir / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rabotaem_backend.settings")

application = get_asgi_application()
