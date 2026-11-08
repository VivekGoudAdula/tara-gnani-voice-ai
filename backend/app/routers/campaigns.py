"""Campaign management router for CRUD, audience selection, voice configs, and execution."""

from datetime import datetime, timezone
import math
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from app.core.config import settings
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import get_current_user, require_roles
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.campaigns import (
    AudiencePreviewResponse, AudienceSetRequest, CampaignAnalyticsResponse, CampaignCreate,
    CampaignDetail, CampaignLaunchRequest, CampaignLaunchResponse, CampaignListItem,
    CampaignPreviewRequest, CampaignPreviewResponse, CampaignProgress, CampaignRecipientItem,
    CampaignRetriesResponse, CampaignScheduleRequest, CampaignUpdate, CampaignValidationResponse,
    RecipientScenarioUpdate,
)
from app.schemas.communication import CommunicationDetail
from app.services.campaign_analytics import calculate_campaign_analytics
from app.services.campaign_audience import get_audience_preview, preview_blocked_reason, set_campaign_audience
from app.services.campaign_configs import DEFAULT_VOICE_CONFIG, get_campaign_configs, save_campaign_config
from app.services.campaign_execution import execute_campaign_dispatch, refresh_recipient_statuses
from app.services.campaign_retry import get_campaign_retry_queue, queue_campaign_retries
from app.services.campaign_scheduler import schedule_campaign
from app.services.campaign_validation import validate_campaign_readiness
from app.services.campaign_variables import map_campaign_voice_variables, validate_voice_config
from app.services.campaigns import get_campaign_progress, run_campaign_dispatch
from app.services.compliance import is_fake_seeded_number

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


async def resolve_campaign(db: Any, tid: str, cid: str) -> dict[str, Any]:
    """Fetch campaign strictly scoped to tenant."""
    if not ObjectId.is_valid(cid):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    camp = await db.campaigns.find_one(build_tenant_query(tid, {"_id": ObjectId(cid)}))
    if not camp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return camp


@router.post("", response_model=CampaignDetail, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    req: CampaignCreate, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> CampaignDetail:
    """Create a new campaign in DRAFT status with initial default voice config."""
    db, tid, uid = get_db(), user["tenant_id"], user["user_id"]
    prod = await db.products.find_one(build_tenant_query(tid, {"_id": ObjectId(req.product_id) if ObjectId.is_valid(req.product_id) else req.product_id}))
    if not prod:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected product not found")

    now_utc = datetime.now(timezone.utc)
    doc = {
        "tenant_id": tid, "name": req.name.strip(), "description": req.description,
        "product_id": str(prod["_id"]), "product_name": prod.get("name", "Product"),
        "entity_type": req.entity_type, "objective": req.objective.strip(), "status": "DRAFT",
        "channels": ["voice"], "audience_filter": {}, "include_not_eligible": False,
        "scoring_run_id": None, "config_version": 1, "created_by": uid, "created_at": now_utc,
        "updated_at": now_utc, "launched_at": None, "completed_at": None,
        "test_run_label": req.test_run_label.strip() if req.test_run_label else None,
    }
    cid = str((await db.campaigns.insert_one(doc)).inserted_id)
    doc["_id"] = ObjectId(cid)

    # Seed default voice config version 1
    await save_campaign_config(db, cid, tid, "voice", DEFAULT_VOICE_CONFIG, uid)
    await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "campaign_created", "entity_type": "campaign", "entity_id": cid, "at": now_utc})
    return CampaignDetail(**doc_to_dict(doc), current_voice_config=DEFAULT_VOICE_CONFIG)


