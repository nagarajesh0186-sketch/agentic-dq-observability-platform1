"""Unit tests for application settings."""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch


class TestSettings:
    def test_default_model(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            from configs.settings import GeminiSettings
            settings = GeminiSettings()
            assert settings.model == "gemini-1.5-flash"

    def test_default_log_level(self):
        from configs.settings import AppSettings
        settings = AppSettings()
        assert settings.log_level in ("INFO", "DEBUG", "WARNING", "ERROR")

    def test_get_settings_cached(self):
        from configs.settings import get_settings
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_email_to_email_list_parsing(self):
        with patch.dict(
            os.environ,
            {"ALERT_EMAIL_TO": "a@b.com,c@d.com,e@f.com"},
            clear=False,
        ):
            from configs.settings import EmailSettings
            settings = EmailSettings()
            assert len(settings.to_email_list) == 3
            assert "a@b.com" in settings.to_email_list
