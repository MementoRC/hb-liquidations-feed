"""Standalone network client using aiohttp."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class WSAssistant:
    """Standalone WebSocket assistant wrapping aiohttp."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse):
        self._ws = ws

    async def send(self, payload: Any) -> None:
        if isinstance(payload, dict):
            await self._ws.send_json(payload)
        else:
            await self._ws.send_str(str(payload))

    async def disconnect(self) -> None:
        if not self._ws.closed:
            await self._ws.close()

    async def iter_messages(self) -> AsyncGenerator[Any, None]:
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    yield json.loads(msg.data)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse WS message: {msg.data}")
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break


class NetworkClient:
    """Standalone HTTP/WS client using aiohttp."""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def ws_connect(self, url: str) -> WSAssistant:
        session = await self._ensure_session()
        ws = await session.ws_connect(url)
        return WSAssistant(ws)

    async def rest_get(self, url: str, params: dict | None = None) -> Any:
        session = await self._ensure_session()
        async with session.get(url, params=params) as resp:
            return await resp.json()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
