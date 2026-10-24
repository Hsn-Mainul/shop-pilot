import uuid

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.security import decode_token
from app.realtime.hub import hub
from app.services.media_stream_asr import MediaStreamSession

# ShopPilot FastAPI backend server
app = FastAPI(title="Shop Automation Platform API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.websocket("/ws/media/{call_id}")
async def media_stream_endpoint(websocket: WebSocket, call_id: str) -> None:
    """Twilio Media Streams → dialect ASR → live transcript + realtime push."""
    try:
        cid = uuid.UUID(call_id)
    except ValueError:
        await websocket.close(code=4400)
        return

    await websocket.accept()
    session = MediaStreamSession(cid)
    try:
        while True:
            message = await websocket.receive_text()
            if not session.handle_message(message):
                break
    except WebSocketDisconnect:
        session.flush()
    except Exception:
        session.flush()
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)) -> None:
    """Shop-scoped realtime channel. Client: ws://host/ws?token=<access_jwt>"""
    await websocket.accept()
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access" or not payload.get("shop_id"):
        await websocket.close(code=4401)
        return

    shop_id = payload["shop_id"]

    try:
        shop_uuid = uuid.UUID(str(shop_id))
    except ValueError:
        await websocket.close(code=4401)
        return

    await hub.connect(shop_uuid, websocket)
    try:
        await websocket.send_json({"event": "connected", "payload": {"shop_id": str(shop_uuid)}})
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"event": "pong", "payload": {}})
    except WebSocketDisconnect:
        await hub.disconnect(shop_uuid, websocket)
    except Exception:
        await hub.disconnect(shop_uuid, websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
