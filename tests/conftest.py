"""Shared pytest fixtures for hb-liquidations-feed tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@dataclass
class _Canned:
    payload: Any = None
    body: str | bytes | None = None
    status: int = 200
    headers: dict[str, str] | None = None
    query: dict[str, str] | None = None
    disconnect: bool = False


@dataclass
class GetServer:
    """Local aiohttp server answering canned GET responses."""

    url: str = ""
    requests: list[str] = field(default_factory=list)
    _routes: dict[str, list[_Canned]] = field(default_factory=dict)

    def add(
        self,
        path: str,
        payload: Any = None,
        body: str | bytes | None = None,
        status: int = 200,
        headers: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
        disconnect: bool = False,
    ) -> None:
        canned = _Canned(payload, body, status, headers, query, disconnect)
        self._routes.setdefault(path, []).append(canned)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        self.requests.append(
            request.path_qs if request.query_string else request.path,
        )
        for canned in self._routes.get(request.path, []):
            if canned.query is not None and dict(request.query) != canned.query:
                continue
            if canned.disconnect:
                if request.transport is not None:
                    request.transport.close()
                return web.Response(status=500)
            if canned.body is not None:
                return web.Response(
                    body=canned.body if isinstance(canned.body, bytes) else None,
                    text=canned.body if isinstance(canned.body, str) else None,
                    status=canned.status,
                    headers=canned.headers,
                )
            return web.json_response(
                canned.payload,
                status=canned.status,
                headers=canned.headers,
            )
        return web.Response(status=404)


@pytest.fixture
async def serve_get() -> AsyncIterator[GetServer]:
    state = GetServer()
    app = web.Application()
    app.router.add_get("/{tail:.*}", state.handle)
    server = TestServer(app)
    await server.start_server()
    state.url = str(server.make_url("")).rstrip("/")
    try:
        yield state
    finally:
        await server.close()
