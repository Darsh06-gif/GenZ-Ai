from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    data_dir: Path
    db_path: Path

    def ensure(self) -> "AppPaths":
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self


def get_paths() -> AppPaths:
    root = Path(__file__).resolve().parents[2]
    data_dir = root / "data"
    db_path = data_dir / "notes.db"
    return AppPaths(project_root=root, data_dir=data_dir, db_path=db_path).ensure()

