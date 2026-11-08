"""Twilio outbound voice provider implementing TwiML Media Streams for real-time AI audio streaming."""

import logging
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET

try:
    from twilio.rest import Client as TwilioRestClient
except ImportError:
    TwilioRestClient = None  # type: ignore

from app.core.config import settings
from app.providers.base import CommunicationProvider, ProviderRequest, ProviderResult

logger = logging.getLogger("tara.providers.twilio_voice")


def build_media_stream_twiml(
    stream_url: str,
    parameters: Optional[Dict[str, str]] = None,
) -> str:
    """
    Construct TwiML document establishing bidirectional WebSocket media stream connection.

    Args:
        stream_url: WebSocket URL (wss://...) where Twilio will stream 8kHz mulaw audio.
        parameters: Custom key-value pairs passed as child <Parameter> elements inside <Stream>.

    Returns:
        Formatted XML string conforming to Twilio Media Streams specification.
    """
    response_elem = ET.Element("Response")
    connect_elem = ET.SubElement(response_elem, "Connect")
    stream_elem = ET.SubElement(connect_elem, "Stream", url=stream_url)

    if parameters:
        for key, value in parameters.items():
            if value is not None:
                ET.SubElement(stream_elem, "Parameter", name=str(key), value=str(value))

    # Output standard XML declaration and string
    return ET.tostring(response_elem, encoding="utf-8", xml_declaration=True).decode("utf-8")


class TwilioVoiceProvider(CommunicationProvider):
    """
    Outbound Voice communication provider using Twilio Telephony and Media Streams.

    Initiates outbound calls with an inline TwiML document that connects the live call
    to TARA's FastAPI WebSocket gateway for bidirectional AI voice conversation.
    """

    name = "twilio_voice"
    channel = "voice"

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        public_base_url: Optional[str] = None,
        mock_mode: Optional[bool] = None,
    ):
        self.account_sid = account_sid if account_sid is not None else settings.twilio_account_sid
        self.auth_token = auth_token if auth_token is not None else settings.twilio_auth_token
        self.from_number = from_number if from_number is not None else settings.twilio_from_number
        self.public_base_url = (public_base_url or settings.public_base_url).rstrip("/")
        self.mock_mode = mock_mode if mock_mode is not None else (not bool(self.account_sid and self.auth_token))

        self._client: Optional[Any] = None
        if not self.mock_mode and TwilioRestClient and self.account_sid and self.auth_token:
            self._client = TwilioRestClient(self.account_sid, self.auth_token)

    def get_stream_url(self) -> str:
        """Derive WebSocket stream URL from configured public base URL."""
        base = self.public_base_url
        if base.startswith("https://"):
            ws_base = "wss://" + base[8:]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[7:]
        else:
            ws_base = f"wss://{base}"
        return f"{ws_base}{settings.voice_stream_path}"

    async def send(self, request: ProviderRequest) -> ProviderResult:
        """
        Initiate an outbound Twilio call connected to TARA's WebSocket media stream.

        Args:
            request: ProviderRequest containing recipient phone, template variables, and metadata.

        Returns:
            ProviderResult with call SID and dispatch status.
        """
        if not request.recipient_phone:
            return ProviderResult(
                success=False,
                error="Recipient phone number is required for voice call",
                status="FAILED",
            )

        # Build custom parameters passed into the stream for session context
        meta = request.metadata or {}
        stream_params = {
            "customer_name": request.variables.get("customer_name", "Customer"),
            "language": request.variables.get("language", settings.voice_default_language),
            "bank_name": request.variables.get("bank_name", "Bank"),
            "product_name": request.variables.get("product_name", "Personal Loan"),
            "loan_amount": request.variables.get("loan_amount", "5,00,000"),
            "interest_rate": request.variables.get("interest_rate", "10.49%"),
            "campaign_id": str(meta.get("campaign_id", "")),
            "communication_id": str(meta.get("communication_id", "")),
            "tenant_id": str(meta.get("tenant_id", "")),
        }

        stream_url = self.get_stream_url()
        twiml_payload = build_media_stream_twiml(stream_url=stream_url, parameters=stream_params)

        status_callback_url = f"{self.public_base_url}/api/webhooks/twilio/status"

        if self.mock_mode:
            import uuid
            mock_sid = f"CA{uuid.uuid4().hex[:32]}"
            logger.info("Mock mode: Simulated Twilio call dispatch to %s (SID: %s)", request.recipient_phone, mock_sid)
            return ProviderResult(
                success=True,
                provider_ref=mock_sid,
                raw_response={
                    "sid": mock_sid,
                    "status": "queued",
                    "simulated": True,
                    "twiml": twiml_payload,
                },
                status="DISPATCHED",
            )

        if not self._client:
            return ProviderResult(
                success=False,
                error="Twilio client not initialized (missing credentials)",
                status="FAILED",
            )

        try:
            call = self._client.calls.create(
                to=request.recipient_phone,
                from_=self.from_number,
                twiml=twiml_payload,
                status_callback=status_callback_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
            )

            logger.info("Twilio outbound call placed successfully: %s to %s", call.sid, request.recipient_phone)
            return ProviderResult(
                success=True,
                provider_ref=call.sid,
                raw_response={"sid": call.sid, "status": call.status},
                status="DISPATCHED",
            )
        except Exception as exc:
            logger.error("Failed to place Twilio outbound call to %s: %s", request.recipient_phone, exc)
            return ProviderResult(
                success=False,
                error=str(exc),
                status="FAILED",
            )

