# Product Strategy Debate Console

A real-time web console where your SaaS executive team (CFO, CPO, CTO, CRO) debates product decisions in parallel with live consensus visualization.

## Features

✅ **Parallel Execution** - All 4 executives analyze simultaneously  
✅ **Real-Time Streaming** - See each exec's thinking as it happens  
✅ **Live Consensus Meter** - Watch agreement level update in real-time  
✅ **Beautiful Web UI** - No command line needed  
✅ **Executive Personas** - CFO, CPO, CTO, CRO with specialized viewpoints  
✅ **Final Decision** - Clear GO/PIVOT/HOLD recommendation with rationale  

## Project Structure

```
product-debate-console/
├── backend/
│   ├── main.py              ← FastAPI server
│   ├── config.py            ← Azure OpenAI setup
│   ├── agents.py            ← Exec personas (CFO, CPO, CTO, CRO)
│   ├── state.py             ← Data types
│   ├── graph.py             ← LangGraph with parallel execution
│   ├── evaluators.py        ← Consensus calculation
│   └── websocket_manager.py ← Real-time streaming
│
├── frontend/
│   ├── index.html           ← Main UI
│   ├── style.css            ← Styling
│   └── app.js               ← WebSocket client
│
├── .env                     ← Your Azure credentials
└── requirements.txt         ← Python dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install packages
pip install -r requirements.txt
```

### 2. Configure Azure OpenAI

Create `.env` file in project root:

```bash
AZURE_OPENAI_ENDPOINT=https://YOUR_INSTANCE.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_DEPLOYMENT_GPT4=gpt-4-turbo
DEBUG=true
```

### 3. Start the Server

```bash
python backend/main.py
```

You should see:
```
✓ Azure OpenAI credentials loaded
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 4. Open the Console

Visit: `http://localhost:8000`

## Usage

### Example Debate

**Question:**
```
Should we build a collaborative AI editor as a new product 
or focus on integrating AI into our existing platform?
```

**Context (optional):**
```json
{
  "company_size": "150 people",
  "current_revenue": "$40M ARR",
  "engineering_team": "25 engineers",
  "market_position": "leading in code intelligence",
  "timeline": "decision needed by end of Q1"
}
```

**Click "Start Debate"**

The system will:
1. Decompose your question into evaluation criteria
2. Stream all 4 execs analyzing in parallel
3. Display real-time consensus agreement meter
4. Show final GO/PIVOT/HOLD decision with confidence

## Executive Personas

| Exec | Role | Primary Concern |
|------|------|-----------------|
| **CPO** (Jamie Rodriguez) 🎯 | Product Strategy | Customer needs, product-market fit |
| **CFO** (Alex Chen) 💰 | Financial Viability | ROI, profitability, capital efficiency |
| **CTO** (Sam Park) ⚙️ | Technical Feasibility | Engineering effort, scalability |
| **CRO** (Taylor Morgan) 📈 | Revenue Impact | Sales cycles, competitive positioning |

## Customization

### Change Executive Personas

Edit `backend/agents.py` to modify or add new executive roles:

```python
CHIEF_MARKETING_OFFICER = ExecutiveAgent(
    name="Morgan Lee",
    title="Chief Marketing Officer",
    emoji="📢",
    role="cmo",
    system_prompt="""You are Morgan, the CMO...""",
    temperature=0.7,
    primary_concern="Brand positioning, market awareness"
)
```

### Adjust Debate Settings

Edit `backend/config.py`:

```python
MAX_DEBATE_ROUNDS = 2
ENABLE_PARALLEL = True
STREAMING_ENABLED = True
```

## Troubleshooting

**"WebSocket connection failed"**
- Make sure backend is running: `python backend/main.py`
- Check it's on `http://localhost:8000` (not HTTPS)

**"AZURE_OPENAI_ENDPOINT not set"**
- Create `.env` file in project root (not in backend/)
- Reload server after updating `.env`

**"Token limit exceeded"**
- Reduce `max_tokens` in `config.py` (currently 2500)
- Reduce context size in your inputs

## Next Steps

1. **Try real questions** - Ask actual product decisions
2. **Iterate on prompts** - Refine what each exec cares about
3. **Add persistence** - Save sessions for historical comparison
4. **Deploy** - Share with your actual team
5. **Add refinement** - Enable execs to debate each other across rounds

## License

MIT
