import asyncio
import json
from typing import Callable, Optional
from datetime import datetime

class WebSocketManager:
    """Manages WebSocket connections for real-time streaming"""
    
    def __init__(self):
        self.active_connections = []
    
    async def connect(self, websocket):
        """Client connects"""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    async def disconnect(self, websocket):
        """Client disconnects"""
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass
    
    async def stream_exec_output(self,
                                 exec_role: str,
                                 exec_name: str,
                                 exec_emoji: str,
                                 exec_title: str,
                                 llm_response):
        """Stream LLM response token-by-token from exec"""

        buffer = ""

        # Stream the response - handle LangChain's AIMessageChunk format
        async for chunk in llm_response:
            token = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if not token:
                continue
            buffer += token

            # Send token update
            await self.broadcast({
                "type": "exec_streaming",
                "role": exec_role,
                "name": exec_name,
                "emoji": exec_emoji,
                "title": exec_title,
                "token": token,
                "timestamp": datetime.now().isoformat()
            })

            await asyncio.sleep(0.01)  # Small delay for visual effect

        # Send completion with full output
        await self.broadcast({
            "type": "exec_complete",
            "role": exec_role,
            "name": exec_name,
            "emoji": exec_emoji,
            "title": exec_title,
            "output": buffer,
            "timestamp": datetime.now().isoformat()
        })

        return buffer
    
    async def broadcast_consensus(self, consensus: dict):
        """Broadcast updated consensus metrics"""
        await self.broadcast({
            "type": "consensus_update",
            "consensus": consensus,
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_decision(self, decision: dict):
        """Broadcast final decision"""
        await self.broadcast({
            "type": "final_decision",
            "decision": decision,
            "timestamp": datetime.now().isoformat()
        })

# Global manager
manager = WebSocketManager()
