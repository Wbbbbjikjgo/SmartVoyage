"""Base MCP server infrastructure: shared HTTP client and helpers."""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class BaseMCPServer:
    """Base class for all MCP tool servers.

    Responsibilities:
    - Lazily manage a shared async HTTP client (with a sane timeout).
    - Provide a unified error-response helper.
    - Provide a mock-mode toggle so each server can fall back to
      deterministic fake data when the upstream API is unavailable or
      when free quota must be preserved.
    """

    name: str = "Base Tools"
    description: str = "基础工具集"

    def __init__(self, mock_mode: Optional[bool] = None):
        """Initialize the base server.

        Args:
            mock_mode: Explicitly force mock mode on/off. When ``None``,
                the concrete subclass decides (usually from settings).
        """
        self.mock_mode = bool(mock_mode)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a lazily-initialized async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def error(message: str) -> Dict[str, Any]:
        """Build a unified error response dict."""
        return {"error": True, "message": message}

    async def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform a GET request and return the parsed JSON body.

        Args:
            url: Request URL.
            params: Query string parameters.
            headers: Extra headers (e.g. Authorization for Aliyun market).

        Returns:
            Parsed JSON dict.

        Raises:
            httpx.HTTPError: On network or HTTP status errors.
        """
        client = await self._get_client()
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
