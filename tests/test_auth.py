"""
tests/test_auth.py
==================
Automated tests for core.auth.CredentialManager.

Covers all acceptance criteria from the production change request:
  ✓ Legacy AIzaSy credential accepted (format-agnostic pass-through).
  ✓ Modern AQ. credential accepted (no prefix rejection).
  ✓ Empty credential rejected locally (before hitting Google).
  ✓ Whitespace-only credential rejected locally.
  ✓ Invalid credential correctly reports Google's authentication error.
  ✓ Revoked credential handled gracefully.
  ✓ Network failure distinguished from authentication failure.
  ✓ Credential is never logged in plain text.

Run: pytest tests/test_auth.py -v
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Ensure project root is importable ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.auth import (
    CredentialManager,
    AuthStatus,
    AuthResult,
    _build_auth_failure_message,
    _extract_google_message,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

FAKE_AIZA_KEY = "AIzaSyFakeKeyForTestingPurposesOnly1234"
FAKE_AQ_KEY   = "AQ.Ab8RN6llPxWcSoaAmQq7ecj4Gj5tlhlY3uJgIFake"
FAKE_FUTURE   = "FUTURE_FORMAT.SomethingGoogleMightIssueLater"


def _mock_healthy_response():
    """A mock Gemini response that looks healthy."""
    mock = MagicMock()
    mock.text = "OK"
    return mock


# ═══════════════════════════════════════════════════════════════════════════
# Test Group 1: Credential Format Acceptance
# Verifies format-agnostic behaviour — NO prefix assumptions.
# ═══════════════════════════════════════════════════════════════════════════

class TestCredentialFormatAcceptance:
    """
    Requirement: The application must accept ANY non-empty credential.
    No prefix checking against 'AIza' or 'AQ.' or any other pattern.
    """

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_legacy_aiza_credential_accepted(self, mock_configure, mock_model_cls):
        """✓ Legacy AIzaSy credential passes through without rejection."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_healthy_response()
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AIZA_KEY)
        result  = manager.validate()

        assert result.status == AuthStatus.HEALTHY, (
            f"Legacy AIzaSy key was rejected. Status: {result.status}. "
            f"Message: {result.message}"
        )
        mock_configure.assert_called_once_with(api_key=FAKE_AIZA_KEY)

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_modern_aq_credential_accepted(self, mock_configure, mock_model_cls):
        """✓ Modern AQ. credential passes through without rejection."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_healthy_response()
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AQ_KEY)
        result  = manager.validate()

        assert result.status == AuthStatus.HEALTHY, (
            f"AQ. credential was rejected locally (should only be rejected by Google). "
            f"Status: {result.status}. Message: {result.message}"
        )
        mock_configure.assert_called_once_with(api_key=FAKE_AQ_KEY)

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_future_format_credential_accepted(self, mock_configure, mock_model_cls):
        """✓ Unknown future credential formats pass through without rejection."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_healthy_response()
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_FUTURE)
        result  = manager.validate()

        # Should attempt Google auth, not locally reject
        assert result.status in (AuthStatus.HEALTHY, AuthStatus.FAILED), (
            "Future-format credential should reach Google, not be locally rejected. "
            f"Status: {result.status}"
        )
        mock_configure.assert_called_once()

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_whitespace_is_stripped(self, mock_configure, mock_model_cls):
        """✓ Leading/trailing whitespace is normalised before use."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_healthy_response()
        mock_model_cls.return_value = mock_model

        padded = f"  {FAKE_AIZA_KEY}  "
        manager = CredentialManager(padded)
        result  = manager.validate()

        # configure should receive the stripped key
        mock_configure.assert_called_once_with(api_key=FAKE_AIZA_KEY)
        assert result.status == AuthStatus.HEALTHY


# ═══════════════════════════════════════════════════════════════════════════
# Test Group 2: Local Sanity Checks (Before Hitting Google)
# ═══════════════════════════════════════════════════════════════════════════

class TestLocalSanityChecks:
    """
    Only empty and whitespace-only credentials are rejected locally.
    Everything else is forwarded to Google.
    """

    def test_empty_credential_rejected(self):
        """✓ Empty string is rejected without hitting Google."""
        manager = CredentialManager("")
        result  = manager.validate()

        assert result.status == AuthStatus.MISSING
        assert result.is_missing

    def test_whitespace_only_credential_rejected(self):
        """✓ Whitespace-only string is rejected without hitting Google."""
        for blank in ("   ", "\t", "\n", "  \t  \n  "):
            manager = CredentialManager(blank)
            result  = manager.validate()
            assert result.status == AuthStatus.MISSING, (
                f"Whitespace-only credential '{repr(blank)}' should be rejected. "
                f"Got: {result.status}"
            )

    def test_very_short_credential_rejected(self):
        """✓ Credentials below minimum length are rejected without network call."""
        manager = CredentialManager("abc")
        result  = manager.validate()

        assert result.status == AuthStatus.FAILED
        assert "short" in result.message.lower() or "length" in result.message.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Test Group 3: Google Authentication Failure Handling
# ═══════════════════════════════════════════════════════════════════════════

class TestGoogleAuthenticationFailures:
    """
    Verifies that Google's actual error is surfaced on rejection.
    The application must not invent its own error messages.
    """

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_invalid_credential_reports_google_error(self, mock_configure, mock_model_cls):
        """✓ Invalid credential correctly reports Google's authentication error."""
        from google.api_core.exceptions import Unauthenticated

        google_error_msg = (
            "401 Request had invalid authentication credentials. "
            "reason: ACCESS_TOKEN_TYPE_UNSUPPORTED"
        )
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Unauthenticated(google_error_msg)
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AQ_KEY)
        result  = manager.validate()

        assert result.status == AuthStatus.FAILED
        assert result.http_status == 401
        assert result.google_error is not None
        assert "401" in result.google_error or "unauthenticated" in result.google_error.lower()

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_revoked_credential_handled_gracefully(self, mock_configure, mock_model_cls):
        """✓ Revoked credential is reported as FAILED, not a crash."""
        from google.api_core.exceptions import Unauthenticated

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Unauthenticated(
            "401 Credentials have been revoked."
        )
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AIZA_KEY)
        result  = manager.validate()

        assert result.status == AuthStatus.FAILED
        assert not result.is_healthy
        # Should not raise — returns structured result

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_permission_denied_403(self, mock_configure, mock_model_cls):
        """✓ 403 PermissionDenied is reported as FAILED with correct http_status."""
        from google.api_core.exceptions import PermissionDenied

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = PermissionDenied(
            "403 The caller does not have permission."
        )
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AIZA_KEY)
        result  = manager.validate()

        assert result.status == AuthStatus.FAILED
        assert result.http_status == 403

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_rate_limit_429_treated_as_healthy(self, mock_configure, mock_model_cls):
        """✓ 429 Rate Limit means credential IS valid; treated as HEALTHY."""
        from google.api_core.exceptions import ResourceExhausted

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = ResourceExhausted(
            "429 Quota exceeded."
        )
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AIZA_KEY)
        result  = manager.validate()

        # 429 means credential is valid — quota issue, not auth issue
        assert result.status == AuthStatus.HEALTHY
        assert result.http_status == 429


