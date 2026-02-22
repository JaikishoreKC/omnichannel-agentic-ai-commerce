from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin_routes import router as admin_router
from app.api.routes.auth_routes import router as auth_router
from app.api.routes.cart_routes import router as cart_router
from app.api.routes.interaction_routes import router as interaction_router
from app.api.routes.memory_routes import router as memory_router
from app.api.routes.order_routes import router as order_router
from app.api.routes.product_routes import router as product_router
from app.api.routes.session_routes import router as session_router
from app.container import (
    auth_service,
    mongo_manager,
    orchestrator,
    redis_manager,
    session_service,
    settings,
)

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(product_router, prefix=settings.api_prefix)
app.include_router(cart_router, prefix=settings.api_prefix)
app.include_router(order_router, prefix=settings.api_prefix)
app.include_router(session_router, prefix=settings.api_prefix)
app.include_router(memory_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(interaction_router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "services": {
            "mongo": {"status": mongo_manager.status, "error": mongo_manager.error},
            "redis": {"status": redis_manager.status, "error": redis_manager.error},
        },
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = websocket.query_params.get("sessionId")
    if not session_id:
        session = session_service.create_session(channel="websocket", initial_context={})
        session_id = session["id"]
        await websocket.send_json(
            {"type": "session", "payload": {"sessionId": session_id, "expiresAt": session["expiresAt"]}}
        )

    user_id: str | None = None
    auth_header = websocket.headers.get("authorization")
    if auth_header:
        try:
            scheme, token = auth_header.split(" ", 1)
            if scheme.lower() == "bearer":
                user = auth_service.get_user_from_access_token(token)
                user_id = str(user["id"])
        except Exception:
            user_id = None
    if not user_id:
        try:
            session = session_service.get_session(session_id)
            if session.get("userId"):
                user_id = str(session["userId"])
        except Exception:
            user_id = None

    try:
        while True:
            payload = await websocket.receive_json()
            msg_type = payload.get("type")
            if msg_type == "typing":
                await websocket.send_json({"type": "typing", "payload": payload.get("payload", {})})
                continue
            if msg_type != "message":
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "code": "UNSUPPORTED_MESSAGE_TYPE",
                            "message": "Only `message` and `typing` event types are supported.",
                        },
                    }
                )
                continue

            message = payload.get("payload", {}).get("content", "").strip()
            if not message:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {"code": "VALIDATION_ERROR", "message": "Message content is required."},
                    }
                )
                continue

            response = await orchestrator.process_message(
                message=message,
                session_id=session_id,
                user_id=user_id,
                channel="websocket",
            )
            await websocket.send_json({"type": "response", "payload": response})
    except WebSocketDisconnect:
        return
