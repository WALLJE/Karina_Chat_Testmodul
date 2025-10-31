"""Utility clients to interact with MCP-compatible backends and AMBOSS tools."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, MutableMapping, Optional
import json
import os

import requests

import streamlit as st

try:  # pragma: no cover - optional dependency
    from openai import (
        OpenAI,
        OpenAIError,
        APIConnectionError as OpenAIAPIConnectionError,
        APIError as OpenAIAPIError,
        RateLimitError as OpenAIRateLimitError,
    )
except Exception:  # pragma: no cover - optional dependency missing
    OpenAI = None  # type: ignore[assignment]
    OpenAIError = OpenAIAPIConnectionError = OpenAIAPIError = OpenAIRateLimitError = Exception  # type: ignore[assignment]


class MCPClientError(RuntimeError):
    """Base error for all MCP client issues."""


class ConfigurationError(MCPClientError):
    """Raised when the MCP configuration is incomplete."""


class RateLimitError(MCPClientError):
    """Raised when the MCP server reports a rate limiting condition."""


DEFAULT_AMBOSS_MCP_URL = "https://content-mcp.de.production.amboss.com/mcp"


@dataclass
class AmbossConfigurationStatus:
    """Status information about the AMBOSS configuration."""

    available: bool
    message: Optional[str] = None
    base_url: Optional[str] = None
    source: Optional[str] = None
    token_available: bool = False
    details: Optional[str] = None


def _get_secret(key: str) -> Optional[str]:
    try:
        value = st.secrets[key]
    except KeyError:
        return None
    return str(value) if value is not None else None


def _load_amboss_headers(api_key: Optional[str]) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _try_parse_json(payload: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_streamable_response(response: requests.Response) -> Dict[str, Any]:
    """Parse JSON or SSE responses from MCP endpoints."""

    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        parsed = response.json()
        if not isinstance(parsed, dict):
            raise MCPClientError("MCP response payload must be a JSON object")
        return parsed

    payload_lines: List[str] = []
    for line in response.text.splitlines():
        stripped = line.strip()
        if stripped.startswith("data:"):
            payload_lines.append(stripped[len("data:"):].strip())

    if not payload_lines:
        # Ausführliches Debugging: Wir legen den kompletten Rohtext in einem separaten
        # Session-State-Eintrag ab. So kann der Inhalt im Adminbereich inspiziert
        # und kopiert werden, ohne das reguläre Parsing zu verändern. Damit bleibt
        # klar ersichtlich, welche Daten der MCP-Dienst geliefert hat.
        st.session_state["amboss_result_raw"] = {
            "hinweis": "SSE enthielt keine 'data:'-Zeilen.",
            "rohtext": response.text,
            "extrahierte_zeilen": payload_lines,
        }
        raise MCPClientError("Received an SSE response without any data payload to decode.")

    payload = "".join(payload_lines)
    parsed = _try_parse_json(payload)
    if parsed is None:
        # Falls das JSON-Parsing scheitert, vermerken wir sowohl den originalen
        # SSE-Text als auch den zusammengesetzten Payload. Dadurch lässt sich im
        # Adminmodus schnell nachvollziehen, an welchem Fragment das Parsing
        # gescheitert ist. Die ausführlichen Kommentare sollen verdeutlichen,
        # wie sich das Verhalten bei Bedarf weiter anpassen lässt.
        st.session_state["amboss_result_raw"] = {
            "hinweis": "JSON-Parsing der SSE-Nutzlast fehlgeschlagen.",
            "rohtext": response.text,
            "extrahierte_zeilen": payload_lines,
            "zusammengefuehrter_payload": payload,
        }
        raise MCPClientError("Could not decode MCP SSE payload as JSON.")
    # Sobald das Parsing wieder erfolgreich ist, räumen wir den Rohdaten-Eintrag auf,
    # damit im Adminbereich keine überholten Informationen angezeigt werden.
    st.session_state.pop("amboss_result_raw", None)
    return parsed


def _build_tool_payload(tool_name: str, query: str, *, language: str = "de") -> Dict[str, Any]:
    arguments: Dict[str, Any] = {"language": language}
    if tool_name in {"search_article_sections", "search_pharma_substances", "search_media"}:
        arguments["query"] = query
    elif tool_name == "get_definition":
        arguments["term"] = query
    elif tool_name == "get_drug_monograph":
        arguments["substance_eid"] = query
    elif tool_name == "get_guidelines":
        arguments["guideline_ids"] = [query]
    else:
        arguments["query"] = query

    return {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }


class AmbossToolClient:
    """HTTP client that calls AMBOSS MCP tools via a streamable response."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if not base_url:
            raise ConfigurationError("AMBOSS MCP base URL is missing")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

    def call_tool(
        self,
        tool_name: str,
        *,
        query: str,
        language: str = "de",
    ) -> Dict[str, Any]:
        payload = _build_tool_payload(tool_name, query, language=language)
        headers = _load_amboss_headers(self.api_key)
        headers.update(self.extra_headers)

        try:
            response = requests.post(
                self.base_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise MCPClientError(f"AMBOSS MCP request failed: {exc}") from exc

        if response.status_code >= 400:
            raise MCPClientError(
                f"AMBOSS MCP request failed with status {response.status_code}: {response.text}"
            )

        parsed = _parse_streamable_response(response)
        if "error" in parsed:
            raise MCPClientError(
                "AMBOSS MCP server returned an error: "
                + json.dumps(parsed.get("error"), ensure_ascii=False)
            )
        return parsed


def _load_extra_headers(raw: Optional[str]) -> Dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("extra headers must decode into a dict")
        return {str(key): str(value) for key, value in data.items()}
    except (json.JSONDecodeError, ValueError) as exc:
        raise ConfigurationError(
            "MCP_EXTRA_HEADERS must be a JSON object with string values"
        ) from exc


def _load_amboss_extra_headers() -> Dict[str, str]:
    return _load_extra_headers(os.getenv("AMBOSS_MCP_EXTRA_HEADERS"))


def _determine_amboss_base_url() -> tuple[Optional[str], Optional[str]]:
    """Return the configured AMBOSS base URL and its source label."""

    candidates = [
        ("env:AMBOSS_MCP_URL", os.getenv("AMBOSS_MCP_URL")),
        ("env:AMBOSS_MCP_ENDPOINT", os.getenv("AMBOSS_MCP_ENDPOINT")),
        ("secret:Amboss_Url", _get_secret("Amboss_Url")),
        ("env:MCP_SERVER_URL", os.getenv("MCP_SERVER_URL")),
    ]
    for source, value in candidates:
        if value:
            return str(value), source
    return DEFAULT_AMBOSS_MCP_URL, "default"

def _determine_amboss_token() -> str:
    token = _get_secret("Amboss_Token")
    if not token:
        raise ConfigurationError(
            "AMBOSS MCP Token fehlt. Hinterlege 'Amboss_Token' in den Streamlit Secrets."
        )
    return token


def create_amboss_tool_client() -> AmbossToolClient:
    base_url, _ = _determine_amboss_base_url()
    if not base_url:
        raise ConfigurationError(
            "AMBOSS MCP URL ist nicht konfiguriert. Setze AMBOSS_MCP_URL oder Amboss_Url in den Secrets."
        )
    api_key = _determine_amboss_token()
    timeout = float(os.getenv("AMBOSS_MCP_TIMEOUT", os.getenv("MCP_TIMEOUT", "60")))
    extra_headers = _load_amboss_extra_headers()
    return AmbossToolClient(
        base_url,
        api_key=api_key,
        timeout=timeout,
        extra_headers=extra_headers,
    )


def get_amboss_configuration_status() -> AmbossConfigurationStatus:
    """Return whether AMBOSS is configured and include diagnostic info."""

    try:
        _determine_amboss_token()
    except ConfigurationError as exc:
        return AmbossConfigurationStatus(False, str(exc), token_available=False)

    base_url, source = _determine_amboss_base_url()
    if not base_url:
        return AmbossConfigurationStatus(
            False,
            "AMBOSS MCP URL ist nicht gesetzt. Hinterlege AMBOSS_MCP_URL oder Amboss_Url.",
            base_url=None,
            source=source,
            token_available=True,
        )

    details = None
    if source == "default":
        details = (
            "AMBOSS-Standardendpunkt wird verwendet: "
            f"{DEFAULT_AMBOSS_MCP_URL}"
        )
    else:
        details = f"AMBOSS-Endpunkt: {base_url} (Quelle: {source})"

    return AmbossConfigurationStatus(
        True,
        None,
        base_url=base_url,
        source=source,
        token_available=True,
        details=details,
    )


def has_amboss_configuration() -> bool:
    try:
        _determine_amboss_token()
    except ConfigurationError:
        return False
    return bool(_determine_amboss_base_url())


def fetch_amboss_scenario_knowledge(
    scenario_term: str,
    *,
    language: str = "de",
) -> Dict[str, Any]:
    if not scenario_term:
        raise ValueError("scenario_term must not be empty")
    client = create_amboss_tool_client()
    return client.call_tool(
        "search_article_sections",
        query=scenario_term,
        language=language,
    )


@dataclass
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class _Choice:
    def __init__(self, payload: MutableMapping[str, Any]):
        message = _normalise_message(payload)
        self.message = SimpleNamespace(**message)
        self.finish_reason = payload.get("finish_reason")


class ChatCompletionResponse:
    """Lightweight object mirroring the OpenAI response structure."""

    def __init__(self, data: MutableMapping[str, Any]):
        self._raw = data
        self.choices: List[_Choice] = [
            _Choice(choice) for choice in data.get("choices", [])
        ] or [_Choice({"message": {"role": "assistant", "content": ""}})]
        usage_payload = data.get("usage") or {}
        self.usage = _Usage(
            prompt_tokens=int(usage_payload.get("prompt_tokens", 0) or 0),
            completion_tokens=int(usage_payload.get("completion_tokens", 0) or 0),
            total_tokens=int(usage_payload.get("total_tokens") or (
                (usage_payload.get("prompt_tokens") or 0)
                + (usage_payload.get("completion_tokens") or 0)
            )),
        )

    @property
    def raw(self) -> MutableMapping[str, Any]:
        return self._raw


def _normalise_message(choice_payload: MutableMapping[str, Any]) -> Dict[str, str]:
    """Return a dictionary with ``role`` and ``content`` keys.

    MCP responses may follow different schemas.  The adapter tries to
    cover the most common variants (OpenAI-compatible or Claude-style
    content blocks).
    """

    message = choice_payload.get("message") or {}

    if not message and "delta" in choice_payload:
        # Some implementations stream via ``delta``; take the aggregated
        # delta as the final message.
        message = choice_payload.get("delta") or {}

    role = message.get("role", "assistant")
    content = message.get("content")

    if isinstance(content, list):
        # Combine textual segments from Claude/MCP responses.
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, MutableMapping):
                if block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
                elif "content" in block and isinstance(block["content"], str):
                    parts.append(block["content"])
        content = "".join(parts)

    if content is None:
        # Fallbacks for alternative payload shapes
        if "content" in choice_payload:
            content = choice_payload.get("content")
        elif "text" in choice_payload:
            content = choice_payload.get("text")
        else:
            content = ""

    return {"role": role, "content": str(content)}


