from typing import TypedDict, List, Dict, Optional
from datetime import datetime

class ExecutiveOutput(TypedDict):
    """Output from one exec"""
    role: str
    name: str
    title: str
    emoji: str
    output: str
    parsed_data: Optional[Dict]
    timestamp: str
    streaming_complete: bool

class ConsensusAnalysis(TypedDict):
    """Analysis of agreement across execs"""
    overall_consensus_level: float  # 0-1
    areas_of_agreement: List[str]
    areas_of_disagreement: List[str]
    critical_contradictions: List[Dict]
    outliers: List[str]  # Which execs are out of sync?
    next_action: str  # "synthesize" or "refine"

class DebateRound(TypedDict):
    """One round of executive debate"""
    round_number: int
    timestamp: str
    executive_outputs: List[ExecutiveOutput]
    consensus_analysis: Optional[ConsensusAnalysis]
    needs_refinement: bool

class ProductDecisionState(TypedDict):
    """Complete state for product debate"""
    # Input
    query: str
    context: Dict  # Company size, team, constraints, etc.
    
    # Debate flow
    current_round: int
    debate_rounds: List[DebateRound]
    executive_outputs: List[ExecutiveOutput]  # Current round
    
    # Consensus building
    consensus_analysis: Optional[ConsensusAnalysis]
    overall_agreement_level: float
    
    # Final decision
    final_decision: Optional[str]
    recommendation_type: Optional[str]  # "proceed", "pivot", "hold"
    confidence_level: Optional[float]
    decision_rationale: Optional[str]
    
    # Metadata
    session_id: str
    start_time: str
    end_time: Optional[str]
    total_tokens: int

def create_initial_state(query: str, session_id: str, context: Dict = None) -> ProductDecisionState:
    """Factory for initial state"""
    return ProductDecisionState(
        query=query,
        context=context or {},
        current_round=0,
        debate_rounds=[],
        executive_outputs=[],
        consensus_analysis=None,
        overall_agreement_level=0.0,
        final_decision=None,
        recommendation_type=None,
        confidence_level=None,
        decision_rationale=None,
        session_id=session_id,
        start_time=datetime.now().isoformat(),
        end_time=None,
        total_tokens=0
    )
