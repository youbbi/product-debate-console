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

    # ============================================================================
    # Council-specific broadcast methods
    # ============================================================================

    async def broadcast_council_divergence_start(self, providers: list):
        """Notify clients that Council divergence phase started"""
        await self.broadcast({
            "type": "council_divergence_start",
            "providers": providers,
            "total_providers": len(providers),
            "timestamp": datetime.now().isoformat()
        })

    async def stream_council_response(self, provider_id: str, token: str):
        """Stream individual LLM response during divergence"""
        await self.broadcast({
            "type": "council_response_streaming",
            "provider_id": provider_id,
            "token": token,
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_council_response_complete(self, provider_id: str, response: str, parsed_data: dict = None):
        """Notify that one LLM has completed its response"""
        await self.broadcast({
            "type": "council_response_complete",
            "provider_id": provider_id,
            "response": response[:500] + "..." if len(response) > 500 else response,
            "parsed_data": parsed_data,
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_peer_review(self, reviewer_id: str, target_id: str, score: int):
        """Broadcast individual peer review completion"""
        await self.broadcast({
            "type": "council_peer_review",
            "reviewer_id": reviewer_id,
            "target_id": target_id,
            "score": score,
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_rating_matrix(self, matrix: dict):
        """Broadcast completed rating matrix"""
        await self.broadcast({
            "type": "council_rating_matrix",
            "matrix": matrix,
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_council_decision(self, decision: dict, chairman_provider: str):
        """Broadcast final council decision from chairman"""
        await self.broadcast({
            "type": "council_final_decision",
            "decision": decision,
            "chairman_provider": chairman_provider,
            "timestamp": datetime.now().isoformat()
        })

    # ============================================================================
    # Comparison broadcast methods
    # ============================================================================

    async def broadcast_comparison_started(self):
        """Notify that both methods are running in parallel"""
        await self.broadcast({
            "type": "comparison_started",
            "timestamp": datetime.now().isoformat()
        })

    async def broadcast_comparison_complete(self, consensus_result: dict, council_result: dict, comparison: dict):
        """Broadcast comparison results when both methods complete"""
        await self.broadcast({
            "type": "comparison_complete",
            "consensus": consensus_result,
            "council": council_result,
            "comparison": comparison,
            "timestamp": datetime.now().isoformat()
        })


# Global manager
manager = WebSocketManager()
