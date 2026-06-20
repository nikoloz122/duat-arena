import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReplayNotFoundError(FileNotFoundError):
    """Raised when a replay file is not found."""
    pass


@dataclass
class ReplayMetadata:
    """Metadata for a replay."""
    replay_id: str
    total_events: int
    simulation_duration_seconds: float
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    final_market_state: Optional[Dict[str, Any]] = None


class ReplayParser:
    """
    Professional replay parser for DUAT Arena.
    Handles loading, validating, and shaping replay data from JSONL files.
    """

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)

    def load(self, replay_id: str) -> Dict[str, Any]:
        """
        Load a replay by ID and return structured data with metadata and timeline.
        """
        file_path = self._get_replay_path(replay_id)

        if not file_path.exists():
            raise ReplayNotFoundError(f"Replay '{replay_id}' not found at {file_path}")

        events = self._read_jsonl(file_path)
        if not events:
            return self._empty_replay(replay_id)

        # Sort events by timestamp and tick for correct timeline
        sorted_events = sorted(
            events,
            key=lambda e: (e.get("timestamp", ""), e.get("tick", 0))
        )

        timeline = [self._shape_event(event) for event in sorted_events]

        metadata = self._build_metadata(replay_id, timeline)
        return {
            "replay_id": replay_id,
            "total_events": metadata.total_events,
            "simulation_duration": metadata.simulation_duration_seconds,
            "final_market_state": metadata.final_market_state,
            "start_time": metadata.start_time,
            "end_time": metadata.end_time,
            "manifest": self._load_manifest(replay_id),
            "run_summary": self._load_sidecar(replay_id, "summary"),
            "events": timeline,
            "summary": self._build_summary(timeline),
        }

    def _load_manifest(self, replay_id: str) -> Optional[Dict[str, Any]]:
        """Load the manifest sidecar if present. Old replays simply have none."""
        return self._load_sidecar(replay_id, "manifest")

    def _load_sidecar(self, replay_id: str, suffix: str) -> Optional[Dict[str, Any]]:
        """Load a {replay_id}.{suffix}.json sidecar, or None if missing/malformed."""
        sidecar_path = self.log_dir / f"{replay_id}.{suffix}.json"
        if not sidecar_path.exists():
            return None
        try:
            with sidecar_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    def _get_replay_path(self, replay_id: str) -> Path:
        """Validate and return full path to replay file."""
        if not replay_id or not replay_id.replace("-", "").replace("_", "").replace("t", "").isalnum():
            raise ValueError("Invalid replay_id format. Use alphanumeric, hyphen and underscore only.")

        return self.log_dir / f"{replay_id}.jsonl"

    def _read_jsonl(self, path: Path) -> List[Dict[str, Any]]:
        """Read JSONL file safely."""
        events: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            print(f"Warning: Malformed JSON at line {line_num} in {path.name}")
        except Exception as e:
            raise IOError(f"Failed to read replay file {path}: {e}") from e

        return events

    def _shape_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Shape event for frontend/display."""
        action = event.get("action")
        shaped = {
            "timestamp": event.get("timestamp"),
            "tick": event.get("tick"),
            "agent": event.get("agent"),
            "action": action,
            "reason": event.get("reason", ""),
            "market_state": event.get("market_state"),
            "scenario_event": event.get("scenario_event"),
            "portfolio_state": event.get("portfolio_state", {}),
            "behavior_counters": event.get("behavior_counters", {}),
            # Phase 1 hardening fields. Old replays (missing or empty) fall
            # back to `action`.
            "intended_action": event.get("intended_action") or action,
            "executed_action": event.get("executed_action") or action,
            "normalization_notes": event.get("normalization_notes") or [],
        }
        llm_diag = event.get("llm_decide_diagnostics")
        if llm_diag is not None:
            shaped["llm_decide_diagnostics"] = llm_diag
        return shaped

    def _build_metadata(self, replay_id: str, events: List[Dict]) -> ReplayMetadata:
        """Build metadata for the replay."""
        if not events:
            return ReplayMetadata(replay_id=replay_id, total_events=0, simulation_duration_seconds=0.0)

        start = events[0].get("timestamp")
        end = events[-1].get("timestamp")

        duration = 0.0
        try:
            if start and end:
                start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
                duration = max(0.0, (end_dt - start_dt).total_seconds())
        except ValueError:
            pass

        return ReplayMetadata(
            replay_id=replay_id,
            total_events=len(events),
            simulation_duration_seconds=round(duration, 2),
            start_time=start,
            end_time=end,
            final_market_state=events[-1].get("market_state") if events else None,
        )

    def _build_summary(self, events: List[Dict]) -> Dict[str, Any]:
        """Build high-level summary."""
        if not events:
            return {}

        actions = [e.get("action") for e in events if e.get("action")]
        sell_count = sum(1 for action in actions if action == "sell")

        return {
            "total_actions": len(actions),
            "sell_count": sell_count,
            "unique_agents": len(set(e.get("agent") for e in events if e.get("agent"))),
        }

    def _empty_replay(self, replay_id: str) -> Dict[str, Any]:
        """Return empty replay structure."""
        return {
            "replay_id": replay_id,
            "total_events": 0,
            "simulation_duration": 0.0,
            "final_market_state": None,
            "start_time": None,
            "end_time": None,
            "events": [],
            "summary": {},
        }


def load_replay(replay_id: str, log_dir: str = "logs") -> Dict[str, Any]:
    return ReplayParser(log_dir=log_dir).load(replay_id)


def load_run_summary(replay_id: str, log_dir: str = "logs") -> Optional[Dict[str, Any]]:
    """Load the persisted run summary sidecar, or None if it does not exist."""
    return ReplayParser(log_dir=log_dir)._load_sidecar(replay_id, "summary")


def list_runs(log_dir: str = "logs") -> List[Dict[str, Any]]:
    """List available runs (one per replay JSONL) with brief metadata.

    Metadata is derived from the run summary sidecar when present. Runs without
    a summary still appear with minimal info.
    """
    directory = Path(log_dir)
    if not directory.exists():
        return []

    runs: List[Dict[str, Any]] = []
    for replay_file in sorted(directory.glob("*.jsonl")):
        replay_id = replay_file.stem
        summary = load_run_summary(replay_id, log_dir=log_dir)
        runs.append(_summarize_run(replay_id, summary))
    return runs


def _summarize_run(replay_id: str, summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "replay_id": replay_id,
        "scenario": None,
        "agent_count": 0,
        "best_agent_id": None,
        "best_score": None,
        "best_grade": None,
    }
    if not summary:
        return info

    info["scenario"] = summary.get("scenario")
    info["agent_count"] = len(summary.get("agents", []) or [])

    reliability = summary.get("reliability_reports", []) or []
    if reliability:
        best = max(reliability, key=lambda r: r.get("score", 0.0))
        info["best_agent_id"] = best.get("agent_id")
        info["best_score"] = best.get("score")
        info["best_grade"] = best.get("grade")
    return info