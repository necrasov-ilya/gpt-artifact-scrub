from __future__ import annotations

import asyncio
import sys
from pathlib import Path


if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.app.main import main  # type: ignore
else:
    from .app.main import main


if __name__ == "__main__":
    asyncio.run(main())
