"""
core/auth.py
============
Centralised credential management for the Clinical Chart Extractor.

This module is the SINGLE SOURCE OF TRUTH for all Gemini authentication.
No other file should perform credential validation or format checks.

Design principles (per Production Change Request):
  - Format-agnostic: accepts ANY non-empty credential Google issues.
  - Runtime validation: Google's endpoint is the authority, not local rules.
  - Never logs the credential itself; masks secrets in all outputs.
  - Surfaces Google's actual HTTP response on failure.
  - Backward compatible: AIzaSy, AQ., and future formats all work unchanged.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

logger = logging.getLogger(__name__)

# ── Minimum sanity: anything shorter is obviously not a credential ────────────
_MIN_CREDENTIAL_LENGTH = 10


# ─────────────────────────────────────────────────────────────────────────────
# Auth Status Enum
# ─────────────────────────────────────────────────────────────────────────────

class AuthStatus(Enum):
    """Possible states of a Gemini credential."""
    UNTESTED   = auto()   # Credential loaded but not yet verified with Google
    HEALTHY    = auto()   # Google confirmed the credential is valid
    FAILED     = auto()   # Google rejected the credential
    NETWORK_ERROR = auto()# Could not reach Google's servers
    MISSING    = auto()   # No credential supplied


# ─────────────────────────────────────────────────────────────────────────────
# Auth Result — returned from every auth operation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AuthResult:
    """
    Structured result from a credential verification attempt.

    Attributes
    ----------
    status : AuthStatus
        Machine-readable outcome of the authentication check.
    message : str
        Human-readable primary status message.
    google_error : str | None
        The raw error string returned by Google's API, if applicable.
        Always populated when status is FAILED.
    http_status : int | None
        HTTP status code from Google's response (e.g., 401, 403, 429).
    request_id : str | None
        Google's request ID, useful for support escalation.
    latency_ms : float | None
        Round-trip time to Google's servers in milliseconds.
    masked_credential : str
        Safely masked representation of the credential for logging.
        Never contains the actual secret.
    """
    status:             AuthStatus
    message:            str
    google_error:       Optional[str]  = None
    http_status:        Optional[int]  = None
    request_id:         Optional[str]  = None
    latency_ms:         Optional[float] = None
    masked_credential:  str            = ""

    @property
    def is_healthy(self) -> bool:
        return self.status == AuthStatus.HEALTHY

    @property
    def is_missing(self) -> bool:
        return self.status == AuthStatus.MISSING

    def __str__(self) -> str:
        parts = [f"AuthResult(status={self.status.name}"]
        if self.http_status:
            parts.append(f"http={self.http_status}")
        if self.latency_ms is not None:
            parts.append(f"latency={self.latency_ms:.0f}ms")
        parts.append(f"credential={self.masked_credential})")
        return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Credential Manager — the single authority for all auth operations
# ─────────────────────────────────────────────────────────────────────────────

class CredentialManager:
    """
    Centralised handler for Gemini API credentials.

    Responsibilities (per production change request):
      1. Load and normalise the credential (trim whitespace only).
      2. Store securely in memory (never persisted to disk here).
      3. Initialise the Gemini client.
      4. Execute a lightweight connection test against Google's API.
      5. Surface Google's actual response on failure.
      6. Log auth events without ever logging the secret.

    Format-agnostic by design:
      This class performs NO prefix checking (no 'AIza', no 'AQ.' logic).
      The ONLY local validation is: non-empty and above minimum length.
      Everything else is delegated to Google's authentication service.
    """

    # Lightweight probe prompt — minimal tokens, fast response
    _PROBE_PROMPT = "Reply with one word: OK"
    _PROBE_MODEL  = "gemini-2.5-flash"

    def __init__(self, credential: str) -> None:
        """
        Parameters
        ----------
        credential : str
            The raw credential string from the user or environment.
            May be any format Google currently issues (AIzaSy, AQ., etc.).
        """
        self._raw: str = credential

    # ── Public API ─────────────────────────────────────────────────────────

    def validate(self) -> AuthResult:
        """
        Validate the credential by making a lightweight request to Google.

        Returns
        -------
        AuthResult
            Full structured result. Check `.is_healthy` for pass/fail.
            On failure, `.google_error` contains Google's actual message.
        """
        masked = self._mask(self._raw)

        # ── Step 1: Minimal local sanity (whitespace + length only) ──────────
        normalised = self._raw.strip()
        if not normalised:
            logger.warning("Auth: empty credential supplied.")
            return AuthResult(
                status=AuthStatus.MISSING,
                message="No credential supplied. Paste your Gemini API credential.",
                masked_credential=masked,
            )

        if len(normalised) < _MIN_CREDENTIAL_LENGTH:
            logger.warning("Auth: credential too short (%d chars).", len(normalised))
            return AuthResult(
                status=AuthStatus.FAILED,
                message=(
                    f"Credential is too short ({len(normalised)} characters). "
                    "Please paste the complete credential from Google AI Studio."
                ),
                masked_credential=masked,
            )

        # ── Step 2: Initialise Gemini client ─────────────────────────────────
        logger.info("Auth: initialising Gemini client. credential=%s", masked)
        try:
            genai.configure(api_key=normalised)
            model = genai.GenerativeModel(self._PROBE_MODEL)
        except Exception as exc:
            logger.error("Auth: client initialisation failed. credential=%s error=%s",
                         masked, exc)
            return AuthResult(
                status=AuthStatus.FAILED,
                message="Failed to initialise Gemini client.",
                google_error=str(exc),
                masked_credential=masked,
            )

        # ── Step 3: Send minimal probe request ────────────────────────────────
        logger.info("Auth: sending probe request. credential=%s", masked)
        t_start = time.perf_counter()
        try:
            response = model.generate_content(self._PROBE_PROMPT)
            latency_ms = (time.perf_counter() - t_start) * 1000

            logger.info(
                "Auth: probe succeeded. credential=%s latency=%.0fms",
                masked, latency_ms,
            )
            return AuthResult(
                status=AuthStatus.HEALTHY,
                message="Credential verified. Google authentication successful.",
                latency_ms=latency_ms,
                masked_credential=masked,
            )

        except google_exceptions.NotFound as exc:
            # Model 404 NotFound — probe fallback models
            logger.warning("Auth probe: 404 NotFound on %s. Probing fallbacks...", self._PROBE_MODEL)
            for fallback_model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
                if fallback_model == self._PROBE_MODEL:
                    continue
                try:
                    fb = genai.GenerativeModel(fallback_model)
                    fb.generate_content(self._PROBE_PROMPT)
                    latency_ms = (time.perf_counter() - t_start) * 1000
                    return AuthResult(
                        status=AuthStatus.HEALTHY,
                        message=f"Credential verified (using {fallback_model}).",
                        latency_ms=latency_ms,
                        masked_credential=masked,
                    )
                except Exception:
                    pass
            latency_ms = (time.perf_counter() - t_start) * 1000
            return AuthResult(
                status=AuthStatus.FAILED,
                message="HTTP Status: 404 Not Found. The Gemini API endpoint or model is not enabled for this credential.",
                google_error=str(exc),
                http_status=404,
                latency_ms=latency_ms,
                masked_credential=masked,
            )

        except google_exceptions.Unauthenticated as exc:
            latency_ms = (time.perf_counter() - t_start) * 1000
            google_msg = _extract_google_message(exc)
            logger.error(
                "Auth: FAILED — Unauthenticated. credential=%s http=401 "
                "latency=%.0fms google_error=%s",
                masked, latency_ms, google_msg,
            )
            return AuthResult(
                status=AuthStatus.FAILED,
                message=_build_auth_failure_message(401, google_msg),
                google_error=google_msg,
                http_status=401,
                latency_ms=latency_ms,
                masked_credential=masked,
            )

        except google_exceptions.PermissionDenied as exc:
            latency_ms = (time.perf_counter() - t_start) * 1000
            google_msg = _extract_google_message(exc)
            logger.error(
                "Auth: FAILED — PermissionDenied. credential=%s http=403 "
                "latency=%.0fms google_error=%s",
                masked, latency_ms, google_msg,
            )
            return AuthResult(
                status=AuthStatus.FAILED,
                message=_build_auth_failure_message(403, google_msg),
                google_error=google_msg,
                http_status=403,
                latency_ms=latency_ms,
                masked_credential=masked,
            )

        except google_exceptions.ResourceExhausted as exc:
            latency_ms = (time.perf_counter() - t_start) * 1000
            google_msg = _extract_google_message(exc)
            logger.warning(
                "Auth: quota/rate-limit hit during probe. credential=%s "
                "http=429 latency=%.0fms",
                masked, latency_ms,
            )
            # 429 means the credential IS valid but quota is exhausted
            return AuthResult(
                status=AuthStatus.HEALTHY,
                message=(
                    "Credential appears valid (Google returned 429 Rate Limit). "
                    "Wait a moment and try again."
                ),
                google_error=google_msg,
                http_status=429,
                latency_ms=latency_ms,
                masked_credential=masked,
            )

        except (
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
        ) as exc:
            latency_ms = (time.perf_counter() - t_start) * 1000
            google_msg = _extract_google_message(exc)
            logger.warning(
                "Auth: network/service error. credential=%s latency=%.0fms "
                "google_error=%s",
                masked, latency_ms, google_msg,
            )
            return AuthResult(
                status=AuthStatus.NETWORK_ERROR,
                message=(
                    "Could not reach Google's servers. "
                    "Check your internet connection and try again."
                ),
                google_error=google_msg,
                latency_ms=latency_ms,
                masked_credential=masked,
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - t_start) * 1000
            google_msg = str(exc)
            logger.error(
                "Auth: unexpected error. credential=%s latency=%.0fms error=%s",
                masked, latency_ms, google_msg,
                exc_info=True,
            )
            return AuthResult(
                status=AuthStatus.FAILED,
                message="An unexpected error occurred during authentication.",
                google_error=google_msg,
                latency_ms=latency_ms,
                masked_credential=masked,
            )

    def get_normalised(self) -> str:
        """Return the whitespace-stripped credential (never logs it)."""
        return self._raw.strip()

    # ── Private Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _mask(credential: str) -> str:
        """
        Return a safely masked representation of the credential.
        Shows first 4 chars and last 2 chars only.
        Example: 'AIzaSyXXXX...XX'  →  'AIza**...**XX'
        """
        s = credential.strip() if credential else ""
        if len(s) <= 8:
            return "****"
        return f"{s[:4]}{'*' * min(8, len(s) - 6)}..{s[-2:]}"


# ─────────────────────────────────────────────────────────────────────────────
# Module-Level Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_google_message(exc: Exception) -> str:
    """Extract the most useful error description from a Google API exception."""
    msg = str(exc)
    # gRPC exceptions often have a structured message; return it as-is.
    return msg.strip() if msg else repr(exc)


def _build_auth_failure_message(http_status: int, google_error: str) -> str:
    """
    Build a structured, actionable authentication failure message.
    Surfaces Google's actual response rather than generic placeholders.
    """
    status_label = {
        401: "401 Unauthorized",
        403: "403 Forbidden",
    }.get(http_status, str(http_status))

    return (
        f"Authentication failed. Google rejected the supplied credential.\n\n"
        f"**HTTP Status:** {status_label}\n\n"
        f"**Possible causes:**\n"
        f"- Invalid or malformed credential\n"
        f"- Credential has been revoked or expired\n"
        f"- Wrong Google Cloud project\n"
        f"- Gemini API not enabled for this project\n"
        f"- Billing or quota issue on the Google account\n\n"
        f"**Google's response:**\n```\n{google_error}\n```\n\n"
        f"Generate a new credential at: https://aistudio.google.com/app/apikey"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Convenience function — used by llm_engine and app.py
# ─────────────────────────────────────────────────────────────────────────────

def configure_gemini(credential: str) -> None:
    """
    Configure the global Gemini client with the provided credential.
    No prefix checks. No format assumptions.

    Parameters
    ----------
    credential : str
        Any credential Google AI Studio currently issues.
    """
    genai.configure(api_key=credential.strip())
    logger.debug(
        "Gemini client configured. credential=%s",
        CredentialManager._mask(credential),
    )