@router.get("", response_model=PaginatedResponse[CampaignListItem])
async def list_campaigns(
    status_filter: str | None = Query(None, alias="status"), page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100), user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[CampaignListItem]:
    """List tenant campaigns with progress metrics."""
    db, tid = get_db(), user["tenant_id"]
    crit: dict[str, Any] = {}
    if status_filter:
        crit["status"] = status_filter.upper().strip()
    query = build_tenant_query(tid, crit)

    total = await db.campaigns.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    cursor = db.campaigns.find(query).sort("updated_at", -1).skip((page - 1) * page_size).limit(page_size)

    items: list[CampaignListItem] = []
    async for c in cursor:
        cid = str(c["_id"])
        rc_cursor = db.campaign_recipients.aggregate([
            {"$match": {"campaign_id": cid}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ])
        counts: dict[str, int] = {}
        async for r in rc_cursor:
            counts[r["_id"]] = r["count"]
        tot_rcpt = sum(counts.values())
        contacted = counts.get("CONTACTED", 0) + counts.get("INTERESTED", 0) + counts.get("CALLBACK", 0) + counts.get("NOT_INTERESTED", 0)
        items.append(CampaignListItem(
            id=cid, name=c["name"], product_id=c["product_id"], product_name=c.get("product_name", "Product"),
            entity_type=c["entity_type"], status=c["status"], test_run_label=c.get("test_run_label"), total_recipients=tot_rcpt,
            contacted_count=contacted, recipient_counts=counts, updated_at=c["updated_at"], created_at=c["created_at"],
        ))

    return PaginatedResponse(items=items, pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages))


