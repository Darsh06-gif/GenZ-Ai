from __future__ import annotations

import sys
from pathlib import Path


# Ensure project root is on sys.path when running as a script.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import Db  # type: ignore  # pylint: disable=wrong-import-position
from app.core.paths import get_paths  # type: ignore  # pylint: disable=wrong-import-position


def main() -> None:
    paths = get_paths()
    db = Db(paths.db_path)
    db.migrate()
    print(f"OK: migrated db at {db.path}")


if __name__ == "__main__":
    main()


