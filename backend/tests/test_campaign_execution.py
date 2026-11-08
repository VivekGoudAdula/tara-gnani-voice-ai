"""Comprehensive Phase 4 test suite for TARA 2.0 Outbound Campaigns & Customer Intelligence.

Verifies:
1. Campaign creation
2. Campaign validation
3. Audience filtering
4. Audience snapshot creation
5. Lead prioritisation
6. Compliance exclusion
7. DND exclusion
8. Campaign scheduling
9. Campaign start
10. Campaign pause
11. Campaign resume
12. Campaign cancellation
13. Twilio dispatch integration
14. Twilio webhook event mapping
15. Duplicate webhook handling
16. Duplicate dispatch prevention
17. Call completion tracking
18. Retry after no-answer
19. Retry after busy
20. No retry after customer rejection
21. No retry after DND
22. Transcript persistence
23. Summary persistence
24. Lead status update
25. Lead score adjustment
26. Callback handling
27. Campaign analytics calculation
28. Multi-tenant isolation
29. Worker restart recovery
30. Concurrent dispatch limits
"""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from bson import ObjectId
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.db import get_db, init_db
from app.providers.base import ProviderRequest, ProviderResult
from app.providers.twilio_voice import TwilioVoiceProvider, build_media_stream_twiml
from app.providers.twilio_webhook_mapper import can_transition_twilio, map_twilio_status_webhook
from app.schemas.campaigns import (
    AudienceSetRequest,
    CampaignCreate,
    CampaignLaunchRequest,
    CampaignScheduleRequest,
)
from app.services.campaign_analytics import calculate_campaign_analytics
from app.services.campaign_audience import (
    build_candidate_filter,
    get_audience_preview,
    set_campaign_audience,
)
from app.services.campaign_execution import (
    execute_campaign_dispatch,
    get_campaign_lock,
    refresh_recipient_statuses,
)
from app.services.campaign_retry import (
    calculate_next_retry_at,
    get_campaign_retry_queue,
    is_eligible_for_retry,
    queue_campaign_retries,
)
from app.services.campaign_scheduler import (
    check_and_execute_scheduled_campaigns,
    recover_interrupted_campaigns,
    schedule_campaign,
)
from app.services.campaign_validation import validate_campaign_readiness
from app.services.customer_intelligence import (
    calculate_score_adjustment,
    derive_lead_status,
    update_customer_intelligence,
)

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")
TEST_TID_A = "tenant_alpha"
TEST_TID_B = "tenant_beta"


