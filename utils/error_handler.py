"""
utils/error_handler.py
======================
Centralised exception management for the Clinical Chart Extractor.

Per production change request:
  - No prefix-based error classification (no 'AIza', no 'AQ.' logic here).
  - Surfaces Google's ACTUAL error response wherever possible.
  - Provides actionable diagnostics, not generic placeholders.
  - Distinguishes authentication failure from network failure.
"""

from __future__ import annotations
import logging
import streamlit as st

logger = logging.getLogger(__name__)


def handle_extraction_error(exc: Exception, context: str = "") -> None:
    """
    Display a contextual, actionable error message in the Streamlit UI.
    Surfaces Google's actual API response when available. Does NOT crash.

    Parameters
    ----------
    exc : Exception
        The caught exception.
    context : str
        Optional context string for more specific error messaging.
    """
    error_str    = str(exc)
    error_lower  = error_str.lower()

    # ── Authentication / Credential Errors (401) ──────────────────────────────
    # Catches: Unauthenticated, ACCESS_TOKEN_TYPE_UNSUPPORTED, invalid credential
    # Does NOT assume any key format — shows Google's actual response.
    if (
        "unauthenticated" in error_lower
        or "401"          in error_str
        or "access_token_type_unsupported" in error_lower
        or "invalid authentication" in error_lower
        or "login cookie" in error_lower
    ):
        st.error(
            "**Authentication failed. Google rejected the supplied credential.**\n\n"
            "**HTTP Status:** 401 Unauthorized\n\n"
            "**Possible causes:**\n"
            "- Invalid or malformed credential\n"
            "- Credential has been revoked or expired\n"
            "- Wrong Google Cloud project\n"
            "- Gemini API not enabled for this project\n"
            "- Billing or quota issue on the Google account\n\n"
            f"**Google's response:**\n```\n{error_str}\n```\n\n"
            "**Fix:** Generate a fresh credential at "
            "[Google AI Studio → API Keys](https://aistudio.google.com/app/apikey). "
            "Paste the new credential in the sidebar.",
            icon="🔑",
        )

    # ── Model Not Found / Unsupported (404) ───────────────────────────────────
    elif "404" in error_str or "not found" in error_lower:
        st.error(
            "**Model or API Endpoint Not Found (HTTP 404)**\n\n"
            "Google rejected the request because the configured model is not available "
            "for this API key or credential type.\n\n"
            f"**Google's response:**\n```\n{error_str[:400]}\n```\n\n"
            "**Fix:** Ensure you are using a standard Gemini API key generated from "
            "[Google AI Studio](https://aistudio.google.com/app/apikey).",
            icon="🚫",
        )

    # ── Permission / Authorization Errors (403) ───────────────────────────────
    elif "403" in error_str or "permission" in error_lower or "forbidden" in error_lower:
        st.error(
            "**Authentication failed. Google rejected the supplied credential.**\n\n"
            "**HTTP Status:** 403 Forbidden\n\n"
            "**Possible causes:**\n"
            "- Gemini API is not enabled for this Google Cloud project\n"
            "- The credential does not have permission to call this API\n"
            "- Billing is not set up on the Google account\n\n"
            f"**Google's response:**\n```\n{error_str}\n```\n\n"
            "**Fix:** Visit [Google AI Studio](https://aistudio.google.com/app/apikey) "
            "and ensure the Gemini API is enabled for your project.",
            icon="🔒",
        )

    # ── Rate Limit / Quota Errors (429) ───────────────────────────────────────
    elif "429" in error_str or "quota" in error_lower or "resource_exhausted" in error_lower:
        is_daily_exhausted = "limit: 0" in error_str or "limit:0" in error_str
        if is_daily_exhausted:
            st.error(
                "**🔴 Daily API Quota Exhausted**\n\n"
                "Your Gemini API key has used up its **entire free-tier daily allowance** "
                "across all models. This resets at midnight (Google time, ~UTC).\n\n"
                "**Immediate fix — get a fresh key (2 min):**\n"
                "1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)\n"
                "2. Click **Create API Key** → copy it\n"
                "3. Paste the new key into the sidebar **Gemini API Credential** field\n\n"
                "The application itself is working correctly — this is only a quota issue.",
                icon="🔑",
            )
        else:
            st.warning(
                "⏳ **Rate Limit — Please Wait ~60 Seconds**\n\n"
                "You've made too many requests in a short period. "
                "The free tier allows ~15 requests/minute.\n\n"
                "**Fix:** Wait 60 seconds, then click **Extract Clinical Intelligence** again.",
                icon="⏱️",
            )

    # ── Network / Connectivity Errors ─────────────────────────────────────────
    elif (
        "timeout"             in error_lower
        or "connection"       in error_lower
        or "network"          in error_lower
        or "service_unavailable" in error_lower
        or "deadline_exceeded" in error_lower
        or "unavailable"      in error_lower
    ):
        st.error(
            "**Network Error — Could not reach Google's servers.**\n\n"
            "This is a connectivity issue, not a credential issue. "
            "Check your internet connection and try again.\n\n"
            f"**Detail:** `{error_str[:300]}`",
            icon="🌐",
        )

    # ── No credential supplied ─────────────────────────────────────────────────
    elif "no credential" in error_lower or "no api key" in error_lower:
        st.warning(
            "**Credential required.** "
            "Paste your Gemini API credential in the sidebar to continue.\n\n"
            "Generate one for free at "
            "[Google AI Studio](https://aistudio.google.com/app/apikey).",
            icon="🔑",
        )

    # ── JSON Parsing Errors (model returned bad output) ───────────────────────
    elif "json" in error_lower or "parse" in error_lower:
        st.error(
            "**Response Parsing Error**\n\n"
            "The AI response was received but could not be structured into the expected format. "
            "This is rare and typically resolves on retry.\n\n"
            f"**Detail:** `{error_str[:300]}`",
            icon="🔄",
        )

    # ── PDF / File Processing Errors ──────────────────────────────────────────
    elif "pdf" in error_lower or "unsupported" in error_lower or "file" in error_lower:
        st.error(
            f"**File Processing Error:** {exc}\n\n"
            "Please ensure you are uploading a valid PDF or TXT file under 10 MB.",
            icon="📄",
        )

    # ── Tenacity RetryError — unwrap the underlying cause ──────────────────────
    elif "retryerror" in error_lower or "retry" in error_lower:
        # Unwrap to find the real root cause
        inner_exc = None
        cause = getattr(exc, "__cause__", None)
        if cause is not None:
            last = getattr(cause, "last_attempt", None)
            if last is not None:
                inner_exc = last.exception()
        if inner_exc is None:
            last = getattr(exc, "last_attempt", None)
            if last is not None:
                inner_exc = last.exception()

        # Recurse with the real root cause if found
        if inner_exc is not None and inner_exc is not exc:
            handle_extraction_error(inner_exc, context=context)
            return

        # Fallback: check error text for rate limit
        if "quota" in error_lower or "429" in error_str or "resource_exhausted" in error_lower:
            st.warning(
                "⏳ **Rate Limit — Please Wait 30 Seconds**\n\n"
                "You’ve made too many requests to the Gemini API in a short period. "
                "The free tier allows ~15 requests/minute.\n\n"
                "**Fix:** Wait 30–60 seconds, then click **Extract Clinical Intelligence** again.",
                icon="⏱️",
            )
        else:
            st.error(
                "**All retry attempts exhausted.** Google’s API did not respond successfully.\n\n"
                f"**Last error:** `{error_str[:400]}`\n\n"
                "Check your credential and internet connection, then try again.",
                icon="❌",
            )

    # ── Generic Fallback — always surface the actual error ────────────────────
    else:
        st.error(
            f"**Unexpected Error** (context: `{context}`)\n\n"
            f"```\n{error_str[:600]}\n```\n\n"
            "Please try again. If this persists, check the terminal for the full traceback.",
            icon="❌",
        )

    # Always log the full traceback server-side
    logger.exception("Error in context '%s': %s", context, exc)
