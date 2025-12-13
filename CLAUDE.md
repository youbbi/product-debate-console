# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent decision system that simulates an executive team (CFO, CPO, CTO, CRO) debating product decisions in parallel. Each agent provides domain-specific analysis, then a consensus is calculated and a final GO/PIVOT/HOLD recommendation is synthesized.

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server (serves both API and frontend on http://localhost:8000)
python backend/main.py
```

## Environment Variables

Create `.env` in project root (not in backend/):
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_KEY` - Azure API key
- `AZURE_DEPLOYMENT_GPT4` - Deployment name (default: gpt-4-turbo)
- `DEBUG`, `HOST`, `PORT` - Server config

## Architecture

### LangGraph Flow (backend/graph.py)

The debate runs as a sequential LangGraph workflow:

```
START → establish_context → parallel_exec_debate → analyze_consensus → synthesize_decision → END
```

1. **establish_context**: Creates evaluation lenses (financial, product-market fit, technical, revenue)
2. **parallel_exec_debate**: Runs all 4 executives simultaneously via `asyncio.gather()`
3. **analyze_consensus**: Calculates alignment score from exec recommendations
4. **synthesize_decision**: LLM synthesizes a final GO/PIVOT/HOLD recommendation

### State Management (backend/state.py)

`ProductDecisionState` is a TypedDict that flows through the graph, accumulating:
- Input: `query`, `context`
- Per-round: `executive_outputs`, `debate_rounds`
- Final: `recommendation_type`, `confidence_level`, `final_decision`

### Executive Agents (backend/agents.py)

Each executive is a `NamedTuple` with persona details and a specialized system prompt. They output structured JSON with role-specific fields:
- CFO: `financial_recommendation`, `roi_analysis`, `key_metrics`
- CPO: `product_recommendation`, `market_demand`, `product_roadmap_fit`
- CTO: `technology_recommendation`, `technical_feasibility`, `implementation_timeline`
- CRO: `revenue_recommendation`, `sales_impact`, `competitive_positioning_vs_rivals`

### Consensus Evaluation (backend/evaluators.py)

`ConsensusEvaluator.calculate_alignment()` maps exec recommendations to scores (go=90, pivot=60, hold=10) and computes alignment as inverse standard deviation. High alignment (>0.6) proceeds to synthesis; low alignment would trigger refinement rounds.

### Real-Time Updates (backend/websocket_manager.py)

Global `manager` singleton broadcasts events to all WebSocket clients:
- `exec_streaming` / `exec_complete`: Individual agent progress
- `consensus_update`: Alignment meter updates
- `final_decision`: Completed recommendation

### Frontend

Vanilla JS WebSocket client (`frontend/app.js`) renders executive cards in a grid, updates consensus bar, and displays final recommendation. No build step required.

## Adding New Executive Roles

1. Define new `ExecutiveAgent` in `backend/agents.py` with system prompt specifying JSON output keys
2. Add to `EXECUTIVES` dict and `EXEC_ORDER` list
3. Update `ConsensusEvaluator.extract_recommendations()` to parse new role's recommendation field
4. Add role to `EXECUTIVES` array in `frontend/app.js`
