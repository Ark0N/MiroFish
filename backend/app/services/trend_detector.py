"""
Trend detector for ingested content.

Analyzes temporal patterns in ingested content to identify:
- Emerging topics (new keywords appearing with increasing frequency)
- Sentiment shifts in source material
- New entity appearances
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import Counter
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger('mirofish.trend_detector')


STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "can", "could", "i", "you", "he", "she",
    "it", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "its", "our", "their", "this", "that", "these", "those",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "and", "but", "or", "not", "no", "so", "if", "when", "what", "which",
    "who", "how", "all", "each", "every", "both", "few", "more", "most",
    "than", "too", "very", "just", "about", "also", "only", "then",
    "there", "here", "now", "up", "out", "over", "into", "through",
    "same", "other", "some", "such", "new", "said", "one", "two",
})


@dataclass
class TrendSignal:
    """A detected trend in the data."""
    topic: str
    trend_type: str  # "emerging", "growing", "declining", "sentiment_shift"
    strength: float  # 0-1, how strong the signal is
    frequency_current: int = 0
    frequency_previous: int = 0
    sentiment_current: float = 0.0
    sentiment_previous: float = 0.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "trend_type": self.trend_type,
            "strength": round(self.strength, 3),
            "frequency_current": self.frequency_current,
            "frequency_previous": self.frequency_previous,
            "sentiment_current": round(self.sentiment_current, 3),
            "sentiment_previous": round(self.sentiment_previous, 3),
            "description": self.description,
        }


class TrendDetector:
    """Detect trends in temporal content data."""

    POSITIVE_KW = {"good", "great", "support", "agree", "happy", "love",
                   "excellent", "hope", "progress", "positive", "benefit"}
    NEGATIVE_KW = {"bad", "terrible", "oppose", "disagree", "angry", "hate",
                   "awful", "crisis", "fail", "problem", "danger", "risk"}

    def detect_trends(
        self,
        current_texts: List[str],
        previous_texts: Optional[List[str]] = None,
        min_frequency: int = 2,
        top_k: int = 20,
    ) -> List[TrendSignal]:
        """Detect trends by comparing current vs previous content.

        Args:
            current_texts: Recent content to analyze
            previous_texts: Older content for comparison (optional)
            min_frequency: Minimum word frequency to consider
            top_k: Maximum trends to return

        Returns:
            List of TrendSignals sorted by strength
        """
        if not current_texts:
            return []

        current_words = self._extract_keywords(current_texts)
        current_sentiment = self._compute_sentiment(current_texts)

        signals = []

        if previous_texts:
            previous_words = self._extract_keywords(previous_texts)
            previous_sentiment = self._compute_sentiment(previous_texts)

            # Find emerging topics (new or growing keywords)
            for word, count in current_words.items():
                if count < min_frequency:
                    continue

                prev_count = previous_words.get(word, 0)

                if prev_count == 0 and count >= min_frequency:
                    # Completely new topic
                    strength = min(1.0, count / 10.0)
                    signals.append(TrendSignal(
                        topic=word,
                        trend_type="emerging",
                        strength=strength,
                        frequency_current=count,
                        frequency_previous=0,
                        description=f"New topic '{word}' appeared {count} times",
                    ))
                elif count > prev_count * 1.5 and count >= min_frequency:
                    # Growing topic (>50% increase)
                    growth_rate = (count - prev_count) / max(prev_count, 1)
                    strength = min(1.0, growth_rate / 3.0)
                    signals.append(TrendSignal(
                        topic=word,
                        trend_type="growing",
                        strength=strength,
                        frequency_current=count,
                        frequency_previous=prev_count,
                        description=f"'{word}' grew {growth_rate:.0%} ({prev_count} -> {count})",
                    ))

            # Find declining topics
            for word, prev_count in previous_words.items():
                if prev_count < min_frequency:
                    continue
                curr_count = current_words.get(word, 0)
                if curr_count < prev_count * 0.5:
                    decline_rate = (prev_count - curr_count) / prev_count
                    strength = min(1.0, decline_rate)
                    signals.append(TrendSignal(
                        topic=word,
                        trend_type="declining",
                        strength=strength,
                        frequency_current=curr_count,
                        frequency_previous=prev_count,
                        description=f"'{word}' declined {decline_rate:.0%} ({prev_count} -> {curr_count})",
                    ))

            # Detect sentiment shift
            if abs(current_sentiment - previous_sentiment) > 0.1:
                direction = "positive" if current_sentiment > previous_sentiment else "negative"
                shift = abs(current_sentiment - previous_sentiment)
                signals.append(TrendSignal(
                    topic=f"overall_sentiment_{direction}",
                    trend_type="sentiment_shift",
                    strength=min(1.0, shift * 2),
                    sentiment_current=current_sentiment,
                    sentiment_previous=previous_sentiment,
                    description=f"Sentiment shifted {direction} by {shift:.2f}",
                ))

        else:
            # No baseline — just report top keywords as emerging
            for word, count in current_words.most_common(top_k):
                if count < min_frequency:
                    continue
                strength = min(1.0, count / 10.0)
                signals.append(TrendSignal(
                    topic=word,
                    trend_type="emerging",
                    strength=strength,
                    frequency_current=count,
                    description=f"Topic '{word}' with {count} mentions",
                ))

        # Sort by strength and return top_k
        signals.sort(key=lambda s: s.strength, reverse=True)
        return signals[:top_k]

    def _extract_keywords(self, texts: List[str]) -> Counter:
        """Extract meaningful keywords from texts."""
        word_counts = Counter()
        for text in texts:
            words = re.findall(r'\b[a-z]{3,}\b', text.lower())
            for word in words:
                if word not in STOPWORDS:
                    word_counts[word] += 1
        return word_counts

    def _compute_sentiment(self, texts: List[str]) -> float:
        """Compute average sentiment of texts."""
        scores = []
        for text in texts:
            lower = text.lower()
            pos = sum(1 for w in self.POSITIVE_KW if w in lower)
            neg = sum(1 for w in self.NEGATIVE_KW if w in lower)
            total = pos + neg
            scores.append((pos - neg) / total if total > 0 else 0.0)
        return sum(scores) / len(scores) if scores else 0.0
