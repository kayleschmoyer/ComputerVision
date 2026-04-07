from __future__ import annotations

import datetime as dt
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, create_engine, desc, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[dt.datetime] = mapped_column(DateTime)
    event_type: Mapped[str] = mapped_column(String(120))
    clip_path: Mapped[str] = mapped_column(String(500))
    camera_id: Mapped[str] = mapped_column(String(120))
    details: Mapped[str] = mapped_column(String(500))


class AlertIn(BaseModel):
    timestamp: float
    event_type: str
    clip_path: str
    camera_id: str
    details: str


class AlertOut(BaseModel):
    id: int
    timestamp: str
    event_type: str
    clip_path: str
    camera_id: str
    details: str


class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for conn in self.connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)


def create_app(sqlite_path: str = "data/scanguard.db") -> FastAPI:
    app = FastAPI(title="ScanGuard Lite API")
    db_url = f"sqlite:///{sqlite_path}"
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    ws_manager = ConnectionManager()

    dashboard_dir = Path(__file__).parent / "dashboard"
    clips_dir = Path("clips")
    clips_dir.mkdir(exist_ok=True)

    app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    app.mount("/clips", StaticFiles(directory=clips_dir), name="clips")

    @app.get("/")
    def index():
        return FileResponse(dashboard_dir / "index.html")

    @app.post("/alerts")
    async def create_alert(alert: AlertIn):
        with Session(engine) as session:
            record = AlertRecord(
                timestamp=dt.datetime.fromtimestamp(alert.timestamp),
                event_type=alert.event_type,
                clip_path=alert.clip_path,
                camera_id=alert.camera_id,
                details=alert.details,
            )
            session.add(record)
            session.commit()
            session.refresh(record)

            payload = {
                "id": record.id,
                "timestamp": record.timestamp.isoformat(),
                "event_type": record.event_type,
                "clip_path": record.clip_path,
                "camera_id": record.camera_id,
                "details": record.details,
            }

        await ws_manager.broadcast(payload)
        return payload

    @app.get("/alerts", response_model=list[AlertOut])
    def get_alerts(limit: int = 50):
        with Session(engine) as session:
            rows = session.scalars(
                select(AlertRecord).order_by(desc(AlertRecord.id)).limit(limit)
            ).all()
            return [
                AlertOut(
                    id=r.id,
                    timestamp=r.timestamp.isoformat(),
                    event_type=r.event_type,
                    clip_path=r.clip_path,
                    camera_id=r.camera_id,
                    details=r.details,
                )
                for r in rows
            ]

    @app.websocket("/ws/alerts")
    async def alert_socket(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    return app
