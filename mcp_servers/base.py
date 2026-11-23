"""Base MCP server infrastructure.

MCP Server 通过 stdio 与 MCP Client 通信，因此 **绝对不能向 stdout 打印任何
内容**（stdout 是 JSON-RPC 通道）。所有日志统一写入 stderr。
"""

import json
import logging
import sys
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def configure_stdio_logging() -> None:
    """Send all logs to stderr so they never corrupt the MCP stdio channel."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def dump(data: Any) -> str:
    """Serialize a tool result into a UTF-8 JSON string for MCP transport."""
    return json.dumps(data, ensure_ascii=False, default=str)


class BaseMCPServer:
    """Base class for all real MCP tool servers.

    只封装真实外部 API 调用。任何网络/鉴权/配置错误都会以明确的错误信息
    返回，绝不降级为伪造数据。
    """

    name: str = "Base Tools"
    description: str = "基础工具集"

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Return a lazily-initialized async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def error(message: str) -> Dict[str, Any]:
        """Build a unified error response dict."""
        return {"error": True, "message": message}

    @staticmethod
    def require(value: Optional[str], env_name: str) -> str:
        """Return a required credential or raise a clear configuration error."""
        if not value:
            raise RuntimeError(
                f"缺少 {env_name}，请在 .env 中配置真实的 API Key 后重试"
            )
        return value

    async def get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform a GET request and return the parsed JSON body.

        Raises:
            httpx.HTTPError: On network or HTTP status errors.
            RuntimeError: When the upstream returns a non-JSON body.
        """
        client = await self._get_client()
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"上游接口返回了非 JSON 内容（HTTP {response.status_code}）"
            ) from exc