@router.get("/{id}", response_model=CampaignDetail)
async def get_campaign(id: str, user: dict[str, Any] = Depends(get_current_user)) -> CampaignDetail:
    """Retrieve full campaign detail including active voice configuration."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    v_cfg = await db.campaign_configs.find_one({"campaign_id": id, "channel": "voice", "version": camp.get("config_version", 1)})
    progress = await get_campaign_progress(db, id, tid)
    return CampaignDetail(**doc_to_dict(camp), current_voice_config=v_cfg.get("config") if v_cfg else None, recipient_counts=progress["counts_by_status"])


@router.put("/{id}", response_model=CampaignDetail)
async def update_campaign(
    id: str, req: CampaignUpdate, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> CampaignDetail:
    """Update basic campaign settings (DRAFT/READY only)."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") not in ("DRAFT", "READY"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only DRAFT or READY campaigns can be modified")

    updates: dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if req.name is not None: updates["name"] = req.name.strip()
    if req.description is not None: updates["description"] = req.description
    if req.objective is not None: updates["objective"] = req.objective.strip()
    if req.entity_type is not None: updates["entity_type"] = req.entity_type
    if req.test_run_label is not None: updates["test_run_label"] = req.test_run_label.strip() if req.test_run_label else None
    if req.product_id is not None:
        prod = await db.products.find_one(build_tenant_query(tid, {"_id": ObjectId(req.product_id) if ObjectId.is_valid(req.product_id) else req.product_id}))
        if not prod: raise HTTPException(status.HTTP_400_BAD_REQUEST, "Selected product not found")
        updates["product_id"] = str(prod["_id"])
        updates["product_name"] = prod.get("name", "Product")

    await db.campaigns.update_one({"_id": ObjectId(id)}, {"$set": updates})
    return await get_campaign(id, user)


@router.delete("/{id}")
async def delete_campaign(id: str, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"]))) -> dict[str, str]:
    """Soft delete campaign by setting status=CANCELLED (DRAFT/READY only)."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") not in ("DRAFT", "READY"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only DRAFT or READY campaigns can be cancelled/deleted")
    await db.campaigns.update_one({"_id": ObjectId(id)}, {"$set": {"status": "CANCELLED", "updated_at": datetime.now(timezone.utc)}})
    return {"message": "Campaign cancelled successfully"}


@router.get("/{id}/audience/preview", response_model=AudiencePreviewResponse)
async def preview_audience(
    id: str, band: list[str] = Query(None), eligibility: str | None = Query(None),
    min_score: float | None = Query(None), max_score: float | None = Query(None),
    search: str | None = Query(None), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> AudiencePreviewResponse:
    """Pre-flight candidate audience matching and compliance preview."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    return await get_audience_preview(db, camp, band, eligibility, min_score, max_score, search, page, page_size)


@router.put("/{id}/audience")
async def update_audience(
    id: str, req: AudienceSetRequest, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, Any]:
    """Set campaign recipient audience with snapshotting."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") not in ("DRAFT", "READY"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audience can only be modified in DRAFT or READY status")
    return await set_campaign_audience(db, camp, req, user)


@router.get("/{id}/recipients", response_model=PaginatedResponse[CampaignRecipientItem])
async def list_recipients(
    id: str, status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[CampaignRecipientItem]:
    """List recipients inside a campaign with refreshed statuses and live entity names."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    await get_campaign_progress(db, id, tid)

    crit: dict[str, Any] = {"campaign_id": id, "tenant_id": tid}
    if status_filter and isinstance(status_filter, str):
        crit["status"] = status_filter.upper().strip()

    cursor = db.campaign_recipients.find(crit)
    raw_docs = await cursor.to_list(length=1000)

    # Batch resolve live entity info so if anything changes in leads/customers, it updates here immediately
    coll = db.leads if camp.get("entity_type") == "lead" else db.customers
    eids = [doc["entity_id"] for doc in raw_docs]
    id_objs = [ObjectId(e) if ObjectId.is_valid(e) else e for e in eids]
    ent_map = {str(e["_id"]): e async for e in coll.find(build_tenant_query(tid, {"_id": {"$in": id_objs}}))}

    for doc in raw_docs:
        ent = ent_map.get(doc["entity_id"])
        if ent:
            doc["name"] = ent.get("name", doc.get("name"))
            doc["language"] = ent.get("language", doc.get("language"))

    # Sort dialable unblocked recipients first, then by match score descending
    def sort_key(doc: dict[str, Any]) -> tuple[int, float]:
        ent = ent_map.get(doc["entity_id"], {})
        phone = (ent.get("phone") or "").strip()
        is_dialable = 0 if (phone and not is_fake_seeded_number(phone) and ent.get("consent") is True and not ent.get("dnd")) else 1
        return (is_dialable, -float(doc.get("match_score", 0.0)))

    raw_docs.sort(key=sort_key)

    total = len(raw_docs)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    start_idx = (page - 1) * page_size
    paged_docs = raw_docs[start_idx : start_idx + page_size]

    items = [CampaignRecipientItem(**doc_to_dict(doc)) for doc in paged_docs]
    return PaginatedResponse(items=items, pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages))


@router.delete("/{id}/recipients/{entity_id}")
async def remove_recipient(
    id: str, entity_id: str, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, str]:
    """Remove a single recipient from a DRAFT, READY, or PAUSED campaign."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") not in ("DRAFT", "READY", "PAUSED"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove recipients in current campaign status")
    res = await db.campaign_recipients.delete_one({"campaign_id": id, "entity_id": entity_id})
    if res.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found in campaign")
    return {"message": "Recipient removed successfully"}


@router.patch("/{id}/recipients/{entity_id}/scenario")
async def update_recipient_scenario(
    id: str, entity_id: str, req: RecipientScenarioUpdate, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, Any]:
    """Assign or update a tester scenario note for a recipient (DRAFT or READY campaigns only)."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") not in ("DRAFT", "READY"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tester scenario can only be modified for DRAFT or READY campaigns")
    res = await db.campaign_recipients.update_one(
        {"campaign_id": id, "tenant_id": tid, "entity_id": entity_id},
        {"$set": {"tester_scenario": req.tester_scenario, "updated_at": datetime.now(timezone.utc)}},
    )
    if res.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found in campaign")
    return {"message": "Tester scenario updated", "tester_scenario": req.tester_scenario}


@router.put("/{id}/config/{channel}")
async def put_channel_config(
    id: str, channel: str, body: dict[str, Any], user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, Any]:
    """Save a new versioned configuration for a specific channel."""
    db, tid = get_db(), user["tenant_id"]
    await resolve_campaign(db, tid, id)
    return await save_campaign_config(db, id, tid, channel, body, user["user_id"])


@router.get("/{id}/config/{channel}/versions")
async def list_config_versions(
    id: str, channel: str, user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List historical configuration versions for a channel."""
    db, tid = get_db(), user["tenant_id"]
    await resolve_campaign(db, tid, id)
    return await get_campaign_configs(db, id, channel)


@router.post("/{id}/preview", response_model=CampaignPreviewResponse)
async def preview_campaign_call(
    id: str, req: CampaignPreviewRequest, user: dict[str, Any] = Depends(get_current_user),
) -> CampaignPreviewResponse:
    """Non-dispatch render preview showing exact variables sent to voice provider."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    v_doc = await db.campaign_configs.find_one({"campaign_id": id, "channel": "voice", "version": camp.get("config_version", 1)})
    cfg = v_doc.get("config", {}) if v_doc else DEFAULT_VOICE_CONFIG
    errors = validate_voice_config(cfg)

    # Resolve sample recipient
    rcpt: dict[str, Any] = {}
    coll = db.leads if camp["entity_type"] == "lead" else db.customers
    if req.entity_id:
        doc = await coll.find_one(build_tenant_query(tid, {"_id": ObjectId(req.entity_id) if ObjectId.is_valid(req.entity_id) else req.entity_id}))
        if doc: rcpt = doc_to_dict(doc)
    if not rcpt:
        first_r = await db.campaign_recipients.find_one({"campaign_id": id})
        if first_r:
            doc = await coll.find_one(build_tenant_query(tid, {"_id": ObjectId(first_r["entity_id"]) if ObjectId.is_valid(first_r["entity_id"]) else first_r["entity_id"]}))
            if doc: rcpt = doc_to_dict(doc)
    if not rcpt:
        rcpt = {"name": "Aarav Sharma", "language": "telugu", "preferred_amount": "500000"}

    vars_map = map_campaign_voice_variables(cfg, rcpt, camp.get("product_name", "Loan"), user.get("tenant_name", "Test Bank"))
    return CampaignPreviewResponse(
        rendered_opening_message=vars_map.get("opening_message", ""), user_data_variables=vars_map,
        config_version=camp.get("config_version", 1), validation_report={"valid": len(errors) == 0, "errors": errors},
    )


@router.post("/{id}/validate", response_model=CampaignValidationResponse)
async def validate_campaign(
    id: str,
    user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> CampaignValidationResponse:
    """Pre-flight check verifying audience, voice config, and regulatory readiness."""
    db, tid = get_db(), user["tenant_id"]
    await resolve_campaign(db, tid, id)
    return await validate_campaign_readiness(db, id, tid)


@router.post("/{id}/schedule")
async def schedule_campaign_endpoint(
    id: str,
    req: CampaignScheduleRequest,
    user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, Any]:
    """Schedule campaign for future timezone-aware execution."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") not in ("DRAFT", "READY", "PAUSED"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot schedule campaign in {camp.get('status')} status")

    rcpt_count = await db.campaign_recipients.count_documents({"campaign_id": id, "tenant_id": tid})
    if rcpt_count == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot schedule a campaign with zero recipients")

    try:
        return await schedule_campaign(
            db=db,
            campaign_id=id,
            tenant_id=tid,
            scheduled_start_time=req.scheduled_start_time,
            timezone_str=req.timezone,
            user=user,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{id}/launch", response_model=CampaignLaunchResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/{id}/start", response_model=CampaignLaunchResponse, status_code=status.HTTP_202_ACCEPTED)
async def launch_campaign(
    id: str, req: CampaignLaunchRequest, bg_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> CampaignLaunchResponse:
    """Validate and trigger paced outbound dispatch as an asynchronous background execution."""
    db, tid, uid = get_db(), user["tenant_id"], user["user_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") not in ("DRAFT", "READY", "PAUSED", "SCHEDULED"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Cannot launch campaign in {camp.get('status')} status")

    # 1. Pre-condition validations
    rcpt_count = await db.campaign_recipients.count_documents({"campaign_id": id, "tenant_id": tid})
    if rcpt_count == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Campaign has no recipients selected")

    prod = await db.products.find_one(build_tenant_query(tid, {"_id": ObjectId(camp["product_id"]) if ObjectId.is_valid(camp["product_id"]) else camp["product_id"]}))
    if not prod or not prod.get("active", True):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Associated product is inactive or missing")

    v_doc = await db.campaign_configs.find_one({"campaign_id": id, "channel": "voice", "version": camp.get("config_version", 1)})
    cfg = v_doc.get("config", {}) if v_doc else {}
    errs = validate_voice_config(cfg)
    if errs:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"message": "Voice configuration invalid", "errors": errs})

    missing_env = []
    # TARA 2.0: Twilio + Gnani Voice Pipeline
    if not settings.test_mode:
        if not settings.twilio_account_sid: missing_env.append("TWILIO_ACCOUNT_SID")
        if not settings.twilio_auth_token: missing_env.append("TWILIO_AUTH_TOKEN")
        if not settings.twilio_from_number: missing_env.append("TWILIO_FROM_NUMBER")
    if missing_env:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Missing voice configuration: {', '.join(missing_env)}")

    # 2. Safety confirmation checks
    if not req.confirm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Launch confirmation required")
    if req.expected_recipient_count != rcpt_count:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Recipient count mismatch: expected {req.expected_recipient_count}, found {rcpt_count}")

    now_utc = datetime.now(timezone.utc)
    await db.campaigns.update_one({"_id": ObjectId(id)}, {"$set": {"status": "LAUNCHING", "launched_at": now_utc, "updated_at": now_utc}})
    await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "launched", "entity_type": "campaign", "entity_id": id, "at": now_utc})

    # Estimate test mode blocked recipients
    blocked_estimate = 0
    if settings.test_mode:
        allowlist = {num.strip() for num in settings.test_allowlist.split(",") if num.strip()}
        coll = db.leads if camp["entity_type"] == "lead" else db.customers
        async for r in db.campaign_recipients.find({"campaign_id": id}):
            ent = await coll.find_one({"_id": ObjectId(r["entity_id"]) if ObjectId.is_valid(r["entity_id"]) else r["entity_id"]})
            if ent and preview_blocked_reason(ent, True, allowlist):
                blocked_estimate += 1

    bg_tasks.add_task(execute_campaign_dispatch, db, id, tid, user)

    notice = "TEST MODE: only allowlisted numbers will be called" if settings.test_mode else None
    return CampaignLaunchResponse(
        message="Campaign outreach initiated", campaign_id=id, status="LAUNCHING",
        recipient_count=rcpt_count, test_mode=settings.test_mode, notice=notice, blocked_estimate=blocked_estimate,
    )


@router.post("/{id}/pause")
async def pause_campaign(id: str, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"]))) -> dict[str, str]:
    """Pause campaign outreach."""
    db, tid, uid = get_db(), user["tenant_id"], user["user_id"]
    await resolve_campaign(db, tid, id)
    now_utc = datetime.now(timezone.utc)
    await db.campaigns.update_one({"_id": ObjectId(id)}, {"$set": {"status": "PAUSED", "updated_at": now_utc}})
    await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "paused", "entity_type": "campaign", "entity_id": id, "at": now_utc})
    return {"message": "Campaign paused successfully"}


@router.post("/{id}/resume")
async def resume_campaign(
    id: str, bg_tasks: BackgroundTasks, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"])),
) -> dict[str, str]:
    """Resume paused campaign outreach."""
    db, tid, uid = get_db(), user["tenant_id"], user["user_id"]
    camp = await resolve_campaign(db, tid, id)
    if camp.get("status") != "PAUSED":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PAUSED campaigns can be resumed")
    now_utc = datetime.now(timezone.utc)
    await db.campaigns.update_one({"_id": ObjectId(id)}, {"$set": {"status": "LAUNCHING", "updated_at": now_utc}})
    await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "resumed", "entity_type": "campaign", "entity_id": id, "at": now_utc})
    bg_tasks.add_task(execute_campaign_dispatch, db, id, tid, user)
    return {"message": "Campaign resumed successfully"}


@router.post("/{id}/cancel")
async def cancel_campaign(id: str, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"]))) -> dict[str, str]:
    """Permanently cancel campaign outreach."""
    db, tid, uid = get_db(), user["tenant_id"], user["user_id"]
    await resolve_campaign(db, tid, id)
    now_utc = datetime.now(timezone.utc)
    await db.campaigns.update_one({"_id": ObjectId(id)}, {"$set": {"status": "CANCELLED", "updated_at": now_utc}})
    await db.audit_log.insert_one({"tenant_id": tid, "actor_user_id": uid, "action": "cancelled", "entity_type": "campaign", "entity_id": id, "at": now_utc})
    return {"message": "Campaign cancelled"}


@router.post("/{id}/retry")
async def retry_campaign(id: str, user: dict[str, Any] = Depends(require_roles(["SUPER_ADMIN", "EMPLOYEE"]))) -> dict[str, Any]:
    """Manual retry: resets eligible transient failures (NO_ANSWER, BUSY) up to max_attempts."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    v_doc = await db.campaign_configs.find_one({"campaign_id": id, "channel": "voice", "version": camp.get("config_version", 1)})
    cfg = v_doc.get("config", {}) if v_doc else {}
    max_att = (cfg.get("retry_policy") or {}).get("max_attempts", 2)

    retried_count = await queue_campaign_retries(db, id, tid, max_att)
    if retried_count > 0 and camp.get("status") in ("COMPLETED", "PAUSED"):
        await db.campaigns.update_one({"_id": ObjectId(id)}, {"$set": {"status": "READY", "updated_at": datetime.now(timezone.utc)}})
    return {"message": f"Queued {retried_count} recipients for retry", "retried_count": retried_count}


@router.get("/{id}/progress", response_model=CampaignProgress)
async def progress_campaign(id: str, user: dict[str, Any] = Depends(get_current_user)) -> CampaignProgress:
    """Retrieve live campaign progress and recipient breakdown."""
    db, tid = get_db(), user["tenant_id"]
    await resolve_campaign(db, tid, id)
    data = await get_campaign_progress(db, id, tid)
    return CampaignProgress(**data)


@router.get("/{id}/analytics", response_model=CampaignAnalyticsResponse)
async def get_campaign_analytics_endpoint(
    id: str, user: dict[str, Any] = Depends(get_current_user),
) -> CampaignAnalyticsResponse:
    """Retrieve verified campaign analytics, conversion ratios, and duration metrics."""
    db, tid = get_db(), user["tenant_id"]
    await resolve_campaign(db, tid, id)
    return await calculate_campaign_analytics(db, id, tid)


@router.get("/{id}/retries", response_model=CampaignRetriesResponse)
async def get_campaign_retries_endpoint(
    id: str, user: dict[str, Any] = Depends(get_current_user),
) -> CampaignRetriesResponse:
    """Inspect retry queue, attempt counters, and failure reasons."""
    db, tid = get_db(), user["tenant_id"]
    camp = await resolve_campaign(db, tid, id)
    v_doc = await db.campaign_configs.find_one({"campaign_id": id, "channel": "voice", "version": camp.get("config_version", 1)})
    cfg = v_doc.get("config", {}) if v_doc else {}
    max_att = (cfg.get("retry_policy") or {}).get("max_attempts", 2)
    interval = (cfg.get("retry_policy") or {}).get("interval_minutes", 60)
    return await get_campaign_retry_queue(db, id, tid, max_attempts=max_att, base_interval_minutes=interval)


@router.get("/{id}/calls", response_model=PaginatedResponse[CommunicationDetail])
async def list_campaign_calls(
    id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(get_current_user),
) -> PaginatedResponse[CommunicationDetail]:
    """List communication logs and transcripts strictly associated with this campaign."""
    db, tid = get_db(), user["tenant_id"]
    await resolve_campaign(db, tid, id)
    query = build_tenant_query(tid, {"campaign_id": id})
    total = await db.communications.count_documents(query)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    cursor = db.communications.find(query).sort("created_at", -1).skip((page - 1) * page_size).limit(page_size)
    items = [CommunicationDetail(**doc_to_dict(c)) async for c in cursor]
    return PaginatedResponse(items=items, pagination=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages))

