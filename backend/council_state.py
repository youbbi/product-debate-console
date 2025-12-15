"""
State types for LLM Council workflow

The Council method uses a three-stage process:
1. Divergence: Multiple LLMs answer the same query
2. Convergence: Each LLM anonymously reviews other responses
3. Synthesis: Chairman LLM produces final decision based on ratings
"""

from typing import TypedDict, List, Dict, Optional
from datetime import datetime


class LLMResponse(TypedDict):
    """Response from one LLM during divergence stage"""
    provider_id: str  # Anonymous ID during peer review (e.g., "llm_1")
    provider_name: str  # Actual provider name (revealed after synthesis)
    response: str  # Raw text response
    parsed_data: Optional[Dict]  # Parsed JSON if applicable
    timestamp: str
    streaming_complete: bool


class PeerReview(TypedDict):
    """One LLM's review of another's response"""
    reviewer_id: str  # Who is reviewing (anonymous)
    target_id: str  # Whose response is being reviewed (anonymous)
    score: int  # 1-10 rating
    critique: str  # Explanation of the rating
    strengths: List[str]  # What was good about the response
    weaknesses: List[str]  # What could be improved


class RatingMatrix(TypedDict):
    """Aggregated peer review data"""
    reviews: List[PeerReview]  # All individual reviews
    aggregated_scores: Dict[str, float]  # provider_id -> average score received
    score_variance: float  # How much scores varied (agreement measure)
    highest_rated: str  # provider_id with highest average
    lowest_rated: str  # provider_id with lowest average


class CouncilDecisionState(TypedDict):
    """Complete state for Council workflow"""
    # Input
    query: str
    context: Dict

    # Stage 1: Divergence
    llm_responses: List[LLMResponse]
    divergence_complete: bool

    # Stage 2: Convergence (Peer Review)
    peer_reviews: List[PeerReview]
    rating_matrix: Optional[RatingMatrix]
    convergence_complete: bool

    # Stage 3: Synthesis
    chairman_provider: str  # Which LLM is the chairman
    chairman_response: Optional[str]  # Chairman's synthesis
    final_decision: Optional[str]  # Full decision JSON
    recommendation_type: Optional[str]  # GO / PIVOT / HOLD
    confidence_level: Optional[float]  # 0-100%
    weighted_reasoning: Optional[str]  # How ratings influenced decision

    # Metadata
    session_id: str
    method: str  # "council"
    start_time: str
    end_time: Optional[str]
    total_providers: int


class ComparisonResult(TypedDict):
    """Comparison between Consensus and Council methods"""
    consensus_recommendation: str
    council_recommendation: str
    recommendations_match: bool
    consensus_confidence: float
    council_confidence: float
    confidence_difference: float
    consensus_reasoning: str
    council_reasoning: str
    key_differences: List[str]
    combined_insight: str


class DualDecisionState(TypedDict):
    """State for running both methods in parallel"""
    # Shared input
    query: str
    context: Dict
    method: str  # "consensus", "council", or "both"

    # Consensus results (from existing ProductDecisionState)
    consensus_result: Optional[Dict]

    # Council results
    council_result: Optional[CouncilDecisionState]

    # Comparison (when method == "both")
    comparison: Optional[ComparisonResult]

    # Metadata
    session_id: str
    start_time: str
    end_time: Optional[str]


def create_council_state(
    query: str,
    session_id: str,
    context: Dict = None,
    total_providers: int = 3
) -> CouncilDecisionState:
    """Factory for initial Council state"""
    return CouncilDecisionState(
        query=query,
        context=context or {},
        llm_responses=[],
        divergence_complete=False,
        peer_reviews=[],
        rating_matrix=None,
        convergence_complete=False,
        chairman_provider="",
        chairman_response=None,
        final_decision=None,
        recommendation_type=None,
        confidence_level=None,
        weighted_reasoning=None,
        session_id=session_id,
        method="council",
        start_time=datetime.now().isoformat(),
        end_time=None,
        total_providers=total_providers
    )


def create_dual_state(
    query: str,
    session_id: str,
    context: Dict = None,
    method: str = "both"
) -> DualDecisionState:
    """Factory for dual decision state"""
    return DualDecisionState(
        query=query,
        context=context or {},
        method=method,
        consensus_result=None,
        council_result=None,
        comparison=None,
        session_id=session_id,
        start_time=datetime.now().isoformat(),
        end_time=None
    )
