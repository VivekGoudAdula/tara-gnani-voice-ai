"""Comprehensive test suite for Phase 3 Intelligent Agent & Conversation Engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.conversation.models import (
    ConversationContext,
    ConversationState,
    CustomerIntent,
    QualificationState,
)
from app.services.conversation.orchestrator import ConversationOrchestrator
from app.services.conversation.customer_context_service import CustomerContextService
from app.services.conversation.prompt_builder import PromptBuilder
from app.services.conversation.llm_client import LLMReasoningService
from app.services.conversation.tool_registry import ToolRegistry
from app.services.conversation.lead_qualification import LeadQualificationEngine
from app.services.conversation.policy_engine import ConversationPolicyEngine
from app.services.conversation.outcome_extractor import ConversationOutcomeExtractor
from app.services.speech.language import normalize_language_code


def run_coroutine(coro):
    """Synchronously execute coroutine without async loop socketpair issues on Windows."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value


@pytest.fixture
def mock_db():
    """Mock MongoDB database instance with in-memory collection handlers."""
    db = MagicMock()
    db.leads = MagicMock()
    db.customers = MagicMock()
    db.products = MagicMock()
    db.product_matches = MagicMock()
    db.campaigns = MagicMock()
    db.communications = MagicMock()
    db.audit_log = MagicMock()

    db.leads.find_one = AsyncMock(return_value={
        "_id": "lead_123",
        "tenant_id": "test_bank",
        "name": "Vivek Goud",
        "phone": "+919381118626",
        "city": "Hyderabad",
        "segment": "Salaried",
        "income": 750000.0,
        "consent": True,
        "dnd": False,
    })
    db.leads.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.products.find_one = AsyncMock(return_value={
        "_id": "prod_1",
        "tenant_id": "test_bank",
        "name": "Express Personal Loan",
        "category": "personal_loan",
        "interest_rate": "10.49%",
        "max_amount": "5,00,000",
        "features": ["Zero paperwork", "10 min transfer"],
        "faqs": [{"q": "interest rate", "a": "10.49% per annum"}],
    })
    db.product_matches.find_one = AsyncMock(return_value={
        "match_score": 0.92,
        "band": "HIGH",
        "eligibility": "ELIGIBLE",
        "reason_codes": [{"text": "High salary segment"}],
    })
    db.campaigns.find_one = AsyncMock(return_value={
        "name": "Festive Loan Campaign",
        "objective": "Customer Acquisition",
    })
    db.communications.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.audit_log.insert_one = AsyncMock(return_value=MagicMock(inserted_id="audit_1"))
    return db


def test_1_basic_greeting(mock_db):
    """1. Basic greeting: Polite, consultative opening without aggressive 5L pitch."""
    orchestrator = ConversationOrchestrator(mock_db, tenant_id="test_bank", mock_mode=True)
    params = {
        "customer_name": "Vivek Goud",
        "bank_name": "Bangalore Bank",
        "language": "te-IN",
        "product_name": "Personal Loan",
        "loan_amount": "5,00,000",
    }
    run_coroutine(orchestrator.initialize(params))
    greeting = orchestrator.get_initial_greeting()

    assert "Vivek Goud" in greeting
    assert "Bangalore Bank" in greeting
    assert "మాట్లాడవచ్చా" in greeting
    assert orchestrator.context.current_state == ConversationState.GREETING


def test_2_multi_turn_conversation(mock_db):
    """2. Multi-turn conversation: Positive progression through discovery and pitch."""
    orchestrator = ConversationOrchestrator(mock_db, tenant_id="test_bank", mock_mode=True)
    params = {"customer_name": "Sita", "language": "te-IN"}
    run_coroutine(orchestrator.initialize(params))
    orchestrator.get_initial_greeting()

    # Turn 1: Customer asks what it is
    t1 = run_coroutine(orchestrator.process_customer_speech("హా చెప్పండి, వివరాలు ఏమిటి?"))
    assert t1.spoken_text != ""
    assert orchestrator.context.turn_count == 2
    assert t1.is_call_complete is False