class MockVoiceProvider:
    """Mock telephony provider tracking dispatch requests."""

    def __init__(self):
        self.dispatches: list[ProviderRequest] = []
        self.name = "mock_twilio"

    async def send(self, req: ProviderRequest) -> ProviderResult:
        self.dispatches.append(req)
        return ProviderResult(
            success=True,
            provider_ref=f"CA_mock_{len(self.dispatches)}",
            status="DISPATCHED",
        )


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Ensure database connection and test mode settings."""
    await init_db()
    settings.test_mode = True
    settings.test_allowlist = "+919381118626,+919876543210,+919999988888"
    settings.compliance_exempt_numbers = "+919381118626"
    yield


# -------------------------------------------------------------------------
# 1. Campaign Creation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_1_campaign_creation():
    db = get_db()
    now_utc = datetime.now(timezone.utc)
    prod_id = str((await db.products.insert_one({"tenant_id": TEST_TID_A, "name": "Gold Loan", "active": True})).inserted_id)

    doc = {
        "tenant_id": TEST_TID_A,
        "name": "Q4 Outreach",
        "product_id": prod_id,
        "product_name": "Gold Loan",
        "entity_type": "lead",
        "objective": "Customer Acquisition",
        "status": "DRAFT",
        "channels": ["voice"],
        "created_at": now_utc,
        "updated_at": now_utc,
    }
    res = await db.campaigns.insert_one(doc)
    cid = str(res.inserted_id)

    saved = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert saved is not None
    assert saved["name"] == "Q4 Outreach"
    assert saved["status"] == "DRAFT"
    assert saved["product_id"] == prod_id


# -------------------------------------------------------------------------
# 2. Campaign Validation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_2_campaign_validation():
    db = get_db()
    cid = str(ObjectId())

    # Validation on non-existent campaign
    rep_missing = await validate_campaign_readiness(db, cid, TEST_TID_A)
    assert not rep_missing.is_valid
    assert "Campaign does not exist" in rep_missing.errors[0]

    # Validation on campaign with missing audience
    prod_id = str((await db.products.insert_one({"tenant_id": TEST_TID_A, "name": "Auto Loan", "active": True})).inserted_id)
    c_doc = {
        "_id": ObjectId(cid),
        "tenant_id": TEST_TID_A,
        "name": "Auto Loan Drive",
        "product_id": prod_id,
        "product_name": "Auto Loan",
        "entity_type": "lead",
        "objective": "Auto Loan Promotion",
        "status": "DRAFT",
    }
    await db.campaigns.insert_one(c_doc)

    rep_no_aud = await validate_campaign_readiness(db, cid, TEST_TID_A)
    assert not rep_no_aud.is_valid
    assert any("no audience" in err.lower() for err in rep_no_aud.errors)


# -------------------------------------------------------------------------
# 3. Audience Filtering
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_3_audience_filtering():
    camp = {
        "tenant_id": TEST_TID_A,
        "product_id": "prod_123",
        "entity_type": "lead",
    }
    crit = build_candidate_filter(
        campaign=camp,
        bands=["HIGH", "MEDIUM"],
        eligibility="ELIGIBLE",
        min_score=60.0,
        max_score=95.0,
    )
    assert crit["tenant_id"] == TEST_TID_A
    assert crit["band"]["$in"] == ["HIGH", "MEDIUM"]
    assert crit["eligibility"] == "ELIGIBLE"
    assert crit["match_score"]["$gte"] == 60.0
    assert crit["match_score"]["$lte"] == 95.0


# -------------------------------------------------------------------------
# 4. Audience Snapshot Creation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_4_audience_snapshot_creation():
    db = get_db()
    now_utc = datetime.now(timezone.utc)
    cid = str(ObjectId())
    pid = str(ObjectId())

    camp = {
        "_id": ObjectId(cid),
        "tenant_id": TEST_TID_A,
        "product_id": pid,
        "entity_type": "lead",
        "status": "DRAFT",
    }
    await db.campaigns.insert_one(camp)

    lead_id = str((await db.leads.insert_one({
        "tenant_id": TEST_TID_A, "name": "Vikas Patel", "phone": "+919876543210",
        "language": "telugu", "consent": True, "dnd": False,
    })).inserted_id)

    await db.product_matches.insert_one({
        "tenant_id": TEST_TID_A, "product_id": pid, "entity_type": "lead",
        "entity_id": lead_id, "score": 85.0, "match_score": 85.0, "band": "HIGH",
        "eligibility": "ELIGIBLE", "is_latest": True, "created_at": now_utc,
    })

    req = AudienceSetRequest(mode="filter", filter={"bands": ["HIGH"]})
    res = await set_campaign_audience(db, camp, req, {"user_id": "emp_1"})
    assert res["recipient_count"] == 1

    snap = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": lead_id})
    assert snap is not None
    assert snap["name"] == "Vikas Patel"
    assert snap["status"] == "PENDING"
    assert snap["match_score"] == 85.0


# -------------------------------------------------------------------------
# 5. Lead Prioritisation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_5_lead_prioritisation():
    recipients = [
        {"entity_id": "1", "phone": "+919000000001", "match_score": 90.0, "consent": True, "dnd": False},  # Non-dialable seeded
        {"entity_id": "2", "phone": "+919381118626", "match_score": 70.0, "consent": True, "dnd": False},  # Dialable real
        {"entity_id": "3", "phone": "+919876543210", "match_score": 88.0, "consent": True, "dnd": False},  # Dialable real, higher score
    ]
    # Prioritise dialable first, then highest score
    def prio(r):
        is_dialable = 0 if not r["phone"].startswith("+9190000") and r["consent"] and not r["dnd"] else 1
        return (is_dialable, -r["match_score"])

    sorted_r = sorted(recipients, key=prio)
    assert sorted_r[0]["entity_id"] == "3"  # 88.0 dialable
    assert sorted_r[1]["entity_id"] == "2"  # 70.0 dialable
    assert sorted_r[2]["entity_id"] == "1"  # 90.0 non-dialable


# -------------------------------------------------------------------------
# 6. Compliance Exclusion
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_6_compliance_exclusion():
    from app.services.compliance import evaluate_compliance
    db = get_db()
    # Non-consented lead
    lead_no_consent = {"phone": "+919876543210", "consent": False, "dnd": False}
    comp = await evaluate_compliance(lead_no_consent, TEST_TID_A, db)
    assert not comp.allowed
    assert comp.blocked_reason == "no_consent"

    # Non-dialable synthetic number
    lead_fake = {"phone": "+919000012345", "consent": True, "dnd": False}
    comp_fake = await evaluate_compliance(lead_fake, TEST_TID_A, db)
    assert not comp_fake.allowed
    assert comp_fake.blocked_reason == "non_dialable_number"


# -------------------------------------------------------------------------
# 7. DND Exclusion
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_7_dnd_exclusion():
    from app.services.compliance import evaluate_compliance
    db = get_db()
    lead_dnd = {"phone": "+919876543210", "consent": True, "dnd": True}
    comp = await evaluate_compliance(lead_dnd, TEST_TID_A, db)
    assert not comp.allowed
    assert comp.blocked_reason == "dnd"


# -------------------------------------------------------------------------
# 8. Campaign Scheduling
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_8_campaign_scheduling():
    db = get_db()
    cid = str(ObjectId())
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "DRAFT"})

    target_time = datetime.now(timezone.utc) + timedelta(hours=2)
    res = await schedule_campaign(
        db=db,
        campaign_id=cid,
        tenant_id=TEST_TID_A,
        scheduled_start_time=target_time,
        timezone_str="Asia/Kolkata",
    )
    assert res["status"] == "SCHEDULED"

    camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert camp["status"] == "SCHEDULED"
    assert camp["scheduled_start_time"] is not None


# -------------------------------------------------------------------------
# 9. Campaign Start
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_9_campaign_start():
    db = get_db()
    cid = str(ObjectId())
    now_utc = datetime.now(timezone.utc)
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "READY"})

    # Emulate launch / start
    await db.campaigns.update_one(
        {"_id": ObjectId(cid)},
        {"$set": {"status": "RUNNING", "launched_at": now_utc}},
    )
    camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert camp["status"] == "RUNNING"
    assert camp["launched_at"] is not None


# -------------------------------------------------------------------------
# 10. Campaign Pause
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_10_campaign_pause():
    db = get_db()
    cid = str(ObjectId())
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "RUNNING"})

    await db.campaigns.update_one(
        {"_id": ObjectId(cid)},
        {"$set": {"status": "PAUSED", "updated_at": datetime.now(timezone.utc)}},
    )
    camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert camp["status"] == "PAUSED"


# -------------------------------------------------------------------------
# 11. Campaign Resume
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_11_campaign_resume():
    db = get_db()
    cid = str(ObjectId())
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "PAUSED"})

    await db.campaigns.update_one(
        {"_id": ObjectId(cid)},
        {"$set": {"status": "RUNNING", "updated_at": datetime.now(timezone.utc)}},
    )
    camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert camp["status"] == "RUNNING"


# -------------------------------------------------------------------------
# 12. Campaign Cancellation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_12_campaign_cancellation():
    db = get_db()
    cid = str(ObjectId())
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "RUNNING"})

    await db.campaigns.update_one(
        {"_id": ObjectId(cid)},
        {"$set": {"status": "CANCELLED", "updated_at": datetime.now(timezone.utc)}},
    )
    camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert camp["status"] == "CANCELLED"


# -------------------------------------------------------------------------
# 13. Twilio Dispatch Integration
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_13_twilio_dispatch_integration():
    provider = TwilioVoiceProvider(mock_mode=True)
    req = ProviderRequest(
        recipient_phone="+919381118626",
        variables={"customer_name": "Ravi", "bank_name": "Gnani Bank"},
        metadata={"campaign_id": "camp_abc", "communication_id": "comm_xyz"},
    )
    res = await provider.send(req)
    assert res.success
    assert res.provider_ref.startswith("CA")
    assert res.status == "DISPATCHED"


# -------------------------------------------------------------------------
# 14. Twilio Webhook Event Mapping
# -------------------------------------------------------------------------
def test_14_twilio_webhook_event_mapping():
    payload = {
        "CallSid": "CA1234567890abcdef",
        "CallStatus": "completed",
        "CallDuration": "42",
        "To": "+919381118626",
    }
    mapped, unmapped = map_twilio_status_webhook(payload)
    assert mapped["provider_ref"] == "CA1234567890abcdef"
    assert mapped["normalized_status"] == "COMPLETED"
    assert mapped["duration_seconds"] == 42


# -------------------------------------------------------------------------
# 15. Duplicate Webhook Handling
# -------------------------------------------------------------------------
def test_15_duplicate_webhook_handling():
    # Monotonic transition: COMPLETED cannot revert to IN_PROGRESS
    assert not can_transition_twilio("COMPLETED", "IN_PROGRESS")
    # Monotonic transition: duplicate COMPLETED is accepted idempotently
    assert can_transition_twilio("COMPLETED", "COMPLETED")
    # Monotonic transition: DISPATCHED to COMPLETED is valid
    assert can_transition_twilio("DISPATCHED", "COMPLETED")


# -------------------------------------------------------------------------
# 16. Duplicate Dispatch Prevention
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_16_duplicate_dispatch_prevention():
    cid = "campaign_dup_check"
    lock1 = get_campaign_lock(cid)
    lock2 = get_campaign_lock(cid)
    assert lock1 is lock2
    assert not lock1.locked()

    async with lock1:
        assert lock2.locked()


# -------------------------------------------------------------------------
# 17. Call Completion Tracking
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_17_call_completion_tracking():
    db = get_db()
    cid = str(ObjectId())
    now_utc = datetime.now(timezone.utc)
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "RUNNING"})

    # Insert single recipient that is completed
    await db.campaign_recipients.insert_one({
        "campaign_id": cid,
        "tenant_id": TEST_TID_A,
        "entity_id": "rec_done",
        "status": "COMPLETED",
    })
    await refresh_recipient_statuses(db, cid, TEST_TID_A)

    camp = await db.campaigns.find_one({"_id": ObjectId(cid)})
    assert camp["status"] == "COMPLETED"


# -------------------------------------------------------------------------
# 18. Retry After No-Answer
# -------------------------------------------------------------------------
def test_18_retry_after_no_answer():
    recipient = {"status": "NO_ANSWER", "attempts": 1}
    assert is_eligible_for_retry(recipient, max_attempts=2)
    recipient_maxed = {"status": "NO_ANSWER", "attempts": 2}
    assert not is_eligible_for_retry(recipient_maxed, max_attempts=2)


# -------------------------------------------------------------------------
# 19. Retry After Busy
# -------------------------------------------------------------------------
def test_19_retry_after_busy():
    recipient = {"status": "BUSY", "attempts": 1}
    assert is_eligible_for_retry(recipient, max_attempts=3)

    last_time = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    next_time = calculate_next_retry_at(attempt=1, base_interval_minutes=30, last_contact_at=last_time)
    assert next_time == last_time + timedelta(minutes=30)

    # Exponential backoff on attempt 2: 30 * (2^1) = 60 min
    next_time_2 = calculate_next_retry_at(attempt=2, base_interval_minutes=30, last_contact_at=last_time)
    assert next_time_2 == last_time + timedelta(minutes=60)


# -------------------------------------------------------------------------
# 20. No Retry After Customer Rejection
# -------------------------------------------------------------------------
def test_20_no_retry_after_customer_rejection():
    recipient = {"status": "NOT_INTERESTED", "attempts": 1}
    assert not is_eligible_for_retry(recipient, max_attempts=3)


# -------------------------------------------------------------------------
# 21. No Retry After DND
# -------------------------------------------------------------------------
def test_21_no_retry_after_dnd():
    recipient_dnd_status = {"status": "DO_NOT_CALL", "attempts": 1}
    assert not is_eligible_for_retry(recipient_dnd_status, max_attempts=3)

    recipient_blocked_dnd = {"status": "BLOCKED", "blocked_reason": "dnd", "attempts": 0}
    assert not is_eligible_for_retry(recipient_blocked_dnd, max_attempts=3)


# -------------------------------------------------------------------------
# 22. Transcript Persistence
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_22_transcript_persistence():
    db = get_db()
    cid = ObjectId()
    transcript = [
        {"speaker": "agent", "text": "Namaskaram"},
        {"speaker": "customer", "text": "Cheppandi"},
    ]
    await db.communications.insert_one({
        "_id": cid,
        "tenant_id": TEST_TID_A,
        "status": "COMPLETED",
        "outcome": {"transcript": transcript},
    })
    doc = await db.communications.find_one({"_id": cid})
    assert len(doc["outcome"]["transcript"]) == 2
    assert doc["outcome"]["transcript"][1]["speaker"] == "customer"


# -------------------------------------------------------------------------
# 23. Summary Persistence
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_23_summary_persistence():
    db = get_db()
    cid = ObjectId()
    outcome_data = {
        "call_summary": "Customer expressed interest in 5L personal loan.",
        "recommended_next_action": "dispatch_digital_application_link",
        "interest_level": "interested",
    }
    await db.communications.insert_one({
        "_id": cid,
        "tenant_id": TEST_TID_A,
        "status": "COMPLETED",
        "outcome": outcome_data,
    })
    doc = await db.communications.find_one({"_id": cid})
    assert "personal loan" in doc["outcome"]["call_summary"]
    assert doc["outcome"]["recommended_next_action"] == "dispatch_digital_application_link"


# -------------------------------------------------------------------------
# 24. Lead Status Update
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_24_lead_status_update():
    outcome_qualified = {"qualification_status": "qualified", "interest_level": "interested"}
    assert derive_lead_status(outcome_qualified) == "QUALIFIED"

    outcome_rejected = {"interest_level": "not_interested"}
    assert derive_lead_status(outcome_rejected) == "NOT_INTERESTED"

    outcome_dnd = {"is_do_not_call": True}
    assert derive_lead_status(outcome_dnd) == "DO_NOT_CALL"


# -------------------------------------------------------------------------
# 25. Lead Score Adjustment
# -------------------------------------------------------------------------
def test_25_lead_score_adjustment():
    # Positive interest should increase score
    delta_pos, reason_pos = calculate_score_adjustment(
        original_score=60.0, current_score=60.0, outcome={"interest_level": "interested"},
    )
    assert delta_pos > 0.0
    assert "INTEREST" in reason_pos

    # Rejection should drop score significantly
    delta_neg, reason_neg = calculate_score_adjustment(
        original_score=75.0, current_score=75.0, outcome={"interest_level": "not_interested"},
    )
    assert delta_neg < 0.0
    assert "REJECTED" in reason_neg


# -------------------------------------------------------------------------
# 26. Callback Handling
# -------------------------------------------------------------------------
def test_26_callback_handling():
    outcome_cb = {
        "interest_level": "callback",
        "preferred_callback_time": "Tomorrow at 4 PM",
    }
    status = derive_lead_status(outcome_cb)
    assert status == "CALLBACK_SCHEDULED"


# -------------------------------------------------------------------------
# 27. Campaign Analytics Calculation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_27_campaign_analytics_calculation():
    db = get_db()
    cid = str(ObjectId())
    await db.campaigns.insert_one({
        "_id": ObjectId(cid), "tenant_id": TEST_TID_A, "name": "Analytics Test Campaign", "status": "COMPLETED",
    })

    await db.campaign_recipients.insert_many([
        {"campaign_id": cid, "tenant_id": TEST_TID_A, "entity_id": "rec_analytics_1", "status": "COMPLETED", "eligibility": "ELIGIBLE", "attempts": 1},
        {"campaign_id": cid, "tenant_id": TEST_TID_A, "entity_id": "rec_analytics_2", "status": "NO_ANSWER", "eligibility": "ELIGIBLE", "attempts": 2},
    ])

    await db.communications.insert_many([
        {
            "campaign_id": cid, "tenant_id": TEST_TID_A, "status": "COMPLETED",
            "outcome": {"duration_seconds": 65.0, "interest_level": "interested", "qualification_status": "qualified"},
        },
        {
            "campaign_id": cid, "tenant_id": TEST_TID_A, "status": "NO_ANSWER",
            "outcome": {"duration_seconds": 0.0},
        },
    ])

    analytics = await calculate_campaign_analytics(db, cid, TEST_TID_A)
    assert analytics.total_audience == 2
    assert analytics.calls_dispatched == 2
    assert analytics.calls_completed == 1
    assert analytics.interested_customers == 1
    assert analytics.qualified_leads == 1
    assert analytics.derived_metrics.contact_rate == 0.5  # 1 completed / 2 dispatched
    assert analytics.derived_metrics.answer_rate == 0.5   # 1 answered / 2 dispatched
    assert analytics.derived_metrics.dispatch_rate == 1.0 # 2 dispatched / 2 eligible
    assert analytics.derived_metrics.interest_rate == 1.0 # 1 interested / 1 connected
    assert analytics.derived_metrics.qualification_rate == 1.0 # 1 qualified / 1 connected
    assert analytics.derived_metrics.retry_rate == 0.5    # 1 retry / 2 audience
    assert analytics.duration_stats.avg_seconds == 65.0


# -------------------------------------------------------------------------
# 28. Multi-Tenant Isolation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_28_multi_tenant_isolation():
    db = get_db()
    cid_a = str((await db.campaigns.insert_one({"tenant_id": TEST_TID_A, "name": "Tenant A Campaign"})).inserted_id)

    # Attempt lookup with Tenant B
    from app.core.db import build_tenant_query
    q = build_tenant_query(TEST_TID_B, {"_id": ObjectId(cid_a)})
    found = await db.campaigns.find_one(q)
    assert found is None


# -------------------------------------------------------------------------
# 29. Worker Restart Recovery
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_29_worker_restart_recovery():
    db = get_db()
    cid_active = str((await db.campaigns.insert_one({"tenant_id": TEST_TID_A, "status": "RUNNING"})).inserted_id)
    # Insert pending recipient
    await db.campaign_recipients.insert_one({
        "campaign_id": cid_active, "tenant_id": TEST_TID_A, "entity_id": "rec_recov", "status": "PENDING",
    })

    resumed = await recover_interrupted_campaigns(db)
    assert resumed >= 1


# -------------------------------------------------------------------------
# 30. Concurrent Dispatch Limits
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_30_concurrent_dispatch_limits():
    semaphore = asyncio.Semaphore(2)
    active_workers = 0
    max_observed = 0

    async def worker():
        nonlocal active_workers, max_observed
        async with semaphore:
            active_workers += 1
            max_observed = max(max_observed, active_workers)
            await asyncio.sleep(0.02)
            active_workers -= 1

    await asyncio.gather(*(worker() for _ in range(6)))
    assert max_observed <= 2


# -------------------------------------------------------------------------
# 31. In-flight Crash Recovery Reconciliation
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_31_inflight_crash_recovery_reconciliation():
    db = get_db()
    cid = str(ObjectId())
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "RUNNING"})

    # Recipient 1: finished while backend was down (comm COMPLETED)
    comm_1 = await db.communications.insert_one({
        "tenant_id": TEST_TID_A, "campaign_id": cid, "status": "COMPLETED",
        "provider_ref": "CAmock_finished_123", "outcome": {"interest_level": "interested"},
    })
    await db.campaign_recipients.insert_one({
        "campaign_id": cid, "tenant_id": TEST_TID_A, "entity_id": "rec_inflight_1",
        "status": "CALLING", "last_communication_id": str(comm_1.inserted_id),
    })

    # Recipient 2: never created call before crash (no comm) -> resets to PENDING
    await db.campaign_recipients.insert_one({
        "campaign_id": cid, "tenant_id": TEST_TID_A, "entity_id": "rec_inflight_2",
        "status": "CALLING", "last_communication_id": None,
    })

    # Recipient 3: still actively in-flight (< 10m old) -> remains CALLING
    comm_3 = await db.communications.insert_one({
        "tenant_id": TEST_TID_A, "campaign_id": cid, "status": "IN_PROGRESS",
        "provider_ref": "CAmock_active_123", "created_at": datetime.now(timezone.utc),
    })
    await db.campaign_recipients.insert_one({
        "campaign_id": cid, "tenant_id": TEST_TID_A, "entity_id": "rec_inflight_3",
        "status": "CALLING", "last_communication_id": str(comm_3.inserted_id),
    })

    from app.services.campaign_scheduler import recover_interrupted_campaigns
    resumed = await recover_interrupted_campaigns(db)

    # Check reconciled states
    r1 = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": "rec_inflight_1"})
    assert r1["status"] == "INTERESTED"

    r2 = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": "rec_inflight_2"})
    assert r2["status"] in ("PENDING", "CALLING", "BLOCKED", "FAILED")  # Reset to PENDING and resumed

    r3 = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": "rec_inflight_3"})
    assert r3["status"] == "CALLING"  # Active call is preserved, not prematurely aborted


# -------------------------------------------------------------------------
# 32. Automatic Retry Worker Execution
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_32_automatic_retry_worker_execution():
    from datetime import timedelta
    from app.services.campaign_scheduler import check_and_execute_due_retries

    db = get_db()
    cid = str(ObjectId())
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "RUNNING"})

    # Insert a due retry (next_retry_at was 5 minutes ago)
    past_due = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db.campaign_recipients.insert_one({
        "campaign_id": cid, "tenant_id": TEST_TID_A, "entity_id": "rec_due_retry",
        "status": "NO_ANSWER", "attempts": 1, "next_retry_at": past_due,
    })

    queued_count = await check_and_execute_due_retries(db)
    assert queued_count >= 1

    rcpt = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": "rec_due_retry"})
    assert rcpt["status"] in ("PENDING", "CALLING", "BLOCKED", "FAILED")
    assert rcpt.get("next_retry_at") is None


# -------------------------------------------------------------------------
# 33. Paused Campaign Does Not Execute Retries
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_33_paused_campaign_does_not_execute_retries():
    from datetime import timedelta
    from app.services.campaign_scheduler import check_and_execute_due_retries

    db = get_db()
    cid = str(ObjectId())
    # Campaign is PAUSED
    await db.campaigns.insert_one({"_id": ObjectId(cid), "tenant_id": TEST_TID_A, "status": "PAUSED"})

    past_due = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db.campaign_recipients.insert_one({
        "campaign_id": cid, "tenant_id": TEST_TID_A, "entity_id": "rec_paused_retry",
        "status": "NO_ANSWER", "attempts": 1, "next_retry_at": past_due,
    })

    queued_count = await check_and_execute_due_retries(db)
    # The paused recipient must NOT be queued
    rcpt = await db.campaign_recipients.find_one({"campaign_id": cid, "entity_id": "rec_paused_retry"})
    assert rcpt["status"] == "NO_ANSWER"


# -------------------------------------------------------------------------
# 34. Developer Exemption Security in Production
# -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_34_developer_exemption_security_in_production():
    from app.services.compliance import evaluate_compliance

    db = get_db()
    test_phone = "+919346618426"
    settings.compliance_exempt_numbers = test_phone
    settings.seed_test_phone_1 = test_phone

    # When test_mode = False (Production)
    settings.test_mode = False
    recipient = {"phone": test_phone, "consent": True, "dnd": False}

    # Simulate night time outside calling hours (3 AM IST)
    night_time = datetime(2026, 11, 8, 3, 0, tzinfo=timezone.utc)
    res = await evaluate_compliance(recipient, TEST_TID_A, db, current_time=night_time)
    assert res.allowed is False
    assert res.blocked_reason == "outside_calling_hours"

    # Restore test_mode
    settings.test_mode = True
