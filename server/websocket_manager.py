"""WebSocket Connection Manager for Device Continuity and Real-Time Streaming."""
import json
import logging
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("photosync.websocket")

class ConnectionManager:
    """Manages real-time bidirectional WebSocket connections between Web/Electron UI and Android devices."""
    
    def __init__(self):
        # Web dashboard & Electron app connections
        self.ui_connections: Set[WebSocket] = set()
        # Android device connections: device_id -> Set[WebSocket]
        self.device_connections: Dict[str, Set[WebSocket]] = {}
        # In-memory latest continuity state for instant hydrate on UI connect
        self.latest_state: Dict[str, Any] = {
            "battery": None,
            "media": None,
            "clipboard": None,
            "notifications": [],
            "connected_devices": []
        }

    async def connect_ui(self, websocket: WebSocket):
        await websocket.accept()
        self.ui_connections.add(websocket)
        # Send initial snapshot of device state
        await self.send_json(websocket, {
            "event": "STATE_SNAPSHOT",
            "data": self.latest_state
        })
        logger.info(f"UI WebSocket connected. Total UI clients: {len(self.ui_connections)}")

    def disconnect_ui(self, websocket: WebSocket):
        self.ui_connections.discard(websocket)
        logger.info(f"UI WebSocket disconnected. Total UI clients: {len(self.ui_connections)}")

    async def connect_device(self, device_id: str, websocket: WebSocket, device_name: str = "Android Device"):
        await websocket.accept()
        if device_id not in self.device_connections:
            self.device_connections[device_id] = set()
        self.device_connections[device_id].add(websocket)
        
        # Update connected devices list
        if not any(d.get("device_id") == device_id for d in self.latest_state["connected_devices"]):
            self.latest_state["connected_devices"].append({
                "device_id": device_id,
                "device_name": device_name,
                "online": True
            })

        logger.info(f"Device {device_id} ({device_name}) connected. Total sockets for device: {len(self.device_connections[device_id])}")
        
        # Notify UI of device connection
        await self.broadcast_to_ui("DEVICE_CONNECTED", {
            "device_id": device_id,
            "device_name": device_name
        })

    async def disconnect_device(self, device_id: str, websocket: WebSocket):
        if device_id in self.device_connections:
            self.device_connections[device_id].discard(websocket)
            if not self.device_connections[device_id]:
                del self.device_connections[device_id]
                # Mark offline in state
                for d in self.latest_state["connected_devices"]:
                    if d.get("device_id") == device_id:
                        d["online"] = False
                logger.info(f"Device {device_id} completely disconnected.")
                await self.broadcast_to_ui("DEVICE_DISCONNECTED", {"device_id": device_id})

    async def broadcast_to_ui(self, event_type: str, data: Any):
        """Send event payload to all connected UI dashboards / Electron shells."""
        dead_connections = set()
        payload = {"event": event_type, "data": data}
        for ws in self.ui_connections:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead_connections.add(ws)
        for dead in dead_connections:
            self.ui_connections.discard(dead)

    async def send_to_device(self, device_id: str, event_type: str, data: Any) -> bool:
        """Send command to specific Android device."""
        sockets = self.device_connections.get(device_id, set())
        if not sockets:
            return False
        dead = set()
        sent = False
        payload = {"event": event_type, "data": data}
        for ws in sockets:
            try:
                await ws.send_text(json.dumps(payload))
                sent = True
            except Exception:
                dead.add(ws)
        for d in dead:
            sockets.discard(d)
        return sent

    async def broadcast_to_devices(self, event_type: str, data: Any):
        """Broadcast payload (e.g., Clipboard update from PC) to all connected Android phones."""
        payload = {"event": event_type, "data": data}
        for device_id, sockets in list(self.device_connections.items()):
            dead = set()
            for ws in sockets:
                try:
                    await ws.send_text(json.dumps(payload))
                except Exception:
                    dead.add(ws)
            for d in dead:
                sockets.discard(d)

    async def handle_device_event(self, device_id: str, event_type: str, data: dict):
        """Process an inbound continuity event from an Android client."""
        if event_type == "BATTERY_STATUS":
            self.latest_state["battery"] = {**data, "device_id": device_id}
            await self.broadcast_to_ui("BATTERY_STATUS", self.latest_state["battery"])

        elif event_type == "NOTIFICATION_POSTED":
            # Add to ring buffer (keep last 40)
            notifs = self.latest_state["notifications"]
            # Filter out existing with same id if already present
            notif_id = data.get("id")
            notifs = [n for n in notifs if n.get("id") != notif_id]
            notifs.insert(0, {**data, "device_id": device_id})
            self.latest_state["notifications"] = notifs[:40]
            await self.broadcast_to_ui("NOTIFICATION_POSTED", {**data, "device_id": device_id})

        elif event_type == "NOTIFICATION_DISMISSED":
            notif_id = data.get("id")
            self.latest_state["notifications"] = [
                n for n in self.latest_state["notifications"] if n.get("id") != notif_id
            ]
            await self.broadcast_to_ui("NOTIFICATION_DISMISSED", data)

        elif event_type == "CALL_INCOMING":
            await self.broadcast_to_ui("CALL_INCOMING", {**data, "device_id": device_id})

        elif event_type == "MEDIA_PLAYBACK_STATUS":
            self.latest_state["media"] = {**data, "device_id": device_id}
            await self.broadcast_to_ui("MEDIA_PLAYBACK_STATUS", self.latest_state["media"])

        elif event_type == "CLIPBOARD_UPDATE":
            self.latest_state["clipboard"] = data
            await self.broadcast_to_ui("CLIPBOARD_UPDATE", data)

        elif event_type == "PING":
            await self.send_to_device(device_id, "PONG", {})

    async def handle_ui_event(self, websocket: WebSocket, event_type: str, data: dict):
        """Process an event from Web Dashboard or Electron shell."""
        if event_type == "MEDIA_CONTROL_COMMAND":
            device_id = data.get("device_id")
            action = data.get("action")  # PLAY, PAUSE, NEXT, PREV
            if device_id:
                await self.send_to_device(device_id, "MEDIA_CONTROL_COMMAND", {"action": action})
            else:
                await self.broadcast_to_devices("MEDIA_CONTROL_COMMAND", {"action": action})

        elif event_type == "NOTIFICATION_ACTION":
            # Action: DISMISS or REPLY
            device_id = data.get("device_id")
            if device_id:
                await self.send_to_device(device_id, "NOTIFICATION_ACTION", data)
            else:
                await self.broadcast_to_devices("NOTIFICATION_ACTION", data)

        elif event_type == "CLIPBOARD_UPDATE":
            self.latest_state["clipboard"] = data
            # Forward to Android devices
            await self.broadcast_to_devices("CLIPBOARD_UPDATE", data)
            # Echo to any other UI tabs
            await self.broadcast_to_ui("CLIPBOARD_UPDATE", data)

        elif event_type == "GET_STATE":
            await self.send_json(websocket, {
                "event": "STATE_SNAPSHOT",
                "data": self.latest_state
            })

    async def send_json(self, websocket: WebSocket, payload: dict):
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            pass

ws_manager = ConnectionManager()
