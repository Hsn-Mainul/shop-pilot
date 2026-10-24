"""Shop-scoped realtime hub with optional Redis fan-out for multi-worker.

Local connections are always served in-process. When Redis is reachable,
`broadcast` also PUBLISHes so other uvicorn workers deliver to their sockets.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from typing import Any

from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger(__name__)

CHANNEL = "shoppilot:realtime"


class RealtimeHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._redis = None
        self._subscriber_started = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            import redis

            client = redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
            client.ping()
            self._redis = client
            return client
        except Exception:
            self._redis = False  # type: ignore[assignment]
            return None

    async def connect(self, shop_id: uuid.UUID | str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._loop = asyncio.get_running_loop()
        key = str(shop_id)
        async with self._lock:
            self._rooms.setdefault(key, set()).add(websocket)
        self._ensure_subscriber()

    async def disconnect(self, shop_id: uuid.UUID | str, websocket: WebSocket) -> None:
        key = str(shop_id)
        async with self._lock:
            conns = self._rooms.get(key)
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self._rooms.pop(key, None)

    def _ensure_subscriber(self) -> None:
        if self._subscriber_started:
            return
        client = self._get_redis()
        if not client:
            return
        self._subscriber_started = True

        def _listen() -> None:
            try:
                pubsub = client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(CHANNEL)
                for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        data = json.loads(message["data"])
                        shop_id = data.get("shop_id")
                        event = data.get("event")
                        payload = data.get("payload") or {}
                        if not shop_id or not event or not self._loop:
                            continue
                        asyncio.run_coroutine_threadsafe(
                            self._local_broadcast(shop_id, event, payload, from_redis=True),
                            self._loop,
                        )
                    except Exception:
                        logger.exception("realtime redis message failed")
            except Exception:
                logger.exception("realtime redis subscriber stopped")
                self._subscriber_started = False

        threading.Thread(target=_listen, name="realtime-redis", daemon=True).start()

    async def _local_broadcast(
        self,
        shop_id: uuid.UUID | str,
        event: str,
        payload: dict[str, Any],
        *,
        from_redis: bool = False,
    ) -> None:
        key = str(shop_id)
        message = {"event": event, "payload": payload}
        async with self._lock:
            targets = list(self._rooms.get(key, set()))
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(shop_id, ws)
        # Silence unused in single-worker path
        _ = from_redis

    async def broadcast(self, shop_id: uuid.UUID | str, event: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        await self._local_broadcast(shop_id, event, payload)
        client = self._get_redis()
        if client:
            try:
                client.publish(
                    CHANNEL,
                    json.dumps({"shop_id": str(shop_id), "event": event, "payload": payload}),
                )
            except Exception:
                logger.debug("redis publish failed", exc_info=True)

    def broadcast_sync(self, shop_id: uuid.UUID | str, event: str, payload: dict[str, Any] | None = None) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.broadcast(shop_id, event, payload))


hub = RealtimeHub()
