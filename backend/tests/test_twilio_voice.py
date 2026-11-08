"""Unit tests for Twilio Voice provider and TwiML Media Stream generation."""

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch
import pytest

from app.providers.base import ProviderRequest
from app.providers.twilio_voice import TwilioVoiceProvider, build_media_stream_twiml


def test_build_media_stream_twiml():
    """Verify TwiML generation produces valid XML conforming to Twilio Media Streams specification."""
    stream_url = "wss://api.example.com/api/voice/stream"
    params = {
        "customer_name": "Ravi",
        "language": "te-IN",
        "loan_amount": "5,00,000",
    }
    twiml_str = build_media_stream_twiml(stream_url=stream_url, parameters=params)

    # Parse XML to verify structure
    root = ET.fromstring(twiml_str)
    assert root.tag == "Response"
    connect_node = root.find("Connect")
    assert connect_node is not None
    stream_node = connect_node.find("Stream")
    assert stream_node is not None
    assert stream_node.attrib.get("url") == stream_url

    # Check child parameters
    param_nodes = stream_node.findall("Parameter")
    assert len(param_nodes) == 3
    param_dict = {p.attrib.get("name"): p.attrib.get("value") for p in param_nodes}
    assert param_dict["customer_name"] == "Ravi"
    assert param_dict["language"] == "te-IN"
    assert param_dict["loan_amount"] == "5,00,000"


def test_stream_url_derivation():
    """Verify stream URL converts http to ws and https to wss correctly."""
    p1 = TwilioVoiceProvider(public_base_url="https://voice.gnani.ai", mock_mode=True)
    assert p1.get_stream_url() == "wss://voice.gnani.ai/api/voice/stream"

    p2 = TwilioVoiceProvider(public_base_url="http://localhost:8000", mock_mode=True)
    assert p2.get_stream_url() == "ws://localhost:8000/api/voice/stream"


def run_coroutine(coro):
    """Execute non-suspending coroutine synchronously without Windows socketpair event loop."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


def test_mock_mode_dispatch():
    """Verify mock mode creates simulated Call SID and DISPATCHED status."""
    provider = TwilioVoiceProvider(mock_mode=True)
    req = ProviderRequest(
        recipient_phone="+919876543210",
        variables={"customer_name": "Ananya", "language": "hi-IN"},
        metadata={"campaign_id": "camp123"},
    )
    result = run_coroutine(provider.send(req))
    assert result.success is True
    assert result.status == "DISPATCHED"
    assert result.provider_ref is not None
    assert result.provider_ref.startswith("CA")
    assert result.raw_response.get("simulated") is True


def test_missing_phone_number_returns_failure():
    """Verify missing phone number fails validation without dispatching."""
    provider = TwilioVoiceProvider(mock_mode=True)
    req = ProviderRequest(recipient_phone="", variables={})
    result = run_coroutine(provider.send(req))
    assert result.success is False
    assert result.status == "FAILED"
    assert "Recipient phone number is required" in result.error


def test_twilio_client_exception_handling():
    """Verify exceptions from Twilio REST client are captured cleanly in ProviderResult."""
    provider = TwilioVoiceProvider(
        account_sid="ACmock_sid",
        auth_token="mock_token",
        from_number="+1234567890",
        mock_mode=False,
    )
    provider._client = MagicMock()
    provider._client.calls.create.side_effect = Exception("Twilio authentication failure: 20003")

    req = ProviderRequest(recipient_phone="+919876543210")
    result = run_coroutine(provider.send(req))
    assert result.success is False
    assert result.status == "FAILED"
    assert "20003" in result.error

