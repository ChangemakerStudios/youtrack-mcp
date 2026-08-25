"""Unit tests for main.py transport helpers (Compose vs docker -i)."""

import stat
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import main as mcp_main


class TestStdinDetection:
    @pytest.mark.unit
    def test_fifo_is_mcp_client(self):
        fake_stat = SimpleNamespace(st_mode=stat.S_IFIFO)
        with patch.object(mcp_main.os, "fstat", return_value=fake_stat), patch.object(
            mcp_main.sys.stdin, "fileno", return_value=0
        ):
            assert mcp_main._stdin_is_mcp_client() is True
            assert mcp_main._should_fallback_to_http() is False

    @pytest.mark.unit
    def test_tty_stays_stdio(self):
        fake_stat = SimpleNamespace(st_mode=stat.S_IFCHR)
        with patch.object(mcp_main.os, "fstat", return_value=fake_stat), patch.object(
            mcp_main.sys.stdin, "fileno", return_value=0
        ), patch.object(mcp_main.sys.stdin, "isatty", return_value=True):
            assert mcp_main._stdin_is_mcp_client() is False
            assert mcp_main._should_fallback_to_http() is False

    @pytest.mark.unit
    def test_detached_stdin_falls_back(self):
        # /dev/null in docker compose: not a fifo, not a tty
        fake_stat = SimpleNamespace(st_mode=stat.S_IFCHR)
        with patch.object(mcp_main.os, "fstat", return_value=fake_stat), patch.object(
            mcp_main.sys.stdin, "fileno", return_value=0
        ), patch.object(mcp_main.sys.stdin, "isatty", return_value=False):
            assert mcp_main._should_fallback_to_http() is True

    @pytest.mark.unit
    def test_normalize_http_alias(self):
        assert mcp_main._normalize_transport("http") == "streamable-http"
        assert mcp_main._normalize_transport("stdio") == "stdio"
