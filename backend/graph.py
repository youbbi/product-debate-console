from langgraph.graph import StateGraph, START, END
import asyncio
import json
from datetime import datetime
import uuid
from typing import Optional

from config import Config
from state import ProductDecisionState, create_initial_state, ExecutiveOutput, DebateRound
from agents import get_all_executives
from evaluators import ConsensusEvaluator
from websocket_manager import manager
from council_graph import LLMCouncilGraph
from council_state import DualDecisionState, create_dual_state
from council_evaluators import CouncilEvaluator
from database import save_debate

class ProductDebateGraph:
    def __init__(self):
        self.llm = Config.get_llm(temperature=0.7)
        self.graph = self._build_graph()
        self.compiled = self.graph.compile()
        self._council_graph: Optional[LLMCouncilGraph] = None

    @property
    def council_graph(self) -> LLMCouncilGraph:
        """Lazy-load council graph only when needed"""
        if self._council_graph is None:
            self._council_graph = LLMCouncilGraph()
        return self._council_graph
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph with parallel execution"""
        workflow = StateGraph(ProductDecisionState)
        
        # Nodes
        workflow.add_node("establish_context", self._establish_context)
        workflow.add_node("parallel_exec_debate", self._parallel_exec_debate)
        workflow.add_node("analyze_consensus", self._analyze_consensus)
        workflow.add_node("synthesize_decision", self._synthesize_decision)
        
        # Edges
        workflow.add_edge(START, "establish_context")
        workflow.add_edge("establish_context", "parallel_exec_debate")
        workflow.add_edge("parallel_exec_debate", "analyze_consensus")
        workflow.add_edge("analyze_consensus", "synthesize_decision")
        workflow.add_edge("synthesize_decision", END)
        
        return workflow
    
    async def _establish_context(self, state: ProductDecisionState) -> dict:
        """Set up evaluation criteria"""
        prompt = f"""You are facilitating an executive team debate on a product decision.

Decision: {state['query']}
Company Context: {json.dumps(state['context'])}

Create 4-5 key evaluation lenses that the executive team should consider:
1. Financial viability (CFO lens)
2. Product-market fit & customer demand (CPO lens)
3. Technical feasibility & engineering effort (CTO lens)
4. Revenue & competitive impact (CRO lens)
5. (Optional strategic fit)

For each lens, provide:
- Name
- Key questions to ask
- Success criteria

