import asyncio
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import backend.api.routes as routes_module
from agents.llm_agent import (
    DEFAULT_MODEL,
    LLM_AGENT_ID,
    MODE_REPLAY,
    _anthropic_request,
    _parse_decision,
    build_llm_agent,
    resolve_llm_model,
)
from agents.registry import EXTERNAL, build_default_registry
from backend.api.routes import SimulationRunRequest
from scenarios.flash_crash import FlashCrashScenario
from simulation.engine import SimulationEngine
from simulation.market import MarketState
from simulation.replay import ReplayRecorder
from simulation.replay_parser import load_replay


def _valid_buy_client(model, system, user, timeout):
    return '{"action": "buy", "size": 1.0, "reason": "momentum", "confidence": 0.7}'


def _hallucinated_client(model, system, user, timeout):
    # Valid JSON, invalid action: the boundary must coerce it to hold.
    return '{"action": "ape_in", "size": 3, "reason": "yolo", "confidence": 0.9}'


def _malformed_client(model, system, user, timeout):
    return "Sure! I think you should buy now."  # not JSON


def _fenced_buy_client(model, system, user, timeout):
    # Real models commonly wrap valid JSON in a Markdown code fence.
    return '```json\n{"action": "buy", "size": 3.0, "reason": "momentum", "confidence": 0.8}\n```'


def _raising_client(model, system, user, timeout):
    raise TimeoutError("llm timed out")


def _http_error_client(model, system, user, timeout):
    body = io.BytesIO(b'{"type":"error","message":"model not found"}')
    raise urllib.error.HTTPError(
        "https://api.anthropic.com/v1/messages",
        404,
        "Not Found",
        {},
        body,
    )


def _cache_file(log_dir: str) -> str:
    return str(Path(log_dir) / "llm_cache.json")


def _run(agent, *, ticks=6, log_dir=None):
    return SimulationEngine(
        agents=[agent],
        scenario=FlashCrashScenario(),
        max_ticks=ticks,
        recorder=ReplayRecorder(log_dir=log_dir),
    ).run()


def _replay_body_without_llm_diagnostics(body: str) -> str:
    lines = []
    for line in body.strip().splitlines():
        event = json.loads(line)
        event.pop("llm_decide_diagnostics", None)
        lines.append(json.dumps(event, ensure_ascii=False))
    return "\n".join(lines) + "\n"


class LlmAgentDecisionTests(unittest.TestCase):
    def test_happy_path_keeps_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_valid_buy_client, cache_path=_cache_file(log_dir))
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertEqual(result.ticks, 6)
        self.assertEqual(
            result.reliability_reports[0]["components"]["decision_integrity"], 1.0
        )
        self.assertTrue(all(not e["normalization_notes"] for e in replay["events"]))

    def test_hallucinated_action_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_hallucinated_client, cache_path=_cache_file(log_dir))
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))
        self.assertTrue(all(e["normalization_notes"] for e in replay["events"]))
        self.assertEqual(
            result.reliability_reports[0]["components"]["decision_integrity"], 0.0
        )

    def test_malformed_output_falls_back_to_hold(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_malformed_client, cache_path=_cache_file(log_dir))
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))
        self.assertLess(
            result.reliability_reports[0]["components"]["decision_integrity"], 1.0
        )

    def test_client_error_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_raising_client, cache_path=_cache_file(log_dir))
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertEqual(result.ticks, 6)
        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))

    def test_http_error_logs_reason_without_typeerror(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_http_error_client, cache_path=_cache_file(log_dir))
            with self.assertLogs("agents.llm_agent", level="WARNING") as captured:
                result = _run(agent, ticks=2, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertTrue(any("http_error" in message for message in captured.output))
        self.assertTrue(any("reason='Not Found'" in message for message in captured.output))
        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))


