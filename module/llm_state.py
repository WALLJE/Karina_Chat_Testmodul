"""Utility helpers to manage the active LLM provider in Streamlit session state."""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

from module.offline import is_offline
from module.mcp_client import (
    ConfigurationError,
    MCPClientError,
    RateLimitError,
    create_client_for_provider,
    has_mcp_configuration,
    has_openai_configuration,
)

LLM_PROVIDER_MCP = "mcp"
LLM_PROVIDER_OPENAI = "openai"

PROVIDER_LABELS: Dict[str, str] = {
    LLM_PROVIDER_MCP: "MCP-Server",
    LLM_PROVIDER_OPENAI: "ChatGPT (OpenAI)",
}

_SESSION_CLIENT_KEY = "mcp_client"
_SESSION_PROVIDER_KEY = "llm_provider"
_SESSION_LOADED_PROVIDER_KEY = "_llm_provider_loaded"


def _determine_default_provider() -> str:
    if has_mcp_configuration():
        return LLM_PROVIDER_MCP
    if has_openai_configuration():
        return LLM_PROVIDER_OPENAI
    return LLM_PROVIDER_MCP


def get_current_provider() -> str:
    provider = st.session_state.get(_SESSION_PROVIDER_KEY)
    if provider in PROVIDER_LABELS:
        return provider
    provider = _determine_default_provider()
    st.session_state[_SESSION_PROVIDER_KEY] = provider
    return provider


def get_provider_label(provider: Optional[str] = None) -> str:
    key = provider or get_current_provider()
    return PROVIDER_LABELS.get(key, key or "unbekannt")


def get_provider_status() -> Dict[str, Dict[str, bool]]:
    """Return availability information for supported providers."""

    return {
        LLM_PROVIDER_MCP: {
            "available": has_mcp_configuration(),
            "label": PROVIDER_LABELS[LLM_PROVIDER_MCP],
        },
        LLM_PROVIDER_OPENAI: {
            "available": has_openai_configuration(),
            "label": PROVIDER_LABELS[LLM_PROVIDER_OPENAI],
        },
    }


def ensure_llm_client(force_reload: bool = False):
    """Ensure that the configured LLM client is present in session state."""

    if is_offline():
        st.session_state[_SESSION_CLIENT_KEY] = None
        st.session_state[_SESSION_LOADED_PROVIDER_KEY] = None
        return None

    provider = get_current_provider()
    loaded_provider = st.session_state.get(_SESSION_LOADED_PROVIDER_KEY)
    client = st.session_state.get(_SESSION_CLIENT_KEY)

    if force_reload or client is None or loaded_provider != provider:
        client = create_client_for_provider(provider)
        st.session_state[_SESSION_CLIENT_KEY] = client
        st.session_state[_SESSION_LOADED_PROVIDER_KEY] = provider

    return client


def set_llm_provider(provider: str, *, reload: bool = True) -> None:
    if provider not in PROVIDER_LABELS:
        raise ConfigurationError(
            f"Unbekannter LLM-Provider '{provider}'. Unterstützt werden: {', '.join(PROVIDER_LABELS)}."
        )

    st.session_state[_SESSION_PROVIDER_KEY] = provider
    st.session_state[_SESSION_LOADED_PROVIDER_KEY] = None
    if reload:
        ensure_llm_client(force_reload=True)


def clear_llm_client() -> None:
    st.session_state[_SESSION_CLIENT_KEY] = None
    st.session_state[_SESSION_LOADED_PROVIDER_KEY] = None


__all__ = [
    "LLM_PROVIDER_MCP",
    "LLM_PROVIDER_OPENAI",
    "PROVIDER_LABELS",
    "ConfigurationError",
    "MCPClientError",
    "RateLimitError",
    "clear_llm_client",
    "ensure_llm_client",
    "get_current_provider",
    "get_provider_label",
    "get_provider_status",
    "set_llm_provider",
]
