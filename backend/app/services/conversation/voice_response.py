"""Temporary voice dialogue response engine for multi-turn acquisition conversations."""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("tara.conversation.voice_response")


class DialogueTurn(BaseModel):
    """Single turn representation in a conversation session."""

    speaker: str  # "agent" or "customer"
    text: str
    timestamp: Optional[float] = None


class TurnResponse(BaseModel):
    """Response returned by the voice response engine for a turn."""

    response_text: str
    turn_index: int
    intent: str = "general"
    interest_level: str = "unknown"  # "interested", "not_interested", "callback", "unknown"
    is_call_complete: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VoiceResponseEngine:
    """
    Multi-turn conversation engine for outbound financial acquisition calls.

    Manages conversation lifecycle from greeting, product pitch, inquiry handling,
    qualification, to consent and polite wrap-up in Telugu, Hindi, and English.
    """

    def __init__(
        self,
        customer_name: str = "Customer",
        bank_name: str = "Gnani Bank",
        product_name: str = "Personal Loan",
        loan_amount: str = "5,00,000",
        interest_rate: str = "10.49%",
        language: str = "te-IN",  # "te-IN", "hi-IN", or "en-IN"
    ):
        self.customer_name = customer_name or "Customer"
        self.bank_name = bank_name or "Gnani Bank"
        self.product_name = product_name or "Personal Loan"
        self.loan_amount = loan_amount or "5,00,000"
        self.interest_rate = interest_rate or "10.49%"
        self.language = (language or "te-IN").lower()

        self.turn_count = 0
        self.history: List[DialogueTurn] = []
        self.detected_interest = "unknown"
        self.is_completed = False

    def generate_initial_greeting(self) -> str:
        """
        Generate the introductory greeting and pitch for turn 0.

        Returns:
            Concise, welcoming greeting in the recipient's language.
        """
        self.turn_count = 1
        if "te" in self.language:
            greeting = (
                f"నమస్కారం {self.customer_name} గారు, నేను {self.bank_name} నుండి తారా మాట్లాడుతున్నాను. "
                f"మీకు ₹{self.loan_amount} ప్రత్యేక {self.product_name} ఆఫర్ ఉంది. మాట్లాడవచ్చా?"
            )
        elif "hi" in self.language:
            greeting = (
                f"नमस्ते {self.customer_name} जी, मैं {self.bank_name} से तारा बोल रही हूँ। "
                f"आपके लिए ₹{self.loan_amount} का विशेष {self.product_name} ऑफर है। क्या दो मिनट बात कर सकते हैं?"
            )
        else:
            greeting = (
                f"Hello {self.customer_name}, I am TARA from {self.bank_name}. "
                f"We have a special {self.product_name} offer of ₹{self.loan_amount} for you. Can we speak?"
            )

        self.history.append(DialogueTurn(speaker="agent", text=greeting))
        return greeting

    def process_customer_turn(self, customer_text: str) -> TurnResponse:
        """
        Process customer's spoken transcript, update dialogue state, and generate next reply.

        Args:
            customer_text: Spoken text recognized by Prisma STT.

        Returns:
            TurnResponse containing next spoken response and conversational status.
        """
        clean_input = customer_text.strip()
        self.history.append(DialogueTurn(speaker="customer", text=clean_input))
        self.turn_count += 1
        lower_input = clean_input.lower()

        # 1. Check for callback request (check first, as "busy now, call later" is a callback)
        callback_signals = ["later", "tarvatha", "baad me", "after", "callback", "busy now", "repu"]
        if any(sig in lower_input for sig in callback_signals):
            self.detected_interest = "callback"
            self.is_completed = True
            reply = self._build_callback_reply()
            self.history.append(DialogueTurn(speaker="agent", text=reply))
            return TurnResponse(
                response_text=reply,
                turn_index=self.turn_count,
                intent="callback_requested",
                interest_level="callback",
                is_call_complete=True,
            )

        # 2. Check for rejection / not interested
        negative_signals = [
            "vaddu", "vadhu", "interest ledu", "oddhu", "time ledu", "call cut",
            "nahi", "nahi chahiye", "mat karo", "busy", "no", "not interested", "stop calling",
        ]
        if any(sig in lower_input for sig in negative_signals):
            self.detected_interest = "not_interested"
            self.is_completed = True
            reply = self._build_rejection_reply()
            self.history.append(DialogueTurn(speaker="agent", text=reply))
            return TurnResponse(
                response_text=reply,
                turn_index=self.turn_count,
                intent="declined",
                interest_level="not_interested",
                is_call_complete=True,
            )

        # 3. Check for interest rate inquiry
        rate_signals = ["vaddi", "interest", "rate", "byaaj", "percent", "emiti"]
        if any(sig in lower_input for sig in rate_signals):
            reply = self._build_rate_reply()
            self.detected_interest = "interested"
            self.history.append(DialogueTurn(speaker="agent", text=reply))
            return TurnResponse(
                response_text=reply,
                turn_index=self.turn_count,
                intent="inquiry_rate",
                interest_level="interested",
                is_call_complete=False,
            )

        # 4. Progression based on turns
        if self.turn_count == 2:
            # Positive response to initial pitch
            self.detected_interest = "interested"
            reply = self._build_features_pitch()
            self.history.append(DialogueTurn(speaker="agent", text=reply))
            return TurnResponse(
                response_text=reply,
                turn_index=self.turn_count,
                intent="pitch_features",
                interest_level="interested",
                is_call_complete=False,
            )

        if self.turn_count == 3:
            # Qualification / confirmation
            self.detected_interest = "interested"
            reply = self._build_qualification_question()
            self.history.append(DialogueTurn(speaker="agent", text=reply))
            return TurnResponse(
                response_text=reply,
                turn_index=self.turn_count,
                intent="qualify",
                interest_level="interested",
                is_call_complete=False,
            )

        # Turn 4 or higher: wrap-up and consent confirmation
        self.detected_interest = "interested"
        self.is_completed = True
        reply = self._build_success_wrapup()
        self.history.append(DialogueTurn(speaker="agent", text=reply))
        return TurnResponse(
            response_text=reply,
            turn_index=self.turn_count,
            intent="consent_confirmed",
            interest_level="interested",
            is_call_complete=True,
        )

    # Language-specific response generators

    def _build_rejection_reply(self) -> str:
        if "te" in self.language:
            return f"సరే {self.customer_name} గారు, మీ విలువైన సమయానికి ధన్యవాదాలు. శుభదినం!"
        if "hi" in self.language:
            return f"ठीक है {self.customer_name} जी, आपके बहुमूल्य समय के लिए धन्यवाद। आपका दिन शुभ हो!"
        return f"Understood {self.customer_name}, thank you for your time. Have a wonderful day!"

    def _build_callback_reply(self) -> str:
        if "te" in self.language:
            return f"సరే {self.customer_name} గారు, మేము మీకు అనుకూలమైన సమయంలో తిరిగి కాల్ చేస్తాము. ధన్యవాదాలు!"
        if "hi" in self.language:
            return f"ठीक है {self.customer_name} जी, हमारे प्रतिनिधि आपको सुविधाजनक समय पर संपर्क करेंगे। धन्यवाद!"
        return f"Certainly {self.customer_name}, we will schedule a callback at your convenience. Thank you!"

    def _build_rate_reply(self) -> str:
        if "te" in self.language:
            return (
                f"ఈ ఆఫర్ పై వార్షిక వడ్డీ రేటు కేవలం {self.interest_rate} మాత్రమే, మరియు ఎటువంటి దాచిన ఛార్జీలు లేవు. "
                f"మీకు ఈ లోన్ వివరాలు ముందుకు పంపవచ్చా?"
            )
        if "hi" in self.language:
            return (
                f"इस ऑफर पर ब्याज दर मात्र {self.interest_rate} प्रति वर्ष से शुरू होती है और कोई हिडन चार्ज नहीं है। "
                f"क्या हम इस प्रक्रिया को आगे बढ़ाएं?"
            )
        return (
            f"Our special interest rate starts at just {self.interest_rate} per annum with zero hidden charges. "
            f"Would you like to proceed with the application?"
        )

    def _build_features_pitch(self) -> str:
        if "te" in self.language:
            return (
                f"చాలా మంచిది {self.customer_name} గారు. ఈ లోన్ ఎటువంటి పేపర్‌వర్క్ లేకుండా మీ ఖాతాలో 10 నిమిషాల్లో జమ అవుతుంది. "
                f"మీకు ఎంత మొత్తం అవసరం ఉంటుంది?"
            )
        if "hi" in self.language:
            return (
                f"बहुत बढ़िया {self.customer_name} जी। यह लोन बिना किसी कागजी कार्रवाई के 10 मिनट में सीधे खाते में ट्रांसफर हो जाएगा। "
                f"आपको कितनी राशि की आवश्यकता है?"
            )
        return (
            f"Wonderful {self.customer_name}. This loan requires zero paperwork and gets disbursed to your account in 10 minutes. "
            f"What amount are you looking for?"
        )

    def _build_qualification_question(self) -> str:
        if "te" in self.language:
            return (
                f"ఖచ్చితంగా అండీ! మీ వాట్సాప్ లేదా ఎస్ఎంఎస్ కు తక్షణ అప్లికేషన్ లింక్ పంపించడానికి అనుమతిస్తారా?"
            )
        if "hi" in self.language:
            return (
                f"बिल्कुल! क्या मैं आपके रजिस्टर्ड मोबाइल नंबर पर व्हाट्सएप या एसएमएस के माध्यम से आवेदन लिंक भेज सकती हूँ?"
            )
        return (
            f"Certainly! May I have your permission to send the instant digital application link to your WhatsApp or mobile number?"
        )

    def _build_success_wrapup(self) -> str:
        if "te" in self.language:
            return (
                f"ధన్యవాదాలు {self.customer_name} గారు! వివరాలు మీ మొబైల్ కు పంపించబడ్డాయి. {self.bank_name} ను సంప్రదించినందుకు సంతోషం. నమస్కారం!"
            )
        if "hi" in self.language:
            return (
                f"धन्यवाद {self.customer_name} जी! विवरण आपके मोबाइल पर भेज दिए गए हैं। {self.bank_name} से बात करने के लिए धन्यवाद। नमस्ते!"
            )
        return (
            f"Thank you {self.customer_name}! The link has been sent to your mobile. It was a pleasure speaking with you from {self.bank_name}. Goodbye!"
        )
