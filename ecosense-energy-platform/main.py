import time
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

app = FastAPI(title="EcoSense Thermal & Energy Telemetry Platform")
templates = Jinja2Templates(directory="templates")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# Input Telemetry Schema
class TelemetryPayload(BaseModel):
    device_id: str = Field(..., example="SUPERBREW_ECO_01")
    power_watts: float = Field(..., example=2200.0)
    temp_c: float = Field(..., example=92.5)
    brew_active: bool = Field(..., example=False)

# Central Machine State & Energy Tracker
state = {
    "device_id": "SUPERBREW_ECO_01",
    "mode": "ACTIVE",
    "power_watts": 0.0,
    "temp_c": 0.0,
    "last_brew_time": time.time(),
    "total_kwh": 0.0,
    "saved_kwh": 0.0,
    "saved_cost_inr": 0.0,
    "last_tick": time.time()
}

# Commercial Power Tariff Rate
COST_PER_KWH_INR = 8.0  # ₹8 per kWh

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/v1/telemetry")
async def receive_telemetry(payload: TelemetryPayload):
    now = time.time()
    time_delta_hours = (now - state["last_tick"]) / 3600.0
    state["last_tick"] = now

    # Reset inactivity timer if a drink was dispensed
    if payload.brew_active:
        state["last_brew_time"] = now

    # Heuristic Rule: If no brew for > 10 seconds, trigger ECO_MODE
    idle_duration = now - state["last_brew_time"]
    if idle_duration > 10.0:
        state["mode"] = "ECO_MODE"
    else:
        state["mode"] = "ACTIVE"

    # Energy calculations
    actual_watts = payload.power_watts
    baseline_watts = 2200.0  # Baseline power draw without smart thermal cycling

    kwh_used = (actual_watts * time_delta_hours) / 1000.0
    kwh_saved = max(0.0, ((baseline_watts - actual_watts) * time_delta_hours) / 1000.0)

    state["total_kwh"] += kwh_used
    state["saved_kwh"] += kwh_saved
    state["saved_cost_inr"] = state["saved_kwh"] * COST_PER_KWH_INR

    state["power_watts"] = actual_watts
    state["temp_c"] = payload.temp_c
    state["device_id"] = payload.device_id

    # Data payload sent live to WebSockets
    update_data = {
        "timestamp": time.strftime("%H:%M:%S"),
        "device_id": state["device_id"],
        "mode": state["mode"],
        "power_watts": round(state["power_watts"], 1),
        "temp_c": round(state["temp_c"], 1),
        "total_kwh": round(state["total_kwh"], 5),
        "saved_kwh": round(state["saved_kwh"], 5),
        "saved_cost_inr": round(state["saved_cost_inr"], 2)
    }

    await manager.broadcast({"type": "ECO_STREAM", "data": update_data})
    return {"status": "success", "mode": state["mode"]}

@app.websocket("/ws/ecosense")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)