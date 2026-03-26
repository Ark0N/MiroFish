"""
Prediction contradiction detector.

Identifies pairs of predictions that are logically contradictory
(e.g., "prices rise" and "deflation occurs"). Also estimates impact
magnitude for each prediction using engagement and language markers.
"""

import re
from typing import Dict, List, Any, Tuple

from ..utils.logger import get_logger

logger = get_logger('mirofish.contradiction')

# Antonym pairs that suggest contradiction
ANTONYM_PAIRS = [
    ({"rise", "increase", "grow", "gain", "surge", "boom", "expand"},
     {"fall", "decrease", "shrink", "loss", "decline", "crash", "contract"}),
    ({"positive", "optimistic", "bullish", "support"},
     {"negative", "pessimistic", "bearish", "oppose"}),
    ({"stability", "peace", "calm", "recovery"},
     {"instability", "conflict", "crisis", "recession"}),
    ({"inflation", "expensive", "costly"},
     {"deflation", "cheap", "affordable"}),
    ({"strengthen", "improve", "progress"},
     {"weaken", "deteriorate", "regress"}),
]


class ContradictionDetector:
    """Detect logical contradictions between predictions."""

    def detect_contradictions(
        self,
        predictions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Find contradictory prediction pairs.

        Args:
            predictions: List of prediction dicts with 'event' field

        Returns:
            List of contradiction dicts with indices, events, severity, and evidence
        """
        contradictions = []

        for i in range(len(predictions)):
            for j in range(i + 1, len(predictions)):
                event_a = predictions[i].get("event", "")
                event_b = predictions[j].get("event", "")

                score, evidence = self._check_contradiction(event_a, event_b)

                if score > 0:
                    severity = "high" if score >= 2 else "medium" if score >= 1 else "low"
                    prob_a = predictions[i].get("probability", 0.5)
                    prob_b = predictions[j].get("probability", 0.5)

                    # Suggest which has stronger evidence
                    stronger = i if prob_a > prob_b else j
                    weaker = j if stronger == i else i

                    contradictions.append({
                        "prediction_a_idx": i,
                        "prediction_b_idx": j,
                        "event_a": event_a,
                        "event_b": event_b,
                        "severity": severity,
                        "contradiction_score": score,
                        "evidence": evidence,
                        "stronger_prediction": stronger,
                        "weaker_prediction": weaker,
                        "recommendation": (
                            f"Prediction {weaker} ('{predictions[weaker].get('event', '')[:50]}') "
                            f"has weaker evidence ({predictions[weaker].get('probability', 0.5)*100:.0f}% vs "
                            f"{predictions[stronger].get('probability', 0.5)*100:.0f}%). Consider revising."
                        ),
                    })

        contradictions.sort(key=lambda c: c["contradiction_score"], reverse=True)
        return contradictions

    def _check_contradiction(self, event_a: str, event_b: str) -> Tuple[int, List[str]]:
        """Check if two events contradict each other.

        Returns (score, evidence_list). Score 0 = no contradiction.
        """
        words_a = set(re.findall(r'\b[a-z]+\b', event_a.lower()))
        words_b = set(re.findall(r'\b[a-z]+\b', event_b.lower()))

        score = 0
        evidence = []

        for positive_set, negative_set in ANTONYM_PAIRS:
            a_has_positive = bool(words_a & positive_set)
            a_has_negative = bool(words_a & negative_set)
            b_has_positive = bool(words_b & positive_set)
            b_has_negative = bool(words_b & negative_set)

            if (a_has_positive and b_has_negative) or (a_has_negative and b_has_positive):
                matching_a = (words_a & positive_set) | (words_a & negative_set)
                matching_b = (words_b & positive_set) | (words_b & negative_set)
                evidence.append(
                    f"Antonym conflict: {matching_a} vs {matching_b}"
                )
                score += 1

        # Check for explicit negation patterns
        if any(neg in event_a.lower() for neg in ["not ", "no ", "won't ", "unlikely"]):
            if any(neg in event_b.lower() for neg in ["will ", "likely ", "expected"]):
                # Check topic overlap
                shared = words_a & words_b
                if len(shared) >= 3:
                    evidence.append(f"Negation conflict on shared topic: {shared}")
                    score += 1

        return score, evidence

    def estimate_impact(
        self,
        prediction: Dict[str, Any],
        agent_posts: Dict[str, List[str]] = None,
    ) -> Dict[str, Any]:
        """Estimate impact magnitude for a prediction (1-10 scale).

        Uses:
        - Emotional language intensity in agent posts
        - Number of agents discussing the topic
        - Prediction probability (higher = more impactful if true)
        """
        event = prediction.get("event", "")
        probability = prediction.get("probability", 0.5)

        # Base impact from probability
        prob_impact = probability * 4  # 0-4 range

        # Emotional language intensity
        emotional_words = {
            "crisis", "catastrophe", "disaster", "unprecedented", "urgent",
            "critical", "emergency", "devastating", "massive", "historic",
            "breakthrough", "revolution", "transformation", "collapse", "surge",
        }
        event_words = set(event.lower().split())
        emotion_count = len(event_words & emotional_words)
        emotion_impact = min(3, emotion_count)  # 0-3 range

        # Agent engagement (if posts available)
        engagement_impact = 0
        if agent_posts:
            topic_words = set(re.findall(r'\b[a-z]{4,}\b', event.lower()))
            discussing = sum(
                1 for posts in agent_posts.values()
                for post in posts
                if topic_words & set(post.lower().split())
            )
            engagement_impact = min(3, discussing / max(1, len(agent_posts)) * 3)  # 0-3 range

        total = prob_impact + emotion_impact + engagement_impact
        score = max(1, min(10, round(total)))

        return {
            "impact_score": score,
            "components": {
                "probability_impact": round(prob_impact, 2),
                "emotional_intensity": round(emotion_impact, 2),
                "engagement_impact": round(engagement_impact, 2),
            },
            "level": "critical" if score >= 8 else "high" if score >= 6 else "medium" if score >= 4 else "low",
        }
