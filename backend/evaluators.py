import json
from typing import Dict, List

class ConsensusEvaluator:
    """Analyzes agreement across executives"""
    
    @staticmethod
    def extract_recommendations(exec_outputs: List[Dict]) -> Dict[str, str]:
        """Extract recommendation from each exec"""
        recommendations = {}
        
        for output in exec_outputs:
            try:
                data = json.loads(output['output'])
                role = output['role']
                
                if role == "cfo":
                    recommendations[role] = data.get('financial_recommendation', 'hold')
                elif role == "cpo":
                    recommendations[role] = data.get('product_recommendation', 'hold')
                elif role == "cto":
                    recommendations[role] = data.get('technology_recommendation', 'no_build')
                elif role == "cro":
                    recommendations[role] = data.get('revenue_recommendation', 'neutral')
            except:
                recommendations[output['role']] = 'unknown'
        
        return recommendations
    
    @staticmethod
    def calculate_alignment(recommendations: Dict[str, str]) -> float:
        """Calculate how aligned all execs are (0-1)"""
        if not recommendations:
            return 0.5
        
        # Scoring: go/proceed/accelerate = high, neutral/proceed_with_caution = medium, hold/no_go = low
        scores = {}
        
        score_map = {
            # Go/Proceed variants
            "go": 90, "proceed": 90, "accelerate": 90, "build": 90,
            # Medium
            "pivot": 60, "proceed_with_caution": 60, "go_with_changes": 60, "build_with_constraints": 60,
            "neutral": 50, "hold": 40,
            # No-Go variants
            "no_go": 10, "hold": 10, "no_build": 10, "don't_build": 10,
            # Unknown
            "unknown": 50
        }
        
        for role, rec in recommendations.items():
            scores[role] = score_map.get(rec.lower(), 50)
        
        # Calculate variance
        values = list(scores.values())
        avg = sum(values) / len(values)
        variance = sum((x - avg) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        # Convert std_dev to alignment (0-1)
        # Low std_dev = high alignment
        max_std_dev = 50
        alignment = max(0, 1 - (std_dev / max_std_dev))
        
        return alignment
    
    @staticmethod
    def identify_disagreements(exec_outputs: List[Dict]) -> List[Dict]:
        """Find key areas of disagreement"""
        disagreements = []
        
        # Extract key concerns from each exec
        concerns = {}
        
        for output in exec_outputs:
            try:
                data = json.loads(output['output'])
                role = output['role']
                
                if role == "cfo":
                    concerns[role] = {
                        "primary": data.get('key_metrics', {}),
                        "concern": data.get('cost_risks', [])
                    }
                elif role == "cpo":
                    concerns[role] = {
                        "demand": data.get('market_demand'),
                        "concern": data.get('product_roadmap_fit')
                    }
                elif role == "cto":
                    concerns[role] = {
                        "timeline": data.get('implementation_timeline'),
                        "concern": data.get('technical_risks', [])
                    }
                elif role == "cro":
                    concerns[role] = {
                        "impact": data.get('sales_impact'),
                        "concern": data.get('competitive_positioning_vs_rivals')
                    }
            except:
                pass
        
        return disagreements
    
    @staticmethod
    def build_consensus_analysis(exec_outputs: List[Dict]) -> Dict:
        """Build comprehensive consensus analysis"""
        recommendations = ConsensusEvaluator.extract_recommendations(exec_outputs)
        alignment = ConsensusEvaluator.calculate_alignment(recommendations)
        
        return {
            "overall_consensus_level": alignment,
            "areas_of_agreement": [],
            "areas_of_disagreement": ConsensusEvaluator.identify_disagreements(exec_outputs),
            "critical_contradictions": [],
            "outliers": [],
            "next_action": "synthesize" if alignment > 0.6 else "refine"
        }
