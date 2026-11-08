"""LLM Reasoning Service for real-time conversational agent decision making."""

import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger("tara.conversation.llm")


class LLMReasoningService:
    """
    Connects to high-speed LLM inference engines (Groq Qwen/Llama) with connection
    pooling, bounded retries, and structured JSON parsing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 8.0,
        mock_mode: bool = False,
    ):
        self.api_key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.groq_model
        self.timeout = timeout
        self.mock_mode = mock_mode or not bool(self.api_key)
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or initialize pooled HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=60.0),
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate_reasoning_step(
        self,
        messages: List[Dict[str, str]],
        fallback_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute reasoning turn with structured JSON response.

        Args:
            messages: List of chat messages (system, history, user).
            fallback_context: Optional context for offline fallback generation.

        Returns:
            Parsed JSON dict with intent, tool_calls, state_transition, and spoken_response.
        """
        if self.mock_mode:
            logger.info("LLMReasoningService executing in mock mode")
            return self._generate_mock_reasoning(messages, fallback_context)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 250,
            "response_format": {"type": "json_object"},
        }

        client = await self._get_client()

        for attempt in range(settings.llm_max_retries + 1):
            try:
                resp = await client.post(self.base_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = self._clean_and_parse_json(content)
                    if parsed:
                        return parsed
                logger.warning("Groq LLM returned status %d on attempt %d: %s", resp.status_code, attempt, resp.text[:200])
            except Exception as exc:
                logger.warning("Groq LLM request error on attempt %d: %s", attempt, exc)

        logger.error("All LLM reasoning attempts failed. Falling back to rule-based conversation engine.")
        return self._generate_mock_reasoning(messages, fallback_context)

    def _clean_and_parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Safely parse JSON response from LLM, stripping markdown code fences."""
        try:
            cleaned = raw_text.strip()
            # Remove ```json ... ``` wrapper if present
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
            return json.loads(cleaned)
        except Exception as exc:
            logger.warning("Failed to parse JSON from LLM output: %s", exc)
            return None

    def _generate_mock_reasoning(
        self,
        messages: List[Dict[str, str]],
        fallback_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fast rule-based offline fallback when LLM is unavailable."""
        ctx = fallback_context or {}
        lang = ctx.get("language", "te-IN").lower()
        last_msg = messages[-1]["content"].lower() if messages else ""

        # Check rejection (support Telugu script, Devanagari, English, and Roman transliterations)
        rejection_signals = [
            "vaddu", "వద్దు", "లేదు", "ledu", "oddhu", "వద్దు", "no", "nahi", "नहीं",
            "not interested", "interest ledu", "ఆసక్తి లేదు", "వద్దు", "stop",
        ]
        if any(w in last_msg for w in rejection_signals):
            if "te" in lang:
                spoken = "సరేనండి, మీ సమయానికి ధన్యవాదాలు. శుభదినం!"
            elif "hi" in lang:
                spoken = "ठीक है, आपके समय के लिए धन्यवाद। आपका दिन शुभ हो!"
            else:
                spoken = "Understood. Thank you for your time. Have a good day!"
            return {
                "thought": "Customer declined the offer",
                "intent": "not_interested",
                "confidence": 0.98,
                "state_transition": "COMPLETED",
                "tool_calls": [{"tool_name": "end_conversation", "arguments": {"reason": "declined"}}],
                "spoken_response": spoken,
            }

        # Check callback
        callback_signals = [
            "later", "tarvatha", "తర్వాత", "baad me", "बाद में", "busy", "బిజీ",
            "repu", "రేపు", "call later", "తిరిగి కాల్", "మళ్లీ", "कल",
        ]
        if any(w in last_msg for w in callback_signals):
            if "te" in lang:
                spoken = "సరేనండి, మీకు అనుకూలమైన సమయంలో తిరిగి కాల్ చేస్తాము. ధన్యవాదాలు!"
            elif "hi" in lang:
                spoken = "ठीक है, हम आपको सुविधाजनक समय पर संपर्क करेंगे। धन्यवाद!"
            else:
                spoken = "Sure, we will arrange a callback at your convenience. Thank you!"
            return {
                "thought": "Customer requested callback",
                "intent": "callback_requested",
                "confidence": 0.95,
                "state_transition": "FOLLOW_UP",
                "tool_calls": [{"tool_name": "schedule_callback", "arguments": {"callback_time": "Later"}}],
                "spoken_response": spoken,
            }

        # Check DND
        if any(w in last_msg for w in ["dnd", "stop calling", "don't call"]):
            return {
                "thought": "Customer requested DND",
                "intent": "do_not_call",
                "confidence": 1.0,
                "state_transition": "COMPLETED",
                "tool_calls": [{"tool_name": "mark_do_not_call", "arguments": {"reason": "Customer request"}}],
                "spoken_response": "క్షమించండి, మీ నంబర్ ని డు-నాట్-కాల్ లిస్ట్ లో చేర్చాము. సెలవు.",
            }

        # Default positive progression
        rate = ctx.get("interest_rate", "10.49%")
        amount = ctx.get("loan_amount", "5,00,000")
        if "te" in lang:
            spoken = f"ధన్యవాదాలు అండీ! మీ అకౌంట్ ఆధారంగా మీకు ₹{amount} వరకు తక్షణ లోన్ లభిస్తుంది, వడ్డీ కేవలం {rate} మాత్రమే. వివరాలు తెలుసుకోవడానికి ఆసక్తి ఉందా?"
        elif "hi" in lang:
            spoken = f"धन्यवाद! आपके खाते पर ₹{amount} तक का प्री-अप्रूव्ड लोन मात्र {rate} ब्याज दर पर उपलब्ध है। क्या आप विवरण जानना चाहेंगे?"
        else:
            spoken = f"Thank you! Based on your account history, you are eligible for up to ₹{amount} starting at {rate} interest. Would you like to hear more?"

        return {
            "thought": "Customer expressed interest, pitch core details",
            "intent": "interested",
            "confidence": 0.9,
            "state_transition": "INFORMATION",
            "tool_calls": [],
            "spoken_response": spoken,
        }

