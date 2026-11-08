"""Service for generating Markdown evidence reports and CSV/JSON data exports."""

import csv
from datetime import datetime, timezone
import io
from typing import Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.db import build_tenant_query
from app.services.outcomes import build_outcomes_filter, get_outcomes_summary


async def generate_evidence_markdown(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    test_run_label: str,
) -> str:
    """Generate an honest, database-backed Markdown evidence report for a test run."""
    summary = await get_outcomes_summary(db, tenant_id, test_run_label=test_run_label)
    query = build_outcomes_filter(tenant_id, test_run_label=test_run_label)
    cursor = db.communications.find(query).sort("created_at", 1)
    comms = await cursor.to_list(length=5000)

    # Distinct recipients
    distinct_recipients = len({str(c.get("recipient_id")) for c in comms if c.get("recipient_id")})
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Match scenarios from campaign_recipients
    camp_ids = list({c["campaign_id"] for c in comms if c.get("campaign_id")})
    rcpt_ids = list({c["recipient_id"] for c in comms if c.get("recipient_id")})
    rcpt_cursor = db.campaign_recipients.find(build_tenant_query(tenant_id, {
        "campaign_id": {"$in": camp_ids},
        "entity_id": {"$in": rcpt_ids},
    }))
    scenario_map: dict[str, str] = {}
    async for r in rcpt_cursor:
        k = f"{r.get('campaign_id')}:{r.get('entity_id')}"
        if r.get("tester_scenario"):
            scenario_map[k] = r["tester_scenario"]

    # Build report sections
    md: list[str] = [
        f"# TARA Voice Outreach Evidence Report",
        f"**Test Run Label:** `{test_run_label}`  ",
        f"**Generated:** {now_str}  ",
        f"**Tenant ID:** `{tenant_id}`  \n",
        "## 1. Test Conditions & Environment",
        f"- **TEST_MODE:** `{settings.test_mode}`",
        f"- **Distinct Recipients Contacted:** {distinct_recipients}",
        "- **Telephony Carrier:** Twilio Voice & Media Streams",
        "- **Speech-To-Text (STT):** Gnani Prisma v3.0 (Streaming)",
        "- **Text-To-Speech (TTS):** Gnani Timbre v2.5 (Neural Indian Voices)",
        "- **Conversation Intelligence:** Groq LLM (Ultra-Fast Inference)",
        "- **Orchestration Gateway:** TARA 2.0 Bi-directional FastAPI Gateway",
        "\n## 2. Quantitative Performance Metrics",
        "| Metric | Result | Definition |",
        "| :--- | :--- | :--- |",
        f"| **Attempted** | {summary.attempted} | {summary.definitions['attempted']} |",
        f"| **Blocked** | {summary.blocked} | {summary.definitions['blocked']} |",
        f"| **Dispatched** | {summary.dispatched} | {summary.definitions['dispatched']} |",
        f"| **Connected** | {summary.connected} | {summary.definitions['connected']} |",
        f"| **Completed** | {summary.completed} | {summary.definitions['completed']} |",
        f"| **No Answer / Busy** | {summary.no_answer} | {summary.definitions['no_answer']} |",
        f"| **Failed** | {summary.failed} | {summary.definitions['failed']} |",
        f"| **Avg Duration** | {f'{summary.avg_duration_seconds}s' if summary.avg_duration_seconds is not None else 'not available'} | {summary.definitions['avg_duration_seconds']} |",
        f"| **Median Duration** | {f'{summary.median_duration_seconds}s' if summary.median_duration_seconds is not None else 'not available'} | {summary.definitions['median_duration_seconds']} |",
        f"| **P95 Duration** | {f'{summary.p95_duration_seconds}s' if summary.p95_duration_seconds is not None else 'not available'} | {summary.definitions['p95_duration_seconds']} |",
        f"| **Median Latency** | {f'{summary.latency.median_ms} ms (n={summary.latency.n})' if summary.latency.available else 'not available (latency not provided in provider webhook payload)'} | {summary.definitions['latency']} |",
        f"| **Total Cost** | {f'${summary.cost.total}' if summary.cost.available else 'not available (cost not provided in provider webhook payload)'} | {summary.definitions['cost']} |",
        f"| **Webhook Integrity** | {summary.webhook_delivery.communications_with_terminal_status} terminal / {summary.webhook_delivery.events_received} events | {summary.definitions['webhook_delivery']} |",
        "\n### Extraction Fill Rates (Completed Calls)",
        f"- **Interest Level:** {summary.extraction_fill_rate.interest_level}%",
        f"- **Preferred Amount:** {summary.extraction_fill_rate.preferred_amount}%",
        f"- **Callback Time:** {summary.extraction_fill_rate.preferred_callback_time}%",
        f"- **Language Detected:** {summary.extraction_fill_rate.language_used}%",
        "\n## 3. Per-Scenario Evaluation (Expected vs Actual)",
    ]

    scenario_rows = []
    for c in comms:
        k = f"{c.get('campaign_id')}:{c.get('recipient_id')}"
        scen = c.get("tester_scenario") or scenario_map.get(k)
        if scen:
            out = c.get("outcome") or {}
            dur = out.get("duration_seconds", 0)
            act_interest = out.get("interest_level") or c.get("status")
            ext = f"amt={out.get('preferred_amount', '—')}, cb={out.get('preferred_callback_time', '—')}"
            scenario_rows.append(f"| #{str(c['_id'])[-6:]} | {c.get('phone_masked', '—')} | {scen} | {act_interest} | {ext} | {dur}s | {c.get('status')} |")

    if scenario_rows:
        md.append("| Call ID | Masked Phone | Expected Scenario | Actual Outcome | Extracted Fields | Duration | Final Status |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        md.extend(scenario_rows)
    else:
        md.append("No pre-scripted tester scenarios were attached to recipient records in this test run.")

    # Failed and Blocked Calls table
    md.append("\n## 4. Failed and Blocked Calls Log")
    anom_rows = []
    for c in comms:
        st = c.get("status")
        if st in ("BLOCKED", "FAILED"):
            reason = c.get("blocked_reason") or c.get("error") or "Unknown"
            ts = c.get("created_at").strftime("%Y-%m-%d %H:%M:%S") if isinstance(c.get("created_at"), datetime) else "—"
            anom_rows.append(f"| #{str(c['_id'])[-6:]} | {c.get('phone_masked', '—')} | {st} | `{reason}` | {ts} |")

    if anom_rows:
        md.append("| Call ID | Masked Phone | Status | Reason / Error | Timestamp |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")
        md.extend(anom_rows)
    else:
        md.append("All attempted calls in this test run were either dispatched successfully or completed without compliance blocks.")

    # Fixed Limitations Section
    md.extend([
        "\n## 5. Limitations",
        f"These are test calls to {distinct_recipients} verified testers following scripts. "
        "They measure pipeline reliability, latency and extraction behaviour. "
        "They do not measure real-world conversion. Scoring models are trained on synthetic data.",
    ])

    return "\n".join(md)


async def generate_outcomes_export(
    db: AsyncIOMotorDatabase,
    tenant_id: str,
    filters: dict[str, Any],
    export_format: str = "csv",
) -> str | list[dict[str, Any]]:
    """Export up to 5000 communication records in CSV or JSON format with masked phone numbers."""
    query = build_outcomes_filter(
        tenant_id,
        campaign_id=filters.get("campaign_id"),
        test_run_label=filters.get("test_run_label"),
        channel=filters.get("channel"),
        status=filters.get("status"),
        outcome=filters.get("outcome"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )

    cursor = db.communications.find(query).sort("created_at", -1).limit(5000)
    comms = await cursor.to_list(length=5000)

    # Resolve campaigns and tester scenarios
    camp_ids = list({ObjectId(c["campaign_id"]) for c in comms if c.get("campaign_id") and ObjectId.is_valid(c["campaign_id"])})
    camp_map = {str(d["_id"]): d.get("name") async for d in db.campaigns.find(build_tenant_query(tenant_id, {"_id": {"$in": camp_ids}}))}

    rc_cursor = db.campaign_recipients.find(build_tenant_query(tenant_id, {
        "campaign_id": {"$in": [c.get("campaign_id") for c in comms if c.get("campaign_id")]},
        "entity_id": {"$in": [c.get("recipient_id") for c in comms if c.get("recipient_id")]},
    }))
    scen_map = {f"{r.get('campaign_id')}:{r.get('entity_id')}": r.get("tester_scenario") async for r in rc_cursor if r.get("tester_scenario")}

    records: list[dict[str, Any]] = []
    for c in comms:
        cid = str(c["_id"])
        out = c.get("outcome") or {}
        k = f"{c.get('campaign_id')}:{c.get('recipient_id')}"
        ts = c.get("created_at").isoformat() if isinstance(c.get("created_at"), datetime) else str(c.get("created_at", ""))

        lat = out.get("latency")
        lat_ms = str(lat) if isinstance(lat, (int, float)) else (str(lat.get("overall")) if isinstance(lat, dict) and "overall" in lat else "")

        records.append({
            "communication_id": cid,
            "created_at": ts,
            "campaign": camp_map.get(str(c.get("campaign_id", "")), c.get("campaign_id", "")),
            "test_run_label": c.get("test_run_label") or c.get("metadata", {}).get("test_run_label", ""),
            "scenario": c.get("tester_scenario") or scen_map.get(k, ""),
            "status": c.get("status", ""),
            "interest_level": out.get("interest_level", ""),
            "preferred_amount": out.get("preferred_amount", ""),
            "preferred_callback_time": out.get("preferred_callback_time", ""),
            "duration": out.get("duration_seconds", ""),
            "latency_ms": lat_ms,
            "language_used": out.get("language_used") or c.get("request_variables", {}).get("language", ""),
            "hangup_reason": out.get("hangup_reason", ""),
            "blocked_reason": c.get("blocked_reason", ""),
            "config_version": c.get("config_version", ""),
        })

    if export_format == "json":
        return records

    # CSV output with safe quoting (no transcripts included, injection-safe)
    output = io.StringIO()
    fields = [
        "communication_id", "created_at", "campaign", "test_run_label", "scenario",
        "status", "interest_level", "preferred_amount", "preferred_callback_time",
        "duration", "latency_ms", "language_used", "hangup_reason", "blocked_reason", "config_version",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for rec in records:
        safe_rec = {
            k: (f"'{v}" if isinstance(v, str) and v and v[0] in ("=", "+", "-", "@") else v)
            for k, v in rec.items()
        }
        writer.writerow(safe_rec)

    return output.getvalue()
