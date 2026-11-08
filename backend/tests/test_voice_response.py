"""Unit tests for TARA multi-turn voice response engine."""

from app.services.conversation.voice_response import VoiceResponseEngine


def test_initial_greeting_telugu():
    """Verify Telugu greeting includes customer name, bank name, and loan amount."""
    engine = VoiceResponseEngine(
        customer_name="Ramesh",
        bank_name="Andhra Bank",
        loan_amount="3,00,000",
        language="te-IN",
    )
    greeting = engine.generate_initial_greeting()
    assert "Ramesh" in greeting
    assert "Andhra Bank" in greeting
    assert "3,00,000" in greeting
    assert len(engine.history) == 1
    assert engine.turn_count == 1


def test_initial_greeting_hindi():
    """Verify Hindi greeting includes customer name, bank name, and loan amount."""
    engine = VoiceResponseEngine(
        customer_name="Vikram",
        bank_name="SBI",
        loan_amount="5,00,000",
        language="hi-IN",
    )
    greeting = engine.generate_initial_greeting()
    assert "Vikram" in greeting
    assert "SBI" in greeting
    assert "5,00,000" in greeting
    assert engine.turn_count == 1


def test_happy_path_multi_turn_conversation():
    """Verify standard positive conversation executes at least 3-4 consecutive turns."""
    engine = VoiceResponseEngine(customer_name="Sita", language="te-IN")
    engine.generate_initial_greeting()

    # Turn 1: Customer shows interest
    t1 = engine.process_customer_turn("Avunu, cheppandi")
    assert t1.turn_index == 2
    assert t1.interest_level == "interested"
    assert t1.is_call_complete is False
    assert "పేపర్‌వర్క్ లేకుండా" in t1.response_text

    # Turn 2: Customer specifies amount
    t2 = engine.process_customer_turn("Naku rendu lakshalu kavali")
    assert t2.turn_index == 3
    assert t2.interest_level == "interested"
    assert t2.is_call_complete is False
    assert "లింక్ పంపించడానికి" in t2.response_text

    # Turn 3: Customer consents to link
    t3 = engine.process_customer_turn("Sare, pampandi")
    assert t3.turn_index == 4
    assert t3.interest_level == "interested"
    assert t3.is_call_complete is True
    assert "ధన్యవాదాలు" in t3.response_text


def test_rejection_path():
    """Verify customer rejection politely wraps up call with not_interested status."""
    engine = VoiceResponseEngine(customer_name="Ravi", language="te-IN")
    engine.generate_initial_greeting()

    resp = engine.process_customer_turn("Naku vaddu, interest ledu")
    assert resp.is_call_complete is True
    assert resp.interest_level == "not_interested"
    assert "విలువైన సమయానికి ధన్యవాదాలు" in resp.response_text


def test_interest_rate_inquiry():
    """Verify customer asking about interest rate gets rate reply and call stays active."""
    engine = VoiceResponseEngine(customer_name="Arun", interest_rate="9.99%", language="en-IN")
    engine.generate_initial_greeting()

    resp = engine.process_customer_turn("What is the interest rate?")
    assert resp.is_call_complete is False
    assert resp.interest_level == "interested"
    assert "9.99%" in resp.response_text


def test_callback_request():
    """Verify customer asking for callback ends call with callback status."""
    engine = VoiceResponseEngine(customer_name="Pooja", language="hi-IN")
    engine.generate_initial_greeting()

    resp = engine.process_customer_turn("Abhi busy hoon, baad me call karo")
    assert resp.is_call_complete is True
    assert resp.interest_level == "callback"
    assert "सुविधाजनक समय पर" in resp.response_text

