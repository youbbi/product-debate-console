"""
LLM Council Graph

Implements the three-stage LangGraph workflow for the Council decision method:
1. Divergence: Broadcast query to all LLMs in parallel
2. Convergence: Each LLM reviews other responses anonymously (peer review)
3. Synthesis: Chairman LLM synthesizes final decision based on ratings
"""

from langgraph.graph import StateGraph, START, END
import asyncio
import json
import logging
from datetime import datetime
import uuid
from typing import List

from config import Config
from llm_providers import get_configured_providers, get_provider, LLMProvider
from council_state import (
    CouncilDecisionState,
    create_council_state,
    LLMResponse,
    PeerReview
)
from council_evaluators import CouncilEvaluator
from websocket_manager import manager


class LLMCouncilGraph:
    """LangGraph workflow for LLM Council decision method"""

    def __init__(self):
        self.providers = get_configured_providers()
        self.graph = self._build_graph()
        self.compiled = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph with 3-stage Council workflow"""
        workflow = StateGraph(CouncilDecisionState)

        # Nodes
        workflow.add_node("broadcast_divergence", self._broadcast_divergence)
        workflow.add_node("parallel_peer_review", self._parallel_peer_review)
        workflow.add_node("chairman_synthesis", self._chairman_synthesis)

        # Edges
        workflow.add_edge(START, "broadcast_divergence")
        workflow.add_edge("broadcast_divergence", "parallel_peer_review")
        workflow.add_edge("parallel_peer_review", "chairman_synthesis")
        workflow.add_edge("chairman_synthesis", END)

        return workflow

    async def _broadcast_divergence(self, state: CouncilDecisionState) -> dict:
        """Stage 1: Send query to all LLMs in parallel"""

        # Get available providers
        providers = get_configured_providers()
        if len(providers) < 2:
            raise ValueError(f"Council requires at least 2 providers, found {len(providers)}")

        # Create anonymous IDs for providers and map to actual names
        provider_ids = [f"llm_{i+1}" for i in range(len(providers))]
        provider_names = {f"llm_{i+1}": p.name for i, p in enumerate(providers)}

        # Broadcast divergence start with provider names
        await manager.broadcast({
            "type": "council_divergence_start",
            "providers": provider_ids,
            "provider_names": provider_names,
            "total_providers": len(providers),
            "timestamp": datetime.now().isoformat()
        })

        # Build divergence prompt
        prompt = CouncilEvaluator.build_divergence_prompt(
            state['query'],
            state['context']
        )

        # Create tasks for parallel execution
        async def get_llm_response(provider: LLMProvider, provider_id: str) -> LLMResponse:
            """Get response from a single LLM with streaming"""
            logging.info(f"[Council] Starting provider {provider_id} ({provider.name})")
            try:
                # Stream response
                full_response = ""
                token_count = 0
                async for token in provider.astream(prompt):
                    token_count += 1
                    full_response += token
                    await manager.broadcast({
                        "type": "council_response_streaming",
                        "provider_id": provider_id,
                        "provider_name": provider.name,
                        "token": token,
                        "timestamp": datetime.now().isoformat()
                    })

                # Parse JSON from response
                try:
                    if "```json" in full_response:
                        json_str = full_response.split("```json")[1].split("```")[0]
                    elif "```" in full_response:
                        json_str = full_response.split("```")[1].split("```")[0]
                    else:
                        json_str = full_response
                    parsed = json.loads(json_str.strip())
                except:
                    parsed = None

                response = LLMResponse(
                    provider_id=provider_id,
                    provider_name=provider.name,
                    response=full_response,
                    parsed_data=parsed,
                    timestamp=datetime.now().isoformat(),
                    streaming_complete=True
                )

                logging.info(f"[Council] Completed {provider_id} ({provider.name}): {token_count} tokens")

                # Broadcast completion
                await manager.broadcast({
                    "type": "council_response_complete",
                    "provider_id": provider_id,
                    "provider_name": provider.name,
                    "response": full_response[:500] + "..." if len(full_response) > 500 else full_response,
                    "parsed_data": parsed,
                    "timestamp": datetime.now().isoformat()
                })

                return response

            except Exception as e:
                logging.error(f"[Council] {provider_id} ({provider.name}) failed: {type(e).__name__}: {str(e)}")

                # Broadcast error event so frontend knows
                await manager.broadcast({
                    "type": "council_response_error",
                    "provider_id": provider_id,
                    "provider_name": provider.name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

                # Return error response
                return LLMResponse(
                    provider_id=provider_id,
                    provider_name=provider.name,
                    response=f"Error: {str(e)}",
                    parsed_data=None,
                    timestamp=datetime.now().isoformat(),
                    streaming_complete=True
                )

        # Run all providers in parallel
        tasks = [
            get_llm_response(provider, provider_id)
            for provider, provider_id in zip(providers, provider_ids)
        ]
        responses = await asyncio.gather(*tasks)

        # Analyze divergence between responses
        divergence_analysis = CouncilEvaluator.analyze_divergence(list(responses))

        # Broadcast divergence analysis for UI highlighting
        await manager.broadcast({
            "type": "council_divergence_analysis",
            "analysis": divergence_analysis,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "llm_responses": list(responses),
            "divergence_complete": True,
            "total_providers": len(providers),
            "divergence_analysis": divergence_analysis
        }

    async def _parallel_peer_review(self, state: CouncilDecisionState) -> dict:
        """Stage 2: Each LLM reviews other responses anonymously"""

        responses = state['llm_responses']
        providers = get_configured_providers()

        # Broadcast peer review start
        await manager.broadcast({
            "type": "council_peer_review_start",
            "total_reviews": len(responses) * (len(responses) - 1),
            "timestamp": datetime.now().isoformat()
        })

        peer_reviews: List[PeerReview] = []

        # Each LLM reviews all other responses
        async def review_response(
            reviewer_provider: LLMProvider,
            reviewer_id: str,
            target_response: LLMResponse
        ) -> PeerReview:
            """One LLM reviews another's response"""
            target_id = target_response['provider_id']

            # Build review prompt
            prompt = CouncilEvaluator.build_peer_review_prompt(
                target_response['response'],
                target_id,
                state['query'],
                state['context']
            )

            try:
                # Get review
                review_text = await reviewer_provider.invoke(prompt)

                # Parse review
                parsed = CouncilEvaluator.parse_peer_review(review_text)
                if parsed:
                    review = PeerReview(
                        reviewer_id=reviewer_id,
                        target_id=target_id,
                        score=parsed['score'],
                        critique=parsed['critique'],
                        strengths=parsed['strengths'],
                        weaknesses=parsed['weaknesses']
                    )
                else:
                    review = PeerReview(
                        reviewer_id=reviewer_id,
                        target_id=target_id,
                        score=5,
                        critique="Unable to parse review",
                        strengths=[],
                        weaknesses=[]
                    )

                # Broadcast review
                await manager.broadcast({
                    "type": "council_peer_review",
                    "reviewer_id": reviewer_id,
                    "target_id": target_id,
                    "score": review['score'],
                    "timestamp": datetime.now().isoformat()
                })

                return review

            except Exception as e:
                return PeerReview(
                    reviewer_id=reviewer_id,
                    target_id=target_id,
                    score=5,
                    critique=f"Review failed: {str(e)}",
                    strengths=[],
                    weaknesses=[]
                )

        # Create review tasks
        review_tasks = []
        for i, (reviewer_provider, reviewer_resp) in enumerate(zip(providers, responses)):
            reviewer_id = reviewer_resp['provider_id']
            for target_resp in responses:
                # Don't review yourself
                if target_resp['provider_id'] != reviewer_id:
                    review_tasks.append(
                        review_response(reviewer_provider, reviewer_id, target_resp)
                    )

        # Run all reviews in parallel
        reviews = await asyncio.gather(*review_tasks)
        peer_reviews = list(reviews)

        # Aggregate ratings
        rating_matrix = CouncilEvaluator.aggregate_ratings(peer_reviews)

        # Broadcast rating matrix
        await manager.broadcast({
            "type": "council_rating_matrix",
            "matrix": {
                "aggregated_scores": rating_matrix['aggregated_scores'],
                "highest_rated": rating_matrix['highest_rated'],
                "lowest_rated": rating_matrix['lowest_rated'],
                "score_variance": rating_matrix['score_variance']
            },
            "timestamp": datetime.now().isoformat()
        })

        return {
            "peer_reviews": peer_reviews,
            "rating_matrix": rating_matrix,
            "convergence_complete": True
        }

    async def _chairman_synthesis(self, state: CouncilDecisionState) -> dict:
        """Stage 3: Chairman LLM synthesizes final decision"""

        # Determine chairman (use configured or highest-rated)
        chairman_id = Config.COUNCIL_CHAIRMAN_PROVIDER
        chairman_provider = get_provider(chairman_id)

        if not chairman_provider:
            # Fall back to highest-rated provider
            highest_rated = state['rating_matrix']['highest_rated']
            for resp in state['llm_responses']:
                if resp['provider_id'] == highest_rated:
                    chairman_provider = get_provider(resp['provider_name'].lower().split()[0])
                    chairman_id = resp['provider_name']
                    break

        if not chairman_provider:
            # Last resort: use first available
            chairman_provider = get_configured_providers()[0]
            chairman_id = chairman_provider.name

        # Broadcast synthesis start
        await manager.broadcast({
            "type": "council_synthesis_start",
            "chairman_provider": chairman_id,
            "timestamp": datetime.now().isoformat()
        })

        # Build chairman prompt
        prompt = CouncilEvaluator.build_chairman_prompt(
            state['query'],
            state['context'],
            state['llm_responses'],
            state['rating_matrix']
        )

        # Get chairman's synthesis with streaming
        full_response = ""
        async for token in chairman_provider.astream(prompt):
            full_response += token
            await manager.broadcast({
                "type": "council_synthesis_streaming",
                "token": token,
                "timestamp": datetime.now().isoformat()
            })

        # Parse final decision
        try:
            if "```json" in full_response:
                json_str = full_response.split("```json")[1].split("```")[0]
            elif "```" in full_response:
                json_str = full_response.split("```")[1].split("```")[0]
            else:
                json_str = full_response
            final_data = json.loads(json_str.strip())
            recommendation = final_data.get('recommendation', 'HOLD').upper()
            confidence = final_data.get('confidence_level', 50)
            weighted_reasoning = final_data.get('weighted_reasoning', '')
        except:
            recommendation = "HOLD"
            confidence = 50
            weighted_reasoning = "Unable to parse synthesis"
            final_data = {"recommendation": recommendation, "confidence_level": confidence}

        # Broadcast final decision
        await manager.broadcast({
            "type": "council_final_decision",
            "decision": {
                "recommendation": recommendation,
                "confidence_level": confidence,
                "weighted_reasoning": weighted_reasoning,
                "executive_summary": final_data.get('executive_summary', ''),
                "key_insights": final_data.get('key_insights_from_council', []),
                "next_steps": final_data.get('recommended_next_steps', [])
            },
            "chairman_provider": chairman_id,
            "timestamp": datetime.now().isoformat()
        })

        return {
            "chairman_provider": chairman_id,
            "chairman_response": full_response,
            "final_decision": json.dumps(final_data),
            "recommendation_type": recommendation,
            "confidence_level": confidence,
            "weighted_reasoning": weighted_reasoning,
            "end_time": datetime.now().isoformat()
        }

    async def invoke_async(
        self,
        query: str,
        context: dict = None
    ) -> CouncilDecisionState:
        """Run the Council workflow"""
        session_id = str(uuid.uuid4())[:8]
        state = create_council_state(
            query=query,
            session_id=session_id,
            context=context,
            total_providers=len(self.providers)
        )

        # Use async invocation
        result = await self.compiled.ainvoke(state)
        return result