# ═══════════════════════════════════════════════════════════════════════════
# Test Group 4: Network Error Distinction
# ═══════════════════════════════════════════════════════════════════════════

class TestNetworkErrorDistinction:
    """
    Network failures must be clearly distinguished from auth failures.
    """

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_network_failure_distinguished_from_auth_failure(
        self, mock_configure, mock_model_cls
    ):
        """✓ Network failure returns NETWORK_ERROR, not FAILED."""
        from google.api_core.exceptions import ServiceUnavailable

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = ServiceUnavailable("503 Service Unavailable.")
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AIZA_KEY)
        result  = manager.validate()

        assert result.status == AuthStatus.NETWORK_ERROR, (
            f"Network error should return NETWORK_ERROR, got {result.status}"
        )

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_timeout_is_network_error(self, mock_configure, mock_model_cls):
        """✓ DeadlineExceeded is a network error, not an auth failure."""
        from google.api_core.exceptions import DeadlineExceeded

        mock_model = MagicMock()
        mock_model.generate_content.side_effect = DeadlineExceeded("504 Deadline exceeded.")
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AIZA_KEY)
        result  = manager.validate()

        assert result.status == AuthStatus.NETWORK_ERROR


# ═══════════════════════════════════════════════════════════════════════════
# Test Group 5: Secret Masking
# ═══════════════════════════════════════════════════════════════════════════

