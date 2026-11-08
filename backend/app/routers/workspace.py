"""Workspace router for tenant-level administrative operations."""

import logging
from typing import Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.db import build_tenant_query, doc_to_dict, get_db
from app.core.deps import get_current_user, require_role
from app.core.sample_data import generate_sample_customers, generate_sample_leads, get_default_products

logger = logging.getLogger("tara.workspace")
router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.post("/sample-data", status_code=status.HTTP_201_CREATED)
async def load_sample_data(
    current_user: dict[str, Any] = Depends(require_role("SUPER_ADMIN")),
) -> dict[str, Any]:
    """
    Populate caller's tenant with sample products, leads, and customers.
    Restricted to SUPER_ADMIN. Idempotent: returns 409 if data already exists.
    """
    db = get_db()
    tenant_id = current_user["tenant_id"]

    # Check if tenant already has leads or customers
    tenant_query = build_tenant_query(tenant_id)
    existing_leads = await db.leads.count_documents(tenant_query)
    existing_customers = await db.customers.count_documents(tenant_query)

    if existing_leads > 0 or existing_customers > 0:
        logger.warning("Sample data load rejected: workspace %s already has records", tenant_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sample data already loaded for this workspace",
        )

    # 1. Insert 3 default products
    products = get_default_products(tenant_id)
    if products:
        await db.products.insert_many(products)

    # 2. Insert 40 sample leads
    leads = generate_sample_leads(tenant_id, count=40)
    if leads:
        await db.leads.insert_many(leads)

    # 3. Insert 20 sample customers
    customers = generate_sample_customers(tenant_id, count=20)
    if customers:
        await db.customers.insert_many(customers)

    logger.info(
        "Loaded sample data for tenant %s: %d products, %d leads, %d customers",
        tenant_id,
        len(products),
        len(leads),
        len(customers),
    )
    return {
        "status": "success",
        "message": "Sample data loaded successfully",
        "counts": {
            "products": len(products),
            "leads": len(leads),
            "customers": len(customers),
        },
    }


