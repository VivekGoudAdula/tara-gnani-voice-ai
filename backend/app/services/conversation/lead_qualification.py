"""Configurable Lead Qualification Engine for banking acquisition conversations."""

import logging
import re
from typing import Any, Dict, Optional
from app.services.conversation.models import QualificationState

logger = logging.getLogger("tara.conversation.qualification")


class LeadQualificationEngine:
    """
    Evaluates and tracks customer need, budget, timeline, and purchase authority
    throughout telephone conversations.
    """

    @staticmethod
    def extract_and_update(
        current_state: QualificationState,
        customer_speech: str,
        llm_qualification_update: Optional[Dict[str, Any]] = None,
    ) -> QualificationState:
        """
        Update qualification criteria based on customer speech and LLM extraction.

        Args:
            current_state: Existing qualification state.
            customer_speech: Raw transcript spoken by customer.
            llm_qualification_update: Optional structured fields extracted by LLM.

        Returns:
            Updated QualificationState model.
        """
        updated = current_state.model_copy(deep=True)
        text_lower = customer_speech.lower()

        # 1. Update from LLM extraction if provided
        if llm_qualification_update:
            if llm_qualification_update.get("need"):
                updated.need_identified = True
                updated.stated_need = llm_qualification_update["need"]
            if llm_qualification_update.get("budget_or_amount"):
                updated.budget_or_amount = str(llm_qualification_update["budget_or_amount"])
            if llm_qualification_update.get("timeline"):
                updated.timeline = llm_qualification_update["timeline"]

        # 2. Rule-based heuristics for numbers/amounts (e.g. "2 lakhs", "rendu lakshalu", "50000")
        if not updated.budget_or_amount:
            amount_match = re.search(r"(\d+[\d,]*\s*(?:lakh|laksh|k|thousand|rupees|rs)?)", text_lower)
            if amount_match and len(amount_match.group(1).strip()) > 1:
                updated.budget_or_amount = amount_match.group(1).strip()

        # 3. Purpose / Need signals (apply heuristics only if not already extracted)
        if not updated.stated_need:
            need_keywords = {
                "marriage": "wedding / marriage",
                "pelli": "wedding / marriage",
                "medical": "medical emergency",
                "hospital": "medical emergency",
                "aroogyam": "medical emergency",
                "house": "home improvement",
                "renovation": "home improvement",
                "illu": "home improvement",
                "business": "business expansion",
                "education": "higher education",
                "chaduvu": "higher education",
            }
            for kw, need_desc in need_keywords.items():
                if kw in text_lower:
                    updated.need_identified = True
                    updated.stated_need = need_desc
                    break

        # 4. Timeline signals
        if any(w in text_lower for w in ["now", "ventane", "today", "urgent", "e roju", "immediate"]):
            updated.timeline = "Immediate (< 48 hours)"
        elif any(w in text_lower for w in ["next week", "tarvatha", "vache vaaram", "month"]):
            updated.timeline = "Next 30 days"

        # 5. Evaluate qualification progression
        criteria_met = sum([
            1 if updated.need_identified else 0,
            1 if updated.budget_or_amount else 0,
            1 if updated.timeline else 0,
        ])

        if criteria_met >= 2:
            updated.status = "qualified"
            updated.score_adjustment = 0.15
        elif criteria_met == 1:
            updated.status = "in_progress"
            updated.score_adjustment = 0.05
        else:
            updated.status = "unqualified"

        return updated