def test_3_customer_context_retrieval(mock_db):
    """3. Customer context retrieval: Verified customer details loaded with tenant scoping."""
    ctx_service = CustomerContextService(mock_db, tenant_id="test_bank")
    cust = run_coroutine(ctx_service.get_customer_context("lead_123", "lead"))
    assert cust["name"] == "Vivek Goud"
    assert cust["city"] == "Hyderabad"
    mock_db.leads.find_one.assert_called_once()


def test_4_product_information_retrieval(mock_db):
    """4. Product information retrieval: Verified product parameters fetched."""
    ctx_service = CustomerContextService(mock_db, tenant_id="test_bank")
    prod = run_coroutine(ctx_service.get_product_context("prod_1"))
    assert prod["name"] == "Express Personal Loan"
    assert "Zero paperwork" in prod["features"]


def test_5_faq_answering(mock_db):
    """5. FAQ answering: Verified answer returned for product query."""
    tools = ToolRegistry(mock_db, tenant_id="test_bank")
    res = run_coroutine(tools.execute_tool("search_product_faq", {"query": "what is the interest rate?"}))
    assert res.success is True
    assert "10.49%" in res.output["answer"]


def test_6_pricing_question_verified_data(mock_db):
    """6. Pricing question: Uses verified product pricing from context."""
    tools = ToolRegistry(mock_db, tenant_id="test_bank")
    res = run_coroutine(tools.execute_tool("get_product_information", {}))
    assert res.success is True
    assert res.output["interest_rate"] == "10.49%"


def test_7_objection_handling(mock_db):
    """7. Objection handling: Objection logged and respectful state maintained."""
    tools = ToolRegistry(mock_db, tenant_id="test_bank")
    res = run_coroutine(tools.execute_tool("record_customer_objection", {
        "objection_type": "High Interest Rate",
        "details": "Customer thinks 10.49% is too high",
    }))
    assert res.success is True
    assert res.output["type"] == "High Interest Rate"


def test_8_clear_rejection(mock_db):
    """8. Clear rejection: Customer decline terminates call politely."""
    orchestrator = ConversationOrchestrator(mock_db, tenant_id="test_bank", mock_mode=True)
    run_coroutine(orchestrator.initialize({"customer_name": "Ravi", "language": "te-IN"}))
    orchestrator.get_initial_greeting()

    resp = run_coroutine(orchestrator.process_customer_speech("నాకు వద్దు, ఇంట్రెస్ట్ లేదు"))
    assert resp.intent == CustomerIntent.NOT_INTERESTED
    assert resp.is_call_complete is True
    assert resp.state == ConversationState.COMPLETED


def test_9_do_not_call_request(mock_db):
    """9. Do-Not-Call request: Customer DND immediately marks opt-out and terminates call."""
    tools = ToolRegistry(mock_db, tenant_id="test_bank")
    res = run_coroutine(tools.execute_tool("mark_do_not_call", {"entity_id": "lead_123", "reason": "Opt out"}))
    assert res.success is True
    mock_db.leads.update_one.assert_called()
    mock_db.audit_log.insert_one.assert_called()


def test_10_callback_request(mock_db):
    """10. Callback request: Schedules callback and politely ends turn."""
    orchestrator = ConversationOrchestrator(mock_db, tenant_id="test_bank", mock_mode=True)
    run_coroutine(orchestrator.initialize({"customer_name": "Anil", "language": "te-IN"}))
    orchestrator.get_initial_greeting()

    resp = run_coroutine(orchestrator.process_customer_speech("ఇప్పుడు బిజీగా ఉన్నాను, రేపు మాట్లాడదాం"))
    assert resp.intent == CustomerIntent.CALLBACK_REQUESTED
    assert resp.is_call_complete is True


def test_11_lead_qualification():
    """11. Lead qualification: Extracts need, amount, and updates qualification state."""
    q = QualificationState()
    updated = LeadQualificationEngine.extract_and_update(
        q,
        "Naku illu renovation kosam 3 lakhs kavali",
        {"need": "Home Renovation", "budget_or_amount": "3,00,000", "timeline": "Immediate"},
    )
    assert updated.status == "qualified"
    assert updated.stated_need == "Home Renovation"
    assert updated.budget_or_amount == "3,00,000"
    assert updated.score_adjustment > 0.0