class _ChatCompletions:
    def __init__(self, client: "MCPClient") -> None:
        self._client = client

    def create(self, *, model: Optional[str] = None, messages: Iterable[Dict[str, Any]], temperature: Optional[float] = None, **kwargs: Any) -> ChatCompletionResponse:  # noqa: E501
        payload: Dict[str, Any] = {
            "model": model or self._client.default_model,
            "messages": list(messages),
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if kwargs:
            payload.update(kwargs)
        data = self._client._post(self._client.chat_completions_path, payload)
        return ChatCompletionResponse(data)


class _ChatNamespace:
    def __init__(self, client: "MCPClient") -> None:
        self.completions = _ChatCompletions(client)


class MCPClient:
    """Thin HTTP client for MCP chat completions."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 60.0,
        auth_header: str = "Authorization",
        chat_completions_path: str = "/v1/chat/completions",
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        if not base_url:
            raise ConfigurationError("MCP base URL is missing")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model or os.getenv("MCP_MODEL", "default")
        self.timeout = timeout
        self.auth_header = auth_header or "Authorization"
        self.chat_completions_path = chat_completions_path
        self.extra_headers = extra_headers or {}
        self.chat = _ChatNamespace(self)

    def _post(self, path: str, payload: Dict[str, Any]) -> MutableMapping[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        headers.update(self.extra_headers)
        if self.api_key:
            headers[self.auth_header] = f"Bearer {self.api_key}" if self.auth_header.lower() == "authorization" else self.api_key
        try:
            response = requests.post(url, json=payload, timeout=self.timeout, headers=headers)
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise MCPClientError(f"MCP request failed: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError("MCP server rate limit exceeded")
        if response.status_code >= 500:
            raise MCPClientError(
                f"MCP server error {response.status_code}: {response.text}"
            )
        if response.status_code >= 400:
            raise MCPClientError(
                f"MCP request failed with status {response.status_code}: {response.text}"
            )

        if not response.content:
            return {}

        content_type = response.headers.get("Content-Type", "")
        body_text = response.text

        if "text/event-stream" in content_type or body_text.lstrip().startswith("event:"):
            data_lines: List[str] = []
            for line in body_text.splitlines():
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                elif not line.strip() and data_lines:
                    break

            if not data_lines:
                raise MCPClientError(
                    "Received an SSE response without any data payload to decode."
                )

            body_text = "\n".join(data_lines)

        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as exc:  # pragma: no cover - invalid response
            raise MCPClientError(
                f"Invalid MCP response: {exc}. Raw payload: {body_text[:200]}"
            ) from exc

        if isinstance(data, MutableMapping) and data.get("error"):
            raise MCPClientError(
                "MCP server returned an error: "
                + json.dumps(data.get("error"), ensure_ascii=False)
            )

        return data


class _OpenAIChatCompletions:
    def __init__(self, client: "OpenAIChatClient") -> None:
        self._client = client

    def create(
        self,
        *,
        model: Optional[str] = None,
        messages: Iterable[Dict[str, Any]],
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> Any:
        payload: Dict[str, Any] = {
            "model": model or self._client.default_model,
            "messages": list(messages),
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if kwargs:
            payload.update(kwargs)

        try:
            return self._client._client.chat.completions.create(**payload)
        except OpenAIRateLimitError as exc:  # pragma: no cover - network failure
            raise RateLimitError("OpenAI rate limit exceeded") from exc
        except (OpenAIAPIError, OpenAIAPIConnectionError, OpenAIError) as exc:  # pragma: no cover - network failure
            raise MCPClientError(f"OpenAI request failed: {exc}") from exc


class _OpenAIChatNamespace:
    def __init__(self, client: "OpenAIChatClient") -> None:
        self.completions = _OpenAIChatCompletions(client)


class OpenAIChatClient:
    """Wrapper that provides the same interface as :class:`MCPClient`."""

    def __init__(self, raw_client: "OpenAI", default_model: Optional[str] = None) -> None:
        self._client = raw_client
        self.default_model = default_model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.chat = _OpenAIChatNamespace(self)


def create_mcp_client_from_env() -> MCPClient:
    """Create an :class:`MCPClient` based on environment variables."""

    base_url = os.getenv("MCP_SERVER_URL")
    if not base_url:
        raise ConfigurationError(
            "MCP_SERVER_URL is not set. Provide the MCP endpoint before starting the app."
        )
    api_key = os.getenv("MCP_API_KEY")
    default_model = os.getenv("MCP_MODEL")
    timeout = float(os.getenv("MCP_TIMEOUT", "60"))
    auth_header = os.getenv("MCP_AUTH_HEADER", "Authorization")
    chat_path = os.getenv("MCP_CHAT_COMPLETIONS_PATH", "/v1/chat/completions")
    extra_headers = _load_extra_headers(os.getenv("MCP_EXTRA_HEADERS"))

    return MCPClient(
        base_url,
        api_key=api_key,
        default_model=default_model,
        timeout=timeout,
        auth_header=auth_header,
        chat_completions_path=chat_path,
        extra_headers=extra_headers,
    )


def create_openai_client_from_env() -> OpenAIChatClient:
    """Create an :class:`OpenAIChatClient` using the OpenAI SDK configuration."""

    if OpenAI is None:  # pragma: no cover - optional dependency missing
        raise ConfigurationError(
            "Das OpenAI-Python-Paket ist nicht installiert. Bitte ergänze 'openai' in den Abhängigkeiten."
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "OPENAI_API_KEY ist nicht gesetzt. Bitte trage den Schlüssel in den Umgebungsvariablen ein."
        )

    base_url = os.getenv("OPENAI_BASE_URL") or None
    organization = os.getenv("OPENAI_ORG") or None

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            organization=organization,
        )
    except OpenAIError as exc:  # pragma: no cover - SDK initialisation failure
        raise MCPClientError(f"OpenAI-Client konnte nicht initialisiert werden: {exc}") from exc

    default_model = os.getenv("OPENAI_MODEL") or os.getenv("OPENAI_DEFAULT_MODEL")
    return OpenAIChatClient(client, default_model=default_model)


def has_mcp_configuration() -> bool:
    """Return True if the environment is configured for MCP usage."""

    return bool(os.getenv("MCP_SERVER_URL"))


def has_openai_configuration() -> bool:
    """Return True if the environment provides OpenAI credentials."""

    return OpenAI is not None and bool(os.getenv("OPENAI_API_KEY"))


def create_client_for_provider(provider: str) -> Any:
    """Return a chat client for the requested provider."""

    normalized = (provider or "").strip().lower()
    if normalized in {"mcp", "mcp-client", "mcp_server"}:
        return create_mcp_client_from_env()
    if normalized in {"openai", "chatgpt", "gpt"}:
        return create_openai_client_from_env()
    raise ConfigurationError(
        f"Unbekannter LLM-Provider '{provider}'. Unterstützt werden 'mcp' und 'openai'."
    )


__all__ = [
    "AmbossToolClient",
    "ChatCompletionResponse",
    "ConfigurationError",
    "AmbossConfigurationStatus",
    "fetch_amboss_scenario_knowledge",
    "create_amboss_tool_client",
    "MCPClient",
    "MCPClientError",
    "RateLimitError",
    "OpenAIChatClient",
    "create_mcp_client_from_env",
    "create_openai_client_from_env",
    "create_client_for_provider",
    "get_amboss_configuration_status",
    "has_amboss_configuration",
    "has_mcp_configuration",
    "has_openai_configuration",
]
