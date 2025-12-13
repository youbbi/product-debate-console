from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import asyncio
import json
from datetime import datetime

from config import Config
from graph import ProductDebateGraph
from websocket_manager import manager
from state import create_initial_state

app = FastAPI(title="Product Strategy Debate Console")

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="frontend"), name="static")

debate_graph = ProductDebateGraph()

# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Serve the console"""
    return FileResponse("frontend/index.html")

@app.post("/api/debate")
async def start_debate(payload: dict):
    """Start a new debate session"""
    query = payload.get("question", "")
    context = payload.get("context", {})
    
    if not query:
        return {"error": "Question required"}
    
    try:
        # Run debate asynchronously
        result = await debate_graph.invoke_async(query, context)
        
        return {
            "session_id": result['session_id'],
            "status": "complete",
            "recommendation": result.get('recommendation_type'),
            "confidence": result.get('confidence_level'),
            "debate_summary": result.get('final_decision')
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Retrieve a past debate session"""
    # This would query your database
    return {"session_id": session_id, "status": "not_implemented"}

# ============================================================================
# WebSocket for Real-Time Streaming
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time debate streaming"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "start_debate":
                # Start new debate
                query = message.get("question")
                context = message.get("context", {})
                
                await manager.broadcast({
                    "type": "debate_started",
                    "timestamp": datetime.now().isoformat()
                })
                
                try:
                    result = await debate_graph.invoke_async(query, context)
                    
                    await manager.broadcast({
                        "type": "debate_complete",
                        "recommendation": result.get('recommendation_type'),
                        "confidence": result.get('confidence_level'),
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    await manager.broadcast({
                        "type": "error",
                        "message": str(e)
                    })
            
            elif message.get("type") == "ping":
                # Keep-alive
                await manager.broadcast({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket)

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "azure_configured": bool(Config.AZURE_ENDPOINT)
    }

# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info"
    )