class LlmModelConfigTests(unittest.TestCase):
    def test_default_model_is_supported_haiku_snapshot(self) -> None:
        self.assertEqual(DEFAULT_MODEL, "claude-haiku-4-5-20251001")

    def test_resolve_llm_model_prefers_explicit_argument(self) -> None:
        self.assertEqual(resolve_llm_model("claude-sonnet-4-6"), "claude-sonnet-4-6")

    def test_resolve_llm_model_prefers_env(self) -> None:
        with patch.dict(os.environ, {"DUAT_LLM_MODEL": "claude-sonnet-4-6"}, clear=False):
            self.assertEqual(resolve_llm_model(), "claude-sonnet-4-6")

    def test_resolve_llm_model_falls_back_to_default(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "DUAT_LLM_MODEL"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(resolve_llm_model(), DEFAULT_MODEL)

    @patch("agents.llm_agent.urllib.request.urlopen")
    def test_anthropic_request_sends_exact_model_id_in_body(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"content": [{"type": "text", "text": '{"action": "hold"}'}]}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.assertLogs("agents.llm_agent", level="INFO") as captured:
            _anthropic_request(
                "claude-haiku-4-5-20251001",
                "system prompt",
                "user prompt",
                5.0,
                "test-key",
                256,
            )

        request = mock_urlopen.call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "claude-haiku-4-5-20251001")
        self.assertTrue(
            any("request_body.model=claude-haiku-4-5-20251001" in line for line in captured.output)
        )


class ParseDecisionTests(unittest.TestCase):
    def test_clean_json_object(self) -> None:
        parsed = _parse_decision('{"action": "buy", "size": 1.0}')
        self.assertEqual(parsed, {"action": "buy", "size": 1.0})

    def test_markdown_fenced_json(self) -> None:
        parsed = _parse_decision(
            '```json\n{"action": "sell", "size": 2.0, "reason": "exit"}\n```'
        )
        self.assertEqual(parsed, {"action": "sell", "size": 2.0, "reason": "exit"})

    def test_bare_fenced_json(self) -> None:
        parsed = _parse_decision('```\n{"action": "hold"}\n```')
        self.assertEqual(parsed, {"action": "hold"})

    def test_prose_then_json(self) -> None:
        parsed = _parse_decision(
            'Sure, here is my decision: {"action": "buy", "size": 1.5}. Good luck!'
        )
        self.assertEqual(parsed, {"action": "buy", "size": 1.5})

    def test_braces_inside_string_do_not_break_balance(self) -> None:
        parsed = _parse_decision('{"action": "buy", "reason": "close } brace"}')
        self.assertEqual(parsed, {"action": "buy", "reason": "close } brace"})

    def test_pure_prose_returns_none(self) -> None:
        self.assertIsNone(_parse_decision("I think you should buy now."))

    def test_empty_returns_none(self) -> None:
        self.assertIsNone(_parse_decision(""))
        self.assertIsNone(_parse_decision(None))

    def test_json_array_is_not_a_decision(self) -> None:
        self.assertIsNone(_parse_decision("[1, 2, 3]"))


class LlmAgentFencedOutputTests(unittest.TestCase):
    def test_fenced_json_is_parsed_and_executed(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_fenced_buy_client, cache_path=_cache_file(log_dir))
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        # Fenced JSON now parses cleanly: the agent acts and keeps integrity.
        self.assertTrue(all(not e["normalization_notes"] for e in replay["events"]))
        self.assertEqual(
            result.reliability_reports[0]["components"]["decision_integrity"], 1.0
        )
        self.assertTrue(any(e["intended_action"] == "buy" for e in replay["events"]))


class LlmAgentCacheTests(unittest.TestCase):
    def test_record_then_replay_makes_zero_calls_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as log_a, tempfile.TemporaryDirectory() as log_b:
            cache_path = _cache_file(log_a)

            calls = {"n": 0}

            def counting_client(model, system, user, timeout):
                calls["n"] += 1
                return _valid_buy_client(model, system, user, timeout)

            # First run records responses to the cache.
            agent1 = build_llm_agent(client=counting_client, cache_path=cache_path)
            body1 = Path(_run(agent1, ticks=8, log_dir=log_a).replay_path).read_text(
                encoding="utf-8"
            )
            self.assertGreater(calls["n"], 0)
            calls_after_record = calls["n"]

            # Second run reuses the same cache; the client must never be called.
            def exploding_client(model, system, user, timeout):
                raise AssertionError("client should not be called on a cache hit")

            agent2 = build_llm_agent(client=exploding_client, cache_path=cache_path)
            body2 = Path(_run(agent2, ticks=8, log_dir=log_b).replay_path).read_text(
                encoding="utf-8"
            )

        self.assertEqual(calls["n"], calls_after_record)  # no new calls
        self.assertEqual(
            _replay_body_without_llm_diagnostics(body1),
            _replay_body_without_llm_diagnostics(body2),
        )

    def test_replay_mode_never_calls_api(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            def exploding_client(model, system, user, timeout):
                raise AssertionError("replay mode must not call the API")

            agent = build_llm_agent(
                client=exploding_client, cache_path=_cache_file(log_dir), mode=MODE_REPLAY
            )
            result = _run(agent, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))


