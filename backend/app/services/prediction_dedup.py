"""
Prediction deduplication service.

Detects and merges duplicate/near-duplicate predictions across reports
using word-level Jaccard similarity. Prevents the same event from
appearing multiple times in ensemble or comparison views.
"""

import re
from typing import Dict, List, Any, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_dedup')

STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "will", "would", "may", "might", "can",
    "could", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "and", "or", "but", "not", "that", "this", "it",
})


class PredictionDeduplicator:
    """Detect and merge duplicate predictions."""

    def __init__(self, similarity_threshold: float = 0.5):
        """
        Args:
            similarity_threshold: Jaccard similarity above which predictions
                                  are considered duplicates (0-1)
        """
        self.similarity_threshold = similarity_threshold

    def deduplicate(
        self,
        predictions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Remove duplicate predictions, merging their data.

        When duplicates are found, keeps the one with the highest probability
        and adds a 'merged_from' field listing the duplicates.

        Args:
            predictions: List of prediction dicts

        Returns:
            Deduplicated list of predictions
        """
        if len(predictions) <= 1:
            return predictions

        # Build clusters of similar predictions
        clusters = []
        used = set()

        for i, pred_a in enumerate(predictions):
            if i in used:
                continue

            cluster = [i]
            used.add(i)

            for j, pred_b in enumerate(predictions):
                if j in used or j <= i:
                    continue

                sim = self.compute_similarity(
                    pred_a.get("event", ""),
                    pred_b.get("event", "")
                )
                if sim >= self.similarity_threshold:
                    cluster.append(j)
                    used.add(j)

            clusters.append(cluster)

        # Merge each cluster into a single prediction
        result = []
        for cluster in clusters:
            if len(cluster) == 1:
                result.append(predictions[cluster[0]])
            else:
                merged = self._merge_cluster([predictions[i] for i in cluster])
                result.append(merged)

        return result

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Compute Jaccard similarity between two texts.

        Uses meaningful words (stopwords removed, lowercased).
        """
        words_a = self._extract_words(text_a)
        words_b = self._extract_words(text_b)

        if not words_a and not words_b:
            return 1.0  # Both empty = identical
        if not words_a or not words_b:
            return 0.0

        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        return intersection / union if union > 0 else 0.0

    def find_duplicates(
        self,
        predictions: List[Dict[str, Any]],
    ) -> List[Tuple[int, int, float]]:
        """Find all pairs of duplicate predictions.

        Returns:
            List of (idx_a, idx_b, similarity) tuples above threshold
        """
        duplicates = []
        for i in range(len(predictions)):
            for j in range(i + 1, len(predictions)):
                sim = self.compute_similarity(
                    predictions[i].get("event", ""),
                    predictions[j].get("event", "")
                )
                if sim >= self.similarity_threshold:
                    duplicates.append((i, j, round(sim, 4)))
        return duplicates

    def _merge_cluster(self, preds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge a cluster of similar predictions into one.

        Takes the prediction with highest probability as the base,
        averages probabilities, and records merge sources.
        """
        # Sort by probability descending
        preds.sort(key=lambda p: p.get("probability", 0), reverse=True)
        base = dict(preds[0])

        # Average probability across duplicates
        probs = [p.get("probability", 0.5) for p in preds]
        base["probability"] = round(sum(probs) / len(probs), 4)

        # Average agreement
        agreements = [p.get("agent_agreement", 0.5) for p in preds]
        base["agent_agreement"] = round(sum(agreements) / len(agreements), 4)

        # Merge evidence and risk factors
        all_evidence = set()
        all_risks = set()
        for p in preds:
            all_evidence.update(p.get("evidence", []))
            all_risks.update(p.get("risk_factors", []))
        base["evidence"] = list(all_evidence)
        base["risk_factors"] = list(all_risks)

        # Record merge info
        base["merged_from"] = [p.get("event", "") for p in preds[1:]]
        base["merge_count"] = len(preds)

        return base

    @staticmethod
    def _extract_words(text: str) -> set:
        """Extract meaningful words from text."""
        words = set(re.findall(r'\b[a-z]{3,}\b', text.lower()))
        return words - STOPWORDS
