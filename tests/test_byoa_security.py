import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend.core.rate_limit import SlidingWindowRateLimiter
from backend.core.security import require_arena_api_key
from backend.core.startup import validate_production_config


class RateLimiterTests(unittest.TestCase):
    def test_allows_calls_under_limit(self) -> None:
        limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=60)
        limiter.check("client-a")
        limiter.check("client-a")
        limiter.check("client-a")

    def test_blocks_calls_over_limit(self) -> None:
        limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=60)
        limiter.check("client-a")
        limiter.check("client-a")
        with self.assertRaises(HTTPException) as ctx:
            limiter.check("client-a")
        self.assertEqual(ctx.exception.status_code, 429)


class ArenaApiKeyAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_when_key_not_configured(self) -> None:
        with patch("backend.core.security.settings") as mock_settings:
            mock_settings.arena_api_key = ""
            await require_arena_api_key(None)

    async def test_rejects_missing_header(self) -> None:
        with patch("backend.core.security.settings") as mock_settings:
            mock_settings.arena_api_key = "secret"
            with self.assertRaises(HTTPException) as ctx:
                await require_arena_api_key(None)
            self.assertEqual(ctx.exception.status_code, 401)


class ProductionStartupTests(unittest.TestCase):
    def test_production_requires_keys(self) -> None:
        with patch("backend.core.startup.settings") as mock_settings:
            mock_settings.is_production = True
            mock_settings.byoa_key = ""
            mock_settings.arena_api_key = ""
            with self.assertRaises(RuntimeError):
                validate_production_config()

    def test_development_skips_validation(self) -> None:
        with patch("backend.core.startup.settings") as mock_settings:
            mock_settings.is_production = False
            validate_production_config()


if __name__ == "__main__":
    unittest.main()