class LlmAgentDegradationTests(unittest.TestCase):
    def test_missing_key_and_empty_cache_degrades_to_holds(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            # client=None forces the default path, which requires a key.
            agent = build_llm_agent(client=None, cache_path=_cache_file(log_dir))
            env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            with patch.dict(os.environ, env_without_key, clear=True):
                result = _run(agent, log_dir=log_dir)
                replay = load_replay(result.replay_id, log_dir=log_dir)

        self.assertEqual(result.ticks, 6)
        self.assertTrue(all(e["executed_action"] == "hold" for e in replay["events"]))


class LlmTick0DiagnosticsTests(unittest.TestCase):
    def test_tick0_replay_and_result_include_llm_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_valid_buy_client, cache_path=_cache_file(log_dir))
            result = _run(agent, ticks=3, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        tick0_events = [
            e for e in replay["events"] if e["tick"] == 0 and e["agent"] == LLM_AGENT_ID
        ]
        self.assertEqual(len(tick0_events), 1)
        diag = tick0_events[0]["llm_decide_diagnostics"]
        self.assertIsNotNone(diag)
        self.assertEqual(
            diag["raw_decision"],
            {"action": "buy", "size": 1.0, "reason": "momentum", "confidence": 0.7},
        )
        self.assertEqual(diag["normalization_notes"], [])
        self.assertFalse(diag["cache_hit"])
        self.assertTrue(diag["cache_miss"])
        self.assertFalse(diag["anthropic_api_called"])
        self.assertTrue(diag["parser_succeeded"])
        self.assertNotIn("exception_message", diag)

        result_diag = result.to_dict().get("llm_tick0_diagnostics")
        self.assertEqual(result_diag, diag)

    def test_tick0_diagnostics_capture_no_decision_failure(self) -> None:
        with tempfile.TemporaryDirectory() as log_dir:
            agent = build_llm_agent(client=_malformed_client, cache_path=_cache_file(log_dir))
            result = _run(agent, ticks=2, log_dir=log_dir)
            replay = load_replay(result.replay_id, log_dir=log_dir)

        diag = next(
            e["llm_decide_diagnostics"]
            for e in replay["events"]
            if e["tick"] == 0 and e["agent"] == LLM_AGENT_ID
        )
        self.assertIsNone(diag["raw_decision"])
        self.assertFalse(diag["parser_succeeded"])
        self.assertIn("agent returned no decision", diag["normalization_notes"][0])
        self.assertEqual(diag["exception_message"], "parser_failure")


class LlmAgentRegistryApiTests(unittest.TestCase):
    def test_default_registry_lists_llm_agent(self) -> None:
        agents = asyncio.run(routes_module.list_agents())
        listing = {a["id"]: a for a in agents}
        self.assertIn(LLM_AGENT_ID, listing)
        self.assertEqual(listing[LLM_AGENT_ID]["kind"], EXTERNAL)

    def test_run_via_agent_ids_with_faked_client(self) -> None:
        async def run_flow(log_dir: str):
            registry = build_default_registry()
            registry.register(
                LLM_AGENT_ID,
                lambda: build_llm_agent(
                    client=_valid_buy_client, cache_path=_cache_file(log_dir)
                ),
                kind=EXTERNAL,
            )
            with patch.object(routes_module, "DEFAULT_REGISTRY", registry), patch.object(
                routes_module, "settings", SimpleNamespace(replay_log_dir=log_dir)
            ):
                return await routes_module.run_simulation(
                    SimulationRunRequest(ticks=6, agent_ids=[LLM_AGENT_ID])
                )

        with tempfile.TemporaryDirectory() as log_dir:
            result = asyncio.run(run_flow(log_dir))

        self.assertEqual(result["agents"], [LLM_AGENT_ID])


if __name__ == "__main__":
    unittest.main()
