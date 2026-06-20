import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from simulation.events import ReplayEntry


class ReplayRecorder:
    def __init__(self, log_dir: str = "logs") -> None:
        self.log_dir = Path(log_dir)
        self.entries: List[ReplayEntry] = []
        self.run_id: Optional[str] = None

    def record(self, entry: ReplayEntry) -> None:
        """Record a single replay event."""
        self.entries.append(entry)

    def save(
        self,
        run_id: Optional[str] = None,
        manifest: Optional[Dict[str, Any]] = None,
    ) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or self._generate_replay_id()
        file_path = self.log_dir / f"{self.run_id}.jsonl"

        try:
            with file_path.open("w", encoding="utf-8") as f:
                for entry in self.entries:
                    entry_dict = entry.to_dict()
                    f.write(json.dumps(entry_dict, default=str, ensure_ascii=False) + "\n")

            # The manifest is written as a sidecar so the JSONL body stays
            # backward compatible with existing replay parsers.
            if manifest is not None:
                manifest_path = self.log_dir / f"{self.run_id}.manifest.json"
                with manifest_path.open("w", encoding="utf-8") as mf:
                    json.dump(manifest, mf, default=str, ensure_ascii=False, indent=2)

            return file_path

        except Exception as e:
            raise RuntimeError(f"Failed to save replay to {file_path}: {e}") from e

    def save_summary(self, run_id: str, summary: Dict[str, Any]) -> Path:
        """Persist the run summary as a sidecar next to the replay.

        Additive and backward compatible: the JSONL body and manifest sidecar
        are untouched.
        """
        self.log_dir.mkdir(parents=True, exist_ok=True)
        summary_path = self.log_dir / f"{run_id}.summary.json"
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, default=str, ensure_ascii=False, indent=2)
        return summary_path

    def clear(self) -> None:
        """Clear all recorded entries (useful for new simulations)."""
        self.entries.clear()

    def get_entries(self) -> List[ReplayEntry]:
        """Return all recorded entries."""
        return self.entries.copy()

    def _generate_replay_id(self) -> str:
        return "replay"

    def __len__(self) -> int:
        """Return number of recorded events."""
        return len(self.entries)
