"""
Council Evaluators

Implements the peer review and rating matrix logic for the LLM Council workflow.
Each LLM reviews other responses anonymously, creating a rating matrix used
by the Chairman to synthesize the final decision.
"""

import json
from typing import Dict, List, Optional
from council_state import PeerReview, RatingMatrix, LLMResponse, ComparisonResult


class CouncilEvaluator:
    """Evaluates LLM responses through peer review"""

    @staticmethod
    def build_peer_review_prompt(
        target_response: str,
        target_id: str,
        original_query: str,
        context: Dict
    ) -> str:
        """Create prompt for anonymous peer review of a response"""
        return f"""You are an expert evaluator reviewing an AI response to a product decision question.
Your review should be objective and constructive.

ORIGINAL QUESTION:
{original_query}

COMPANY CONTEXT:
{json.dumps(context, indent=2)}

RESPONSE TO REVIEW (Response {target_id}):
{target_response}

Evaluate this response on the following criteria:
1. Accuracy and correctness of analysis
2. Depth of reasoning and insight
3. Practical actionability of recommendations
4. Consideration of risks and trade-offs
5. Clarity and structure of response

Provide your evaluation as JSON:
{{
    "score": <1-10, where 10 is excellent>,
    "critique": "<2-3 sentences explaining your score>",
    "strengths": ["<strength 1>", "<strength 2>"],
    "weaknesses": ["<weakness 1>", "<weakness 2>"]
}}

Be fair but rigorous. Do not inflate scores."""

    @staticmethod
    def build_chairman_prompt(
        original_query: str,
        context: Dict,
        responses: List[LLMResponse],
        rating_matrix: RatingMatrix
    ) -> str:
        """Create prompt for chairman synthesis based on peer ratings"""

        # Build response summaries with scores
        response_summaries = []
        for resp in responses:
            avg_score = rating_matrix['aggregated_scores'].get(resp['provider_id'], 0)
            response_summaries.append(f"""
--- Response {resp['provider_id']} (Average Score: {avg_score:.1f}/10) ---
{resp['response'][:2000]}...
""")

        responses_text = "\n".join(response_summaries)

        # Build rating matrix summary
        matrix_summary = f"""
Highest rated: {rating_matrix['highest_rated']} ({rating_matrix['aggregated_scores'].get(rating_matrix['highest_rated'], 0):.1f}/10)
Lowest rated: {rating_matrix['lowest_rated']} ({rating_matrix['aggregated_scores'].get(rating_matrix['lowest_rated'], 0):.1f}/10)
Score variance: {rating_matrix['score_variance']:.2f} (lower = more agreement)
"""

        return f"""You are the Chairman of an LLM Council, responsible for synthesizing multiple AI perspectives into a final product decision.

ORIGINAL DECISION QUESTION:
{original_query}

COMPANY CONTEXT:
{json.dumps(context, indent=2)}

COUNCIL RESPONSES (with peer-review scores):
{responses_text}

RATING MATRIX SUMMARY:
{matrix_summary}

Your job as Chairman:
1. Give more weight to higher-rated responses, but consider all perspectives
2. Identify the strongest arguments from each response
3. Resolve conflicts by reasoning through trade-offs
4. Synthesize into a clear, actionable recommendation

Output your synthesis as JSON:
{{
    "recommendation": "GO" | "PIVOT" | "HOLD",
    "confidence_level": <0-100>,
    "executive_summary": "<2-3 sentences for decision makers>",
    "weighted_reasoning": "<explain how ratings influenced your synthesis>",
    "key_insights_from_council": ["<insight 1>", "<insight 2>", "<insight 3>"],
    "consensus_points": ["<point 1>", "<point 2>"],
    "disagreement_areas": ["<area 1>", "<area 2>"],
    "recommended_next_steps": ["<step 1>", "<step 2>", "<step 3>"],
    "risk_factors": ["<risk 1>", "<risk 2>"]
}}"""

    @staticmethod
    def parse_peer_review(response_text: str) -> Optional[Dict]:
        """Parse peer review JSON from LLM response"""
        try:
            # Try to extract JSON from response
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text

            data = json.loads(json_str.strip())

            return {
                "score": int(data.get("score", 5)),
                "critique": data.get("critique", ""),
                "strengths": data.get("strengths", []),
                "weaknesses": data.get("weaknesses", [])
            }
        except:
            return None

    @staticmethod
    def aggregate_ratings(peer_reviews: List[PeerReview]) -> RatingMatrix:
        """Compute rating matrix from all peer reviews"""
        # Group reviews by target
        scores_by_target: Dict[str, List[int]] = {}

        for review in peer_reviews:
            target = review['target_id']
            if target not in scores_by_target:
                scores_by_target[target] = []
            scores_by_target[target].append(review['score'])

        # Calculate average scores
        aggregated_scores: Dict[str, float] = {}
        for target, scores in scores_by_target.items():
            if scores:
                aggregated_scores[target] = sum(scores) / len(scores)
            else:
                aggregated_scores[target] = 0.0

        # Find highest and lowest
        if aggregated_scores:
            highest_rated = max(aggregated_scores, key=aggregated_scores.get)
            lowest_rated = min(aggregated_scores, key=aggregated_scores.get)

            # Calculate variance (agreement measure)
            all_scores = [r['score'] for r in peer_reviews]
            if all_scores:
                avg = sum(all_scores) / len(all_scores)
                variance = sum((s - avg) ** 2 for s in all_scores) / len(all_scores)
            else:
                variance = 0.0
        else:
            highest_rated = ""
            lowest_rated = ""
            variance = 0.0

        return RatingMatrix(
            reviews=peer_reviews,
            aggregated_scores=aggregated_scores,
            score_variance=variance,
            highest_rated=highest_rated,
            lowest_rated=lowest_rated
        )

    @staticmethod
    def get_council_alignment(rating_matrix: RatingMatrix) -> float:
        """Calculate how aligned the council is (0-1) based on score variance"""
        # Low variance = high alignment
        # Assuming max realistic variance is around 20 (very divided)
        max_variance = 20.0
        alignment = max(0, 1 - (rating_matrix['score_variance'] / max_variance))
        return alignment

    @staticmethod
    def compare_decisions(
        consensus_result: Dict,
        council_result: Dict
    ) -> ComparisonResult:
        """Compare results from Consensus and Council methods"""

        # Extract recommendations
        consensus_rec = consensus_result.get('recommendation_type', 'HOLD').upper()
        council_rec = council_result.get('recommendation_type', 'HOLD').upper()

        # Extract confidence levels
        consensus_conf = float(consensus_result.get('confidence_level', 50))
        council_conf = float(council_result.get('confidence_level', 50))

        # Extract reasoning
        try:
            consensus_data = json.loads(consensus_result.get('final_decision', '{}'))
            consensus_reasoning = consensus_data.get('executive_summary', '')
        except:
            consensus_reasoning = str(consensus_result.get('final_decision', ''))[:200]

        council_reasoning = council_result.get('weighted_reasoning', '')

        # Identify key differences
        differences = []

        if consensus_rec != council_rec:
            differences.append(f"Different recommendations: Consensus={consensus_rec}, Council={council_rec}")

        if abs(consensus_conf - council_conf) > 20:
            differences.append(f"Significant confidence gap: {abs(consensus_conf - council_conf):.0f}%")

        # Generate combined insight
        if consensus_rec == council_rec:
            combined = f"Both methods agree on {consensus_rec} with average confidence {(consensus_conf + council_conf) / 2:.0f}%"
        else:
            combined = f"Methods disagree: Consensus recommends {consensus_rec} ({consensus_conf:.0f}%) while Council recommends {council_rec} ({council_conf:.0f}%). Consider additional analysis."

        return ComparisonResult(
            consensus_recommendation=consensus_rec,
            council_recommendation=council_rec,
            recommendations_match=(consensus_rec == council_rec),
            consensus_confidence=consensus_conf,
            council_confidence=council_conf,
            confidence_difference=abs(consensus_conf - council_conf),
            consensus_reasoning=consensus_reasoning,
            council_reasoning=council_reasoning,
            key_differences=differences,
            combined_insight=combined
        )

    @staticmethod
    def analyze_divergence(responses: List[LLMResponse]) -> Dict:
        """Analyze divergence between LLM responses to highlight agreements/disagreements"""
        recommendations = {}
        confidence_levels = {}
        summaries = {}

        for resp in responses:
            provider_id = resp['provider_id']
            if resp['parsed_data']:
                rec = resp['parsed_data'].get('recommendation', '').upper()
                conf = resp['parsed_data'].get('confidence_level', 0)
                summary = resp['parsed_data'].get('executive_summary', '')
                recommendations[provider_id] = rec
                confidence_levels[provider_id] = conf
                summaries[provider_id] = summary
            else:
                recommendations[provider_id] = 'UNKNOWN'
                confidence_levels[provider_id] = 0
                summaries[provider_id] = ''

        # Calculate agreement
        rec_values = [r for r in recommendations.values() if r != 'UNKNOWN']
        if rec_values:
            from collections import Counter
            rec_counts = Counter(rec_values)
            majority_recommendation = rec_counts.most_common(1)[0][0]
            all_agree = len(set(rec_values)) == 1
        else:
            majority_recommendation = None
            all_agree = False

        # Identify divergent providers
        divergent_providers = [
            p for p, r in recommendations.items()
            if r != 'UNKNOWN' and r != majority_recommendation
        ] if majority_recommendation else []

        agreeing_providers = [
            p for p, r in recommendations.items()
            if r == majority_recommendation
        ] if majority_recommendation else []

        # Calculate confidence spread
        conf_values = [c for c in confidence_levels.values() if c > 0]
        confidence_spread = max(conf_values) - min(conf_values) if len(conf_values) >= 2 else 0

        return {
            "recommendations": recommendations,
            "confidence_levels": confidence_levels,
            "summaries": summaries,
            "recommendation_agreement": all_agree,
            "majority_recommendation": majority_recommendation,
            "divergent_providers": divergent_providers,
            "agreeing_providers": agreeing_providers,
            "confidence_spread": confidence_spread,
            "total_providers": len(responses),
            "agreeing_count": len(agreeing_providers),
            "diverging_count": len(divergent_providers)
        }

    @staticmethod
    def build_divergence_prompt(query: str, context: Dict) -> str:
        """Create the prompt sent to all LLMs during divergence stage"""
        return f"""You are an AI advisor analyzing a product decision. Provide a thorough, well-reasoned analysis.

DECISION QUESTION:
{query}

COMPANY CONTEXT:
{json.dumps(context, indent=2)}

Analyze this decision from multiple angles:
1. Financial implications (costs, ROI, budget)
2. Product-market fit and customer demand
3. Technical feasibility and implementation effort
4. Revenue potential and competitive positioning
5. Risks and mitigation strategies

Provide your analysis as JSON:
{{
    "recommendation": "GO" | "PIVOT" | "HOLD",
    "confidence_level": <0-100>,
    "executive_summary": "<2-3 sentence summary>",
    "financial_analysis": "<key financial considerations>",
    "product_analysis": "<product-market fit assessment>",
    "technical_analysis": "<feasibility and effort>",
    "revenue_analysis": "<revenue potential>",
    "key_risks": ["<risk 1>", "<risk 2>"],
    "recommended_next_steps": ["<step 1>", "<step 2>"]
}}"""