class TestSecretMasking:
    """
    Credentials must NEVER appear in logs or string representations.
    """

    def test_mask_hides_secret(self):
        """✓ Masked credential does not expose the full secret."""
        mgr    = CredentialManager(FAKE_AIZA_KEY)
        masked = mgr._mask(FAKE_AIZA_KEY)

        assert FAKE_AIZA_KEY not in masked
        assert len(masked) < len(FAKE_AIZA_KEY)
        # Shows only first 4 chars
        assert masked.startswith(FAKE_AIZA_KEY[:4])

    def test_mask_aq_credential(self):
        """✓ AQ. credential is masked the same way as any other."""
        masked = CredentialManager(FAKE_AQ_KEY)._mask(FAKE_AQ_KEY)
        assert FAKE_AQ_KEY not in masked
        assert masked.startswith("AQ.A")

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_auth_result_does_not_contain_secret(self, mock_configure, mock_model_cls):
        """✓ AuthResult.masked_credential never contains the raw secret."""
        mock_model = MagicMock()
        mock_model.generate_content.return_value = _mock_healthy_response()
        mock_model_cls.return_value = mock_model

        manager = CredentialManager(FAKE_AIZA_KEY)
        result  = manager.validate()

        assert FAKE_AIZA_KEY not in result.masked_credential
        assert FAKE_AIZA_KEY not in result.message
        assert FAKE_AIZA_KEY not in str(result)


# ═══════════════════════════════════════════════════════════════════════════
# Test Group 6: No Prefix Assumptions in Code
# ═══════════════════════════════════════════════════════════════════════════

class TestNoPrefixAssumptions:
    """
    Ensure no source files contain obsolete prefix-checking logic.
    """

    FORBIDDEN_PATTERNS = [
        'startswith("AIza")',
        "startswith('AIza')",
        'startswith("AIzaSy")',
        "startswith('AIzaSy')",
        '"AIza" prefix',
        "Expected format: AIza",
        "must begin with AIza",
        "key must start with",
    ]

    SOURCE_FILES = [
        "core/llm_engine.py",
        "core/auth.py",
        "ui/sidebar.py",
        "utils/error_handler.py",
        "config/settings.py",
    ]

    def test_no_aiza_prefix_checks_in_source(self):
        """✓ No source file contains obsolete AIzaSy prefix validation logic."""
        root = Path(__file__).resolve().parent.parent
        violations = []

        for rel_path in self.SOURCE_FILES:
            fpath = root / rel_path
            if not fpath.exists():
                continue
            content = fpath.read_text(encoding="utf-8")
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern in content:
                    violations.append(f"{rel_path}: found '{pattern}'")

        assert not violations, (
            "Obsolete prefix-based validation found in source files:\n"
            + "\n".join(violations)
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test Group 7: auth_failure_message quality
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthFailureMessages:
    """Error messages must surface Google's response, not generic placeholders."""

    def test_failure_message_includes_http_status(self):
        msg = _build_auth_failure_message(401, "Unauthenticated")
        assert "401" in msg

    def test_failure_message_includes_google_error(self):
        google_err = "reason: ACCESS_TOKEN_TYPE_UNSUPPORTED"
        msg = _build_auth_failure_message(401, google_err)
        assert google_err in msg

    def test_failure_message_no_prefix_hints(self):
        """Error message must not tell users to use AIza keys specifically."""
        msg = _build_auth_failure_message(401, "some error")
        assert "AIza" not in msg
        assert "starts with" not in msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
