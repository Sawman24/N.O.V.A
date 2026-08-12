import json
import uuid
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["websocket"])


class ClientBridgeManager:
    def __init__(self):
        self.active_clients: Dict[str, WebSocket] = {}
        self.pending_rpcs: Dict[str, asyncio.Future] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_clients[client_id] = websocket
        print(f"[Nova Bridge] Client '{client_id}' connected.")

    def disconnect(self, client_id: str):
        if client_id in self.active_clients:
            del self.active_clients[client_id]
            print(f"[Nova Bridge] Client '{client_id}' disconnected.")

    async def send_rpc(self, client_id: str, action: str, params: Dict[str, Any], timeout: float = 60.0) -> Any:
        if not self.active_clients:
            return "Error: No desktop client app is currently connected to Nova."

        # Default to first connected client if client_id is 'default' or not found
        ws = self.active_clients.get(client_id)
        if not ws:
            ws = list(self.active_clients.values())[0]

        rpc_id = str(uuid.uuid4())[:8]
        future = asyncio.get_running_loop().create_future()
        self.pending_rpcs[rpc_id] = future

        try:
            payload = {
                "rpc_id": rpc_id,
                "action": action,
                "params": params
            }
            await ws.send_text(json.dumps(payload))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            return f"Error: Remote desktop RPC call '{action}' timed out after {timeout} seconds."
        except Exception as e:
            return f"Error executing remote RPC '{action}': {e}"
        finally:
            self.pending_rpcs.pop(rpc_id, None)

    def handle_response(self, rpc_id: str, result: Any, error: str = None):
        if rpc_id in self.pending_rpcs:
            future = self.pending_rpcs[rpc_id]
            if not future.done():
                if error:
                    future.set_result(f"Error from desktop client: {error}")
                else:
                    future.set_result(result)


bridge_manager = ClientBridgeManager()


@router.websocket("/client")
@router.websocket("/client/{client_id}")
async def websocket_client_endpoint(websocket: WebSocket, client_id: str = "default_pc"):
    await bridge_manager.connect(client_id, websocket)
    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                rpc_id = msg.get("rpc_id")
                result = msg.get("result")
                error = msg.get("error")
                if rpc_id:
                    bridge_manager.handle_response(rpc_id, result, error)
            except Exception as e:
                print(f"[Nova Bridge] Malformed message from client '{client_id}': {e}")
    except WebSocketDisconnect:
        bridge_manager.disconnect(client_id)