Output JSON with key: evaluation_lenses"""
        
        response = self.llm.invoke([{"role": "user", "content": prompt}])
        
        try:
            data = json.loads(response.content)
            lenses = data.get('evaluation_lenses', [])
        except:
            lenses = ["Financial Viability", "Product-Market Fit", "Technical Feasibility", "Revenue Impact"]
        
        await manager.broadcast({
            "type": "context_established",
            "lenses": lenses,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "current_round": 1
        }
    
    async def _parallel_exec_debate(self, state: ProductDecisionState) -> dict:
        """Run all executives in parallel"""
        execs = get_all_executives()
        
        # Create tasks for parallel execution
        tasks = []
        for exec in execs:
            task = asyncio.create_task(
                self._get_exec_perspective(state, exec)
            )
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks)
        
        return {
            "executive_outputs": results,
            "debate_rounds": state['debate_rounds'] + [
                DebateRound(
                    round_number=state['current_round'],
                    timestamp=datetime.now().isoformat(),
                    executive_outputs=results,
                    consensus_analysis=None,
                    needs_refinement=False
                )
            ]
        }
    
    async def _get_exec_perspective(self, state: ProductDecisionState, exec):
        """Get single exec's perspective with real-time streaming"""

        # Build context-aware prompt
        prompt = f"""{exec.system_prompt}

DECISION UNDER REVIEW:
{state['query']}

COMPANY CONTEXT:
{json.dumps(state['context'], indent=2)}

Provide your analysis in JSON format."""

        # Broadcast that exec is starting (before streaming begins)
        input_summary = {
            "query_preview": state['query'][:100] + ("..." if len(state['query']) > 100 else ""),
            "context_keys": list(state['context'].keys()) if state['context'] else [],
            "primary_concern": exec.primary_concern
        }
        await manager.broadcast({
            "type": "exec_started",
            "role": exec.role,
            "name": exec.name,
            "emoji": exec.emoji,
            "title": exec.title,
            "input_summary": input_summary,
            "timestamp": datetime.now().isoformat()
        })

        # Stream LLM response token-by-token
        output_text = await manager.stream_exec_output(
            exec_role=exec.role,
            exec_name=exec.name,
            exec_emoji=exec.emoji,
            exec_title=exec.title,
            llm_response=self.llm.astream([{"role": "user", "content": prompt}])
        )

        # Parse JSON
        try:
            parsed = json.loads(output_text)
        except:
            parsed = None

        return ExecutiveOutput(
            role=exec.role,
            name=exec.name,
            title=exec.title,
            emoji=exec.emoji,
            output=output_text,
            parsed_data=parsed,
            timestamp=datetime.now().isoformat(),
            streaming_complete=True
        )
    
    async def _analyze_consensus(self, state: ProductDecisionState) -> dict:
        """Analyze agreement across execs"""
        consensus = ConsensusEvaluator.build_consensus_analysis(
            state['executive_outputs']
        )
        
        # Broadcast consensus update
        await manager.broadcast_consensus(consensus)
        
        return {
            "consensus_analysis": consensus,
            "overall_agreement_level": consensus['overall_consensus_level']
        }
    
    async def _synthesize_decision(self, state: ProductDecisionState) -> dict:
        """Synthesize final decision"""
        synthesis_prompt = f"""You are an executive facilitator synthesizing a product decision based on the executive team's inputs.

Decision Question: {state['query']}

Executive Perspectives:
{json.dumps([dict(o) for o in state['executive_outputs']], indent=2)}

Consensus Analysis:
Overall Agreement Level: {state['overall_agreement_level']:.0%}

Your job:
1. Synthesize the team's analysis into a clear recommendation
2. Highlight areas of strong consensus
3. Call out critical disagreements that need resolution
4. Make a clear GO/PIVOT/HOLD recommendation
5. Provide next steps

Output JSON with keys:
- recommendation (GO / PIVOT / HOLD)
- confidence_level (0-100%)
- executive_summary (2-3 sentences for the board)
- consensus_points (list of things team agrees on)
- disagreement_areas (list of remaining debates)
- critical_success_factors (list)
- recommended_next_steps (list with priority)
- reasoning (why this recommendation?)"""
        
        response = self.llm.invoke([{"role": "user", "content": synthesis_prompt}])
        
        try:
            final_data = json.loads(response.content)
            recommendation = final_data.get('recommendation', 'HOLD').upper()
            confidence = final_data.get('confidence_level', 50)
        except:
            recommendation = "HOLD"
            confidence = 50
        
        # Broadcast final decision
        await manager.broadcast_decision({
            "recommendation": recommendation,
            "confidence_level": confidence,
            "output": response.content
        })
        
        return {
            "final_decision": response.content,
            "recommendation_type": recommendation,
            "confidence_level": confidence,
            "end_time": datetime.now().isoformat()
        }
    
    async def invoke_async(
        self,
        query: str,
        context: dict = None,
        method: str = "consensus"
    ) -> dict:
        """Run the debate with selected method

        Args:
            query: The decision question
            context: Company context
            method: "consensus", "council", or "both"

        Returns:
            Result dict with method-specific structure
        """
        session_id = str(uuid.uuid4())[:8]

        if method == "consensus":
            return await self._run_consensus(query, context, session_id)
        elif method == "council":
            return await self._run_council(query, context, session_id)
        elif method == "both":
            return await self._run_both(query, context, session_id)
        else:
            raise ValueError(f"Unknown method: {method}")

    async def _run_consensus(
        self,
        query: str,
        context: dict,
        session_id: str
    ) -> ProductDecisionState:
        """Run the executive consensus debate"""
        state = create_initial_state(query, session_id, context)

        # Broadcast that we're using consensus method
        await manager.broadcast({
            "type": "debate_started",
            "method": "consensus",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })

        # Use async invocation since all nodes are async
        result = await self.compiled.ainvoke(state)

        # Save debate to history
        try:
            executives_data = {}
            for output in result.get('executive_outputs', []):
                executives_data[output.role] = {
                    'name': output.name,
                    'title': output.title,
                    'emoji': output.emoji,
                    'output': output.output,
                    'parsed_data': output.parsed_data
                }

            save_debate({
                'id': session_id,
                'question': query,
                'context': context,
                'recommendation': result.get('recommendation_type'),
                'confidence': result.get('confidence_level'),
                'consensus_level': result.get('overall_agreement_level'),
                'executives': executives_data,
                'final_decision': result.get('final_decision')
            })
        except Exception as e:
            print(f"Failed to save debate to history: {e}")

        return result

    async def _run_council(
        self,
        query: str,
        context: dict,
        session_id: str
    ) -> dict:
        """Run the LLM Council workflow"""
        # Broadcast that we're using council method
        await manager.broadcast({
            "type": "debate_started",
            "method": "council",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })

        result = await self.council_graph.invoke_async(query, context)
        return result

    async def _run_both(
        self,
        query: str,
        context: dict,
        session_id: str
    ) -> DualDecisionState:
        """Run both methods in parallel and compare results"""
        # Broadcast comparison started
        await manager.broadcast_comparison_started()

        # Run both in parallel
        consensus_task = asyncio.create_task(
            self._run_consensus(query, context, session_id + "_cons")
        )
        council_task = asyncio.create_task(
            self._run_council(query, context, session_id + "_cncl")
        )

        consensus_result, council_result = await asyncio.gather(
            consensus_task, council_task
        )

        # Compare results
        comparison = CouncilEvaluator.compare_decisions(
            dict(consensus_result),
            dict(council_result)
        )

        # Create dual state
        dual_state = create_dual_state(query, session_id, context, "both")
        dual_state['consensus_result'] = dict(consensus_result)
        dual_state['council_result'] = dict(council_result)
        dual_state['comparison'] = comparison
        dual_state['end_time'] = datetime.now().isoformat()

        # Broadcast comparison complete
        await manager.broadcast_comparison_complete(
            dict(consensus_result),
            dict(council_result),
            comparison
        )

        return dual_state
