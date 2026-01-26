"""获取配置的端口号."""
import sys
from pydantic import ValidationError
from app.config import get_settings

if __name__ == "__main__":
    try:
        settings = get_settings()
        print(settings.app_port, end="")
    except ValidationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
