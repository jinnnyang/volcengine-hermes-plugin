"""Volcengine Doubao Search backend for Hermes web_search."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List

import httpx

try:  # Hermes runtime
    from agent.web_search_provider import WebSearchProvider
except ModuleNotFoundError:  # Local plugin test/runtime outside Hermes source tree
    class WebSearchProvider:  # type: ignore[no-redef]
        @property
        def name(self) -> str:
            raise NotImplementedError

        @property
        def display_name(self) -> str:
            return self.name

        def is_available(self) -> bool:
            raise NotImplementedError

        def supports_search(self) -> bool:
            return True

        def supports_extract(self) -> bool:
            return False

        def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
            raise NotImplementedError

        def get_setup_schema(self) -> Dict[str, Any]:
            return {"name": self.display_name, "badge": "", "tag": "", "env_vars": []}


logger = logging.getLogger(__name__)

DOUBAO_SEARCH_ENDPOINT = "https://open.feedcoopapi.com/search_api/web_search"
SEARCH_API_KEY_ENV_VARS = (
    "VOLCENGINE_API_KEY",
    "ARK_API_KEY",
)
MAX_SEARCH_COUNT = 50


def _first_env_value(names: Iterable[str]) -> str:
    try:
        from plugins._volcengine_common.config import resolve_volcengine_api_key
    except ModuleNotFoundError:
        import importlib.util
        from pathlib import Path
        config_path = Path(__file__).resolve().parents[2] / "_volcengine_common" / "config.py"
        spec = importlib.util.spec_from_file_location("volcengine_common_config", config_path)
        config_module = importlib.util.module_from_spec(spec)
        assert spec is not None and spec.loader is not None
        spec.loader.exec_module(config_module)
        resolve_volcengine_api_key = config_module.resolve_volcengine_api_key

    return resolve_volcengine_api_key()


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_description(result: Dict[str, Any]) -> str:
    body = str(result.get("Summary") or result.get("Snippet") or "").strip()
    badges = [
        str(result.get("SiteName") or "").strip(),
        str(result.get("AuthInfoDes") or "").strip(),
    ]
    header = " | ".join(part for part in badges if part)
    if header and body:
        return f"{header}\n{body}"
    return header or body


def _extract_api_error(data: Dict[str, Any]) -> str | None:
    error = (data.get("ResponseMetadata") or {}).get("Error") or data.get("Error")
    if not isinstance(error, dict):
        return None
    code = str(error.get("Code") or "Unknown").strip()
    message = str(error.get("Message") or error.get("MessageCN") or "Unknown error").strip()
    return f"Volcengine Doubao Search API Error [{code}]: {message}"


class VolcengineWebSearchProvider(WebSearchProvider):
    """Search-only provider for Volcengine Doubao Search direct API."""

    @property
    def name(self) -> str:
        return "volcengine"

    @property
    def display_name(self) -> str:
        return "Volcengine Doubao Search"

    def is_available(self) -> bool:
        return bool(_first_env_value(SEARCH_API_KEY_ENV_VARS))

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        api_key = _first_env_value(SEARCH_API_KEY_ENV_VARS)
        if not api_key:
            return {
                "success": False,
                "error": "Missing Volcengine search API key. Set one of: "
                + ", ".join(SEARCH_API_KEY_ENV_VARS),
            }

        count = max(1, min(int(limit), MAX_SEARCH_COUNT))
        payload: Dict[str, Any] = {
            "Query": query,
            "SearchType": "web",
            "Count": count,
            "NeedSummary": True,
        }

        auth_level = os.getenv("VOLCENGINE_SEARCH_AUTH_LEVEL", "").strip()
        if auth_level:
            try:
                payload["Filter"] = {"AuthInfoLevel": int(auth_level)}
            except ValueError:
                logger.warning("Ignoring invalid VOLCENGINE_SEARCH_AUTH_LEVEL=%r", auth_level)

        time_range = os.getenv("VOLCENGINE_SEARCH_TIME_RANGE", "").strip()
        if time_range:
            payload["TimeRange"] = time_range

        query_rewrite = os.getenv("VOLCENGINE_SEARCH_QUERY_REWRITE", "").strip()
        if query_rewrite:
            payload["QueryControl"] = {"QueryRewrite": _parse_bool(query_rewrite)}

        try:
            response = httpx.post(
                DOUBAO_SEARCH_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "X-Traffic-Tag": "skill_web_search_common",
                },
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Volcengine Doubao Search HTTP error: %s", exc)
            return {
                "success": False,
                "error": f"Volcengine Doubao Search returned HTTP {exc.response.status_code}",
            }
        except httpx.RequestError as exc:
            logger.warning("Volcengine Doubao Search request error: %s", exc)
            return {"success": False, "error": f"Could not reach Volcengine Doubao Search: {exc}"}

        try:
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Volcengine Doubao Search response parse error: %s", exc)
            return {
                "success": False,
                "error": "Could not parse Volcengine Doubao Search response as JSON",
            }

        api_error = _extract_api_error(data)
        if api_error:
            return {"success": False, "error": api_error}

        raw_results = ((data.get("Result") or {}).get("WebResults") or [])[:count]
        web_results: List[Dict[str, Any]] = []
        for index, item in enumerate(raw_results, start=1):
            if not isinstance(item, dict):
                continue
            web_results.append(
                {
                    "title": str(item.get("Title") or ""),
                    "url": str(item.get("Url") or ""),
                    "description": _build_description(item),
                    "position": int(item.get("SortId") or index),
                }
            )

        return {"success": True, "data": {"web": web_results}}

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Volcengine Doubao Search",
            "badge": "paid",
            "tag": "Volcengine Doubao Search direct API; search only.",
            "env_vars": [
                {
                    "key": "VOLCENGINE_API_KEY",
                    "prompt": "Volcengine API Key (shared for all services)",
                    "url": "https://www.volcengine.com/docs/85508/1650263#search-infinity",
                }
            ],
        }
