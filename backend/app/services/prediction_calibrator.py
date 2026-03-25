"""
Prediction confidence calibrator.

Adjusts prediction confidence levels based on agent consensus patterns,
consensus strength metrics, and contrarian agent impact.
"""

import json
import os
from typing import Dict, List, Optional, Any

from ..utils.logger import get_logger

logger = get_logger('mirofish.prediction_calibrator')


class PredictionCalibrator:
    """Calibrate prediction confidence using consensus and contrarian signals.

    Confidence adjustments:
    - High agreement + high consensus strength → boost confidence
    - Low agreement or low stability → reduce confidence
    - Contrarian agents shifted opinion → significant downgrade (weak consensus)
    - High diversity in dominant faction → boost (signal is robust across types)
    """

    # Weight factors for calibration
    AGREEMENT_WEIGHT = 0.35
    STRENGTH_WEIGHT = 0.35
    CONTRARIAN_WEIGHT = 0.30

    def calibrate(
        self,
        predictions: List[Dict[str, Any]],
        consensus_data: Optional[Dict[str, Any]] = None,
        simulation_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Calibrate prediction confidence levels.

        Args:
            predictions: List of prediction dicts (from PredictionSet.to_dict()["predictions"])
            consensus_data: ConsensusResult.to_dict() if available
            simulation_dir: Path to simulation dir for contrarian impact analysis

        Returns:
            List of calibrated prediction dicts with adjusted probability and
            a 'calibration' sub-dict explaining adjustments.
        """
        if not predictions:
            return predictions

        agreement_score = 0.5
        strength_data = None
        contrarian_shift = 0.0

        if consensus_data:
            agreement_score = consensus_data.get("agreement_score", 0.5)
            strength_data = consensus_data.get("consensus_strength")

        if simulation_dir:
            contrarian_shift = self._measure_contrarian_impact(simulation_dir)

        calibrated = []
        for pred in predictions:
            calibrated.append(
                self._calibrate_single(pred, agreement_score, strength_data, contrarian_shift)
            )

        return calibrated

    def _calibrate_single(
        self,
        prediction: Dict[str, Any],
        agreement_score: float,
        strength_data: Optional[Dict[str, Any]],
        contrarian_shift: float,
    ) -> Dict[str, Any]:
        """Calibrate a single prediction."""
        original_prob = prediction.get("probability", 0.5)
        original_agreement = prediction.get("agent_agreement", 0.5)

        # --- Agreement factor ---
        # High agreement → boost, low → penalize
        agreement_factor = self._agreement_factor(agreement_score, original_agreement)

        # --- Strength factor ---
        strength_factor = self._strength_factor(strength_data)

        # --- Contrarian factor ---
        # If contrarians shifted opinion, penalize confidence
        contrarian_factor = self._contrarian_factor(contrarian_shift)

        # Composite adjustment: weighted average of factors
        adjustment = (
            agreement_factor * self.AGREEMENT_WEIGHT +
            strength_factor * self.STRENGTH_WEIGHT +
            contrarian_factor * self.CONTRARIAN_WEIGHT
        )

        # Apply adjustment to probability (bounded 0.05 - 0.99)
        calibrated_prob = max(0.05, min(0.99, original_prob * adjustment))

        # Update confidence interval proportionally
        ci = prediction.get("confidence_interval", [0.0, 1.0])
        ci_center = calibrated_prob
        ci_half_width = (ci[1] - ci[0]) / 2 if len(ci) == 2 else 0.2
        # Widen interval if confidence dropped
        if adjustment < 1.0:
            ci_half_width *= (2.0 - adjustment)  # widen when less confident
        calibrated_ci = [
            max(0.0, round(ci_center - ci_half_width, 3)),
            min(1.0, round(ci_center + ci_half_width, 3))
        ]

        result = dict(prediction)
        result["probability"] = round(calibrated_prob, 3)
        result["confidence_interval"] = calibrated_ci
        result["calibration"] = {
            "original_probability": original_prob,
            "agreement_factor": round(agreement_factor, 3),
            "strength_factor": round(strength_factor, 3),
            "contrarian_factor": round(contrarian_factor, 3),
            "adjustment": round(adjustment, 3),
        }

        return result

    def _agreement_factor(self, consensus_agreement: float, prediction_agreement: float) -> float:
        """Factor based on overall and per-prediction agent agreement.

        Returns multiplier > 1.0 for high agreement, < 1.0 for low.
        """
        # Average of consensus-level and prediction-level agreement
        avg_agreement = (consensus_agreement + prediction_agreement) / 2

        # Map 0-1 agreement to 0.6-1.3 multiplier
        # 0.0 agreement → 0.6x, 0.5 → 1.0x, 1.0 → 1.3x
        return 0.6 + avg_agreement * 0.7

    def _strength_factor(self, strength_data: Optional[Dict[str, Any]]) -> float:
        """Factor based on consensus strength metrics.

        Returns multiplier reflecting quality of consensus signal.
        """
        if not strength_data:
            return 1.0  # neutral if no data

        diversity = strength_data.get("diversity_score", 0.5)
        conviction = strength_data.get("conviction_score", 0.5)
        stability = strength_data.get("stability_score", 0.5)

        # High diversity + conviction + stability → strong signal → boost
        # Map weighted average (0-1) to (0.7-1.3) multiplier
        weighted = diversity * 0.3 + conviction * 0.3 + stability * 0.4
        return 0.7 + weighted * 0.6

    def _contrarian_factor(self, contrarian_shift: float) -> float:
        """Factor based on contrarian impact.

        contrarian_shift: 0.0 = no shift, 1.0 = complete opinion reversal
        Returns multiplier < 1.0 if contrarians had impact.
        """
        # No shift → 1.2x boost (consensus survived challenge)
        # Full shift → 0.5x penalty (consensus was fragile)
        return 1.2 - contrarian_shift * 0.7

    def _measure_contrarian_impact(self, simulation_dir: str) -> float:
        """Measure how much contrarian agents shifted group opinion.

        Reads action logs and compares sentiment of posts replying to
        contrarian agents vs. general sentiment. A large positive delta
        (people changed opinion after contrarian posts) indicates weak consensus.

        Returns 0.0-1.0 shift score.
        """
        contrarian_names = set()
        all_sentiments = []
        reply_sentiments = []  # sentiments of posts following contrarian posts

        positive_kw = {"good", "great", "support", "agree", "happy", "love", "excellent",
                       "hope", "progress", "positive", "improvement", "benefit"}
        negative_kw = {"bad", "terrible", "oppose", "disagree", "angry", "hate", "awful",
                       "crisis", "fail", "problem", "scandal", "corrupt", "outrage", "danger"}

        def score_post(content: str) -> float:
            lower = content.lower()
            pos = sum(1 for w in positive_kw if w in lower)
            neg = sum(1 for w in negative_kw if w in lower)
            total = pos + neg
            return (pos - neg) / total if total > 0 else 0.0

        for platform in ["twitter", "reddit"]:
            actions_file = os.path.join(simulation_dir, platform, "actions.jsonl")
            if not os.path.exists(actions_file):
                continue

            posts_by_round = {}  # round -> list of (agent, content, is_contrarian)
            try:
                with open(actions_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            action = json.loads(line)
                            agent = action.get("agent_name", action.get("user_name", ""))
                            atype = action.get("action_type", "")
                            content = action.get("content", "")
                            round_num = action.get("round", 0)

                            # Identify contrarian agents by username pattern
                            if agent.startswith("contrarian_"):
                                contrarian_names.add(agent)

                            if atype in ("CREATE_POST", "CREATE_COMMENT", "QUOTE_POST") and content:
                                s = score_post(content)
                                all_sentiments.append(s)

                                if round_num not in posts_by_round:
                                    posts_by_round[round_num] = []
                                posts_by_round[round_num].append({
                                    "agent": agent,
                                    "sentiment": s,
                                    "is_contrarian": agent.startswith("contrarian_"),
                                })
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

            # For each round with contrarian posts, check if the NEXT round's
            # non-contrarian sentiment shifted toward the contrarian position
            sorted_rounds = sorted(posts_by_round.keys())
            for i, round_num in enumerate(sorted_rounds):
                has_contrarian = any(p["is_contrarian"] for p in posts_by_round[round_num])
                if has_contrarian and i + 1 < len(sorted_rounds):
                    next_round = sorted_rounds[i + 1]
                    next_non_contrarian = [
                        p["sentiment"] for p in posts_by_round[next_round]
                        if not p["is_contrarian"]
                    ]
                    if next_non_contrarian:
                        reply_sentiments.extend(next_non_contrarian)

        if not all_sentiments or not contrarian_names:
            return 0.0

        # Compare general sentiment vs. post-contrarian sentiment
        avg_general = sum(all_sentiments) / len(all_sentiments) if all_sentiments else 0.0
        avg_reply = sum(reply_sentiments) / len(reply_sentiments) if reply_sentiments else avg_general

        # Shift = how much sentiment changed toward contrarian position
        # Contrarians are by design opposing, so shift is measured as
        # change in absolute direction away from the general consensus
        shift = abs(avg_general - avg_reply)
        # Normalize to 0-1 (max realistic shift is ~1.0 on our -1 to 1 scale)
        return min(1.0, shift)