@router.get("/dashboard")
async def get_dashboard_summary(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve getting-started checklist, summary metrics, and recent audit activity from real DB data."""
    db = get_db()
    tenant_id = current_user["tenant_id"]
    t_query = build_tenant_query(tenant_id)

    # 1. Real entity counts
    leads_count = await db.leads.count_documents(t_query)
    customers_count = await db.customers.count_documents(t_query)
    products_count = await db.products.count_documents(t_query)
    active_products = await db.products.count_documents(build_tenant_query(tenant_id, {"active": True}))

    # 2. Last scoring run
    last_run_doc = await db.scoring_runs.find_one(t_query, sort=[("created_at", -1)])
    is_stale = False
    last_run_time = None
    if last_run_doc:
        last_run_time = last_run_doc.get("created_at")
        # Check if new leads/customers or updated products exist after last scoring run
        new_leads = await db.leads.count_documents(build_tenant_query(tenant_id, {"created_at": {"$gt": last_run_time}}))
        new_customers = await db.customers.count_documents(build_tenant_query(tenant_id, {"created_at": {"$gt": last_run_time}}))
        is_stale = (new_leads > 0 or new_customers > 0)
        last_run_time = last_run_time.isoformat() if hasattr(last_run_time, "isoformat") else str(last_run_time)

    # 3. Campaigns counts by status
    campaign_cursor = db.campaigns.aggregate([
        {"$match": t_query},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ])
    campaign_status_counts: dict[str, int] = {}
    total_campaigns = 0
    active_campaigns = 0
    async for row in campaign_cursor:
        status_name = row["_id"] or "DRAFT"
        cnt = row["count"]
        campaign_status_counts[status_name] = cnt
        total_campaigns += cnt
        if status_name in ("ACTIVE", "LAUNCHING"):
            active_campaigns += cnt

    # 4. Communications and outcomes summary (all time)
    calls_attempted = await db.communications.count_documents(t_query)
    calls_completed = await db.communications.count_documents(build_tenant_query(tenant_id, {"status": {"$in": ["completed", "answered", "success"]}}))
    calls_interested = await db.communications.count_documents(build_tenant_query(tenant_id, {"interest_level": "INTERESTED"}))
    compliance_blocked = await db.communications.count_documents(build_tenant_query(tenant_id, {"status": "blocked"}))

    # 5. Checklist computation
    step1_done = (leads_count + customers_count) > 0
    step2_done = products_count > 0
    step3_done = bool(last_run_doc and not is_stale)
    step4_done = total_campaigns > 0
    step5_done = calls_completed > 0

    checklist = [
        {
            "step": 1,
            "title": "Data loaded",
            "state": "done" if step1_done else "next",
            "detail": f"{leads_count} leads, {customers_count} customers in registry" if step1_done else "Upload a CSV file or load sample bank portfolio",
            "counts": {"leads": leads_count, "customers": customers_count},
            "link": "/app/data-import",
            "action_label": "Import Data" if not step1_done else "Manage Data",
        },
        {
            "step": 2,
            "title": "Products configured",
            "state": "done" if step2_done else ("next" if step1_done else "blocked"),
            "detail": f"{products_count} product(s) configured ({active_products} active)" if step2_done else "Define financial products and eligibility rules",
            "counts": {"total": products_count, "active": active_products},
            "link": "/app/products",
            "action_label": "Configure Products",
        },
        {
            "step": 3,
            "title": "Scoring run",
            "state": "done" if step3_done else ("next" if (step1_done and step2_done) else "blocked"),
            "detail": (f"Last run: {last_run_time[:19].replace('T', ' ')} UTC" + (" (Stale)" if is_stale else "")) if last_run_doc else "Run calibrated ML scoring & eligibility matching",
            "last_run_at": last_run_time,
            "is_stale": is_stale,
            "link": "/app/matches",
            "action_label": "Run Scoring",
        },
        {
            "step": 4,
            "title": "Campaign created & launched",
            "state": "done" if step4_done else ("next" if step3_done else "blocked"),
            "detail": f"{total_campaigns} campaign(s) created ({active_campaigns} active)" if step4_done else "Create an audience, configure voice agent, and preview",
            "counts": {"total": total_campaigns, "active": active_campaigns},
            "link": "/app/campaigns",
            "action_label": "New Campaign",
        },
        {
            "step": 5,
            "title": "Outcomes captured",
            "state": "done" if step5_done else ("next" if step4_done else "blocked"),
            "detail": f"{calls_completed} completed calls recorded ({calls_interested} interested)" if step5_done else "Monitor live calls and collect structured interaction history",
            "counts": {"completed": calls_completed, "interested": calls_interested},
            "link": "/app/outcomes",
            "action_label": "View Outcomes",
        },
    ]

    # 6. Recent activity from audit_log (last 10)
    audit_cursor = db.audit_log.find(t_query).sort("at", -1).limit(10)
    recent_activity = []
    async for a in audit_cursor:
        doc_dict = doc_to_dict(a)
        if "at" in doc_dict and hasattr(doc_dict["at"], "isoformat"):
            doc_dict["at"] = doc_dict["at"].isoformat()
        recent_activity.append(doc_dict)

    return {
        "checklist": checklist,
        "summary": {
            "leads": leads_count,
            "customers": customers_count,
            "products": products_count,
            "active_products": active_products,
            "last_scoring_run": {
                "last_run_at": last_run_time,
                "is_stale": is_stale,
            },
            "campaigns": {
                "total": total_campaigns,
                "active": active_campaigns,
                "by_status": campaign_status_counts,
            },
            "calls": {
                "attempted": calls_attempted,
                "completed": calls_completed,
                "interested": calls_interested,
            },
            "compliance_blocked": compliance_blocked,
        },
        "recent_activity": recent_activity,
    }


@router.get("/providers-health")
async def get_providers_health(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Retrieve verified connectivity and configuration status for Voice AI providers.
    Never exposes raw API keys or secrets.
    """
    from app.core.config import settings

    twilio_configured = bool(
        settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number
    )
    gnani_configured = bool(settings.gnani_api_key)
    groq_configured = bool(settings.groq_api_key)

    masked_sid = (
        (settings.twilio_account_sid[:4] + "••••••••••••••••" + settings.twilio_account_sid[-4:])
        if len(settings.twilio_account_sid) >= 8
        else "Not configured"
    )

    return {
        "twilio": {
            "configured": twilio_configured,
            "status": "CONFIGURED" if twilio_configured else "NOT_CONFIGURED",
            "account_sid_masked": masked_sid,
            "from_number": settings.twilio_from_number or "Not configured",
            "provider_type": "twilio_voice",
            "verification_type": "credential_presence",
        },
        "gnani_prisma": {
            "configured": gnani_configured,
            "status": "CONFIGURED" if gnani_configured else "NOT_CONFIGURED",
            "model": settings.gnani_prisma_model,
            "endpoint": settings.gnani_prisma_url,
            "languages": ["te-IN", "hi-IN", "en-IN"],
            "verification_type": "credential_presence",
        },
        "gnani_timbre": {
            "configured": gnani_configured,
            "status": "CONFIGURED" if gnani_configured else "NOT_CONFIGURED",
            "model": settings.gnani_timbre_model,
            "voice": settings.gnani_timbre_voice,
            "verification_type": "credential_presence",
        },
        "groq_llm": {
            "configured": groq_configured,
            "status": "CONFIGURED" if groq_configured else "NOT_CONFIGURED",
            "model": settings.groq_model,
            "verification_type": "credential_presence",
        },
        "compliance": {
            "calling_window_start": settings.call_window_start,
            "calling_window_end": settings.call_window_end,
            "test_mode": settings.test_mode,
            "contact_cap_count": settings.contact_cap_count,
        },
    }

