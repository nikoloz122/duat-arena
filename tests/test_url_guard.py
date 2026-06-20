import socket
import unittest
from unittest.mock import patch

from backend.core.url_guard import validate_public_url


def _addrinfo(ip: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 443))]


class UrlGuardTests(unittest.TestCase):
    def test_accepts_public_https(self) -> None:
        with patch(
            "backend.core.url_guard.socket.getaddrinfo",
            return_value=_addrinfo("93.184.216.34"),
        ):
            self.assertEqual(
                validate_public_url("https://example.com/decide"),
                "https://example.com/decide",
            )

    def test_accepts_public_host_with_private_looking_name(self) -> None:
        # Public IP wins regardless of the hostname spelling.
        with patch(
            "backend.core.url_guard.socket.getaddrinfo",
            return_value=_addrinfo("8.8.8.8"),
        ):
            self.assertTrue(validate_public_url("https://my-agent.io/decide"))

    def test_rejects_localhost(self) -> None:
        with patch(
            "backend.core.url_guard.socket.getaddrinfo",
            return_value=_addrinfo("127.0.0.1"),
        ):
            with self.assertRaises(ValueError):
                validate_public_url("http://localhost/decide")

    def test_rejects_literal_loopback(self) -> None:
        # Numeric hosts resolve without any network call.
        with self.assertRaises(ValueError):
            validate_public_url("http://127.0.0.1:8000/decide")

    def test_rejects_private_ip(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_url("http://10.0.0.5/decide")

    def test_rejects_private_192(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_url("http://192.168.1.10/decide")

    def test_rejects_metadata_ip(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_url("http://169.254.169.254/latest/meta-data")

    def test_rejects_bad_scheme(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_url("ftp://example.com/decide")

    def test_rejects_missing_host(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_url("https:///decide")

    def test_rejects_unresolvable_host(self) -> None:
        with patch(
            "backend.core.url_guard.socket.getaddrinfo",
            side_effect=socket.gaierror("name resolution failed"),
        ):
            with self.assertRaises(ValueError):
                validate_public_url("https://nope.invalid/decide")

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            validate_public_url("")


if __name__ == "__main__":
    unittest.main()