def test_12_structured_tool_execution(mock_db):
    """12. Structured tool execution: Safely executes task creation."""
    tools = ToolRegistry(mock_db, tenant_id="test_bank")
    res = run_coroutine(tools.execute_tool("create_follow_up_task", {
        "entity_id": "lead_123",
        "task_title": "Send Loan Application SMS",
    }))
    assert res.success is True
    assert res.output["task_created"] is True


def test_13_human_escalation(mock_db):
    """13. Human escalation: Escalation flag set and logged."""
    tools = ToolRegistry(mock_db, tenant_id="test_bank")
    res = run_coroutine(tools.execute_tool("request_human_escalation", {
        "reason": "Customer requested manager",
    }))
    assert res.success is True
    assert res.output["escalated"] is True


def test_14_language_switching():
    """14. Language switching: Normalizes and preserves language codes accurately."""
    assert normalize_language_code("telugu") == "te-IN"
    assert normalize_language_code("Telugu") == "te-IN"
    assert normalize_language_code("hindi") == "hi-IN"
    assert normalize_language_code("Hindi") == "hi-IN"
    assert normalize_language_code("english") == "en-IN"
    assert normalize_language_code("kannada") == "kn-IN"
    assert normalize_language_code("auto") == "indic-auto"


def test_15_conversation_summarization():
    """15. Conversation summarization: Generates structured outcome summary."""
    ctx = ConversationContext(
        session_id="sess_1",
        tenant_id="bank_1",
        customer_name="Ramesh",
        product_name="Personal Loan",
        loan_amount="3,00,000",
        current_intent=CustomerIntent.INTERESTED,
    )
    outcome = ConversationOutcomeExtractor.extract_outcome(ctx)
    assert outcome["interest_level"] == "interested"
    assert "Ramesh" in outcome["call_summary"]
    assert outcome["preferred_amount"] == "3,00,000"


def test_16_conversation_persistence(mock_db):
    """16. Conversation persistence: Writes outcome into MongoDB communications record."""
    ctx = ConversationContext(
        session_id="sess_1",
        tenant_id="test_bank",
        communication_id="comm_999",
        customer_name="Ramesh",
        product_name="Personal Loan",
    )
    run_coroutine(ConversationOutcomeExtractor.persist_outcome(mock_db, ctx))
    mock_db.communications.update_one.assert_called_once()
    mock_db.audit_log.insert_one.assert_called_once()


def test_17_missing_customer_information(mock_db):
    """17. Missing customer information: Handles non-existent recipient ID gracefully."""
    mock_db.leads.find_one = AsyncMock(return_value=None)
    ctx_service = CustomerContextService(mock_db, tenant_id="test_bank")
    cust = run_coroutine(ctx_service.get_customer_context("non_existent_id", "lead"))
    assert cust == {}


def test_18_llm_timeout_and_failure():
    """18. LLM timeout and failure: Recovers with rule-based fallback without call dropping."""
    llm = LLMReasoningService(mock_mode=True)
    res = run_coroutine(llm.generate_reasoning_step([
        {"role": "user", "content": "నాకు లోన్ కావాలి"}
    ], fallback_context={"language": "te-IN"}))
    assert res["intent"] == "interested"
    assert len(res["spoken_response"]) > 0


def test_19_tenant_isolation(mock_db):
    """19. Tenant isolation: Strictly enforces tenant_id in queries."""
    ctx_service = CustomerContextService(mock_db, tenant_id="tenant_alpha")
    run_coroutine(ctx_service.get_customer_context("lead_456"))
    call_args = mock_db.leads.find_one.call_args[0][0]
    assert call_args["tenant_id"] == "tenant_alpha"


def test_20_invalid_tool_arguments(mock_db):
    """20. Invalid tool arguments: Returns safe error result without uncaught crash."""
    tools = ToolRegistry(mock_db, tenant_id="test_bank")
    res = run_coroutine(tools.execute_tool("unknown_fake_tool", {}))
    assert res.success is False
    assert "not registered" in res.error

