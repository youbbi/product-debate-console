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
from llm_providers import get_available_provider_info, calculate_cost_estimate
from database import get_all_debates, get_debate_by_id, delete_debate

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

@app.get("/framework")
async def framework():
    """Serve the decision framework documentation"""
    return FileResponse("frontend/framework.html")

@app.get("/council-framework")
async def council_framework():
    """Serve the LLM Council framework documentation"""
    return FileResponse("frontend/council-framework.html")

@app.get("/api/providers")
async def get_providers():
    """Get list of available LLM providers for Council method"""
    providers = get_available_provider_info()
    return {
        "providers": providers,
        "count": len(providers),
        "council_available": len(providers) >= 2
    }

@app.get("/api/cost-estimate/{method}")
async def get_cost_estimate(method: str):
    """Get estimated API cost for a decision method"""
    if method not in ["consensus", "council", "both"]:
        return {"error": f"Unknown method: {method}"}
    return calculate_cost_estimate(method)

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

@app.get("/api/debates")
async def list_debates():
    """List all past debates"""
    debates = get_all_debates(limit=50)
    return {"debates": debates, "count": len(debates)}

@app.get("/api/debates/{debate_id}")
async def get_debate(debate_id: str):
    """Get full details of a specific debate"""
    debate = get_debate_by_id(debate_id)
    if not debate:
        return {"error": "Debate not found"}
    return debate

@app.delete("/api/debates/{debate_id}")
async def remove_debate(debate_id: str):
    """Delete a debate from history"""
    success = delete_debate(debate_id)
    return {"success": success}

# ============================================================================
# WebSocket for Real-Time Streaming
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time debate streaming"""
    await manager.connect(websocket)
    active_task = None  # Track the running debate task

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("type") == "start_debate":
                # Start new debate with selected method
                query = message.get("question")
                context = message.get("context", {})
                method = message.get("method", "consensus")  # Default to consensus

                # Validate method
                if method not in ["consensus", "council", "both"]:
                    await manager.broadcast({
                        "type": "error",
                        "message": f"Unknown method: {method}"
                    })
                    continue

                async def run_debate():
                    try:
                        # Run debate with selected method
                        result = await debate_graph.invoke_async(query, context, method=method)

                        # Broadcast completion
                        await manager.broadcast({
                            "type": "debate_complete",
                            "method": method,
                            "recommendation": result.get('recommendation_type'),
                            "confidence": result.get('confidence_level'),
                            "timestamp": datetime.now().isoformat()
                        })
                    except asyncio.CancelledError:
                        # Task was cancelled - broadcast cancellation
                        await manager.broadcast({
                            "type": "debate_cancelled",
                            "timestamp": datetime.now().isoformat()
                        })
                    except Exception as e:
                        await manager.broadcast({
                            "type": "error",
                            "message": str(e),
                            "timestamp": datetime.now().isoformat()
                        })

                # Start debate as a task so it can be cancelled
                active_task = asyncio.create_task(run_debate())

            elif message.get("type") == "cancel_debate":
                # Cancel the running debate
                if active_task and not active_task.done():
                    active_task.cancel()
                    active_task = None

            elif message.get("type") == "ping":
                # Keep-alive
                await manager.broadcast({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })

    except WebSocketDisconnect:
        # Cancel any running task on disconnect
        if active_task and not active_task.done():
            active_task.cancel()
        await manager.disconnect(websocket)

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    providers = Config.get_enabled_providers()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "azure_configured": bool(Config.AZURE_ENDPOINT),
        "enabled_providers": providers,
        "council_available": len(providers) >= 2
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
