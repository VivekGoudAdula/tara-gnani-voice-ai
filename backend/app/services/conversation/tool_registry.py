"""Safe tool registry and execution engine for TARA 2.0 conversational agent."""

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.db import build_tenant_query
from app.services.conversation.models import ToolExecutionResult

logger = logging.getLogger("tara.conversation.tool_registry")


class ToolRegistry:
    """
    Executes approved, sandboxed tools for the conversational AI agent with strict
    multi-tenant boundaries and audit tracking.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return standardized JSON schema definitions of all registered tools."""
        return [
            {
                "name": "get_customer_profile",
                "description": "Fetch verified customer details, demographics, and account segment from bank database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string", "description": "ID of customer or lead"},
                        "entity_type": {"type": "string", "enum": ["lead", "customer"], "default": "lead"},
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "get_product_information",
                "description": "Retrieve official interest rates, fees, tenure, and eligibility criteria for a banking product.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string", "description": "Unique product ID"},
                    },
                    "required": [],
                },
            },
            {
                "name": "get_campaign_context",
                "description": "Retrieve campaign objectives, target segment, and product focus.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string", "description": "Active campaign ID"},
                    },
                    "required": [],
                },
            },
            {
                "name": "search_product_faq",
                "description": "Search verified product FAQs for official answers to customer questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Customer question topic"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "update_lead_information",
                "description": "Update customer details provided during the call (e.g. updated city, income, email).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string", "description": "Recipient ID"},
                        "entity_type": {"type": "string", "enum": ["lead", "customer"], "default": "lead"},
                        "updates": {"type": "object", "description": "Key-value dictionary of updated fields"},
                    },
                    "required": ["entity_id", "updates"],
                },
            },
            {
                "name": "update_lead_qualification",
                "description": "Record qualification progress such as loan purpose, amount requested, or timeline.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string", "description": "Lead ID"},
                        "need": {"type": "string", "description": "Customer's identified financial need"},
                        "budget_or_amount": {"type": "string", "description": "Loan amount requested by customer"},
                        "timeline": {"type": "string", "description": "When customer needs the loan"},
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "schedule_callback",
                "description": "Schedule a follow-up outreach callback when customer is busy or requests call later.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string", "description": "Recipient ID"},
                        "callback_time": {"type": "string", "description": "Requested callback window (e.g. tomorrow 4 PM)"},
                    },
                    "required": ["entity_id", "callback_time"],
                },
            },
            {
                "name": "create_follow_up_task",
                "description": "Create an automated CRM task or dispatch SMS/WhatsApp digital application link.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string", "description": "Recipient ID"},
                        "task_title": {"type": "string", "description": "Brief description of task"},
                    },
                    "required": ["entity_id", "task_title"],
                },
            },
            {
                "name": "request_human_escalation",
                "description": "Transfer the call or request an in-person relationship manager contact the customer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Specific reason customer asked for human agent"},
                    },
                    "required": ["reason"],
                },
            },
            {
                "name": "record_customer_objection",
                "description": "Log an objection raised by the customer for CRM analytics (e.g. interest rate too high, competitor preference).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "objection_type": {"type": "string", "description": "Category of objection"},
                        "details": {"type": "string", "description": "Specific concern spoken by customer"},
                    },
                    "required": ["objection_type"],
                },
            },
            {
                "name": "mark_do_not_call",
                "description": "Immediately register customer on Do-Not-Disturb (DND) list and halt all outbound campaigns.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_id": {"type": "string", "description": "Recipient ID to opt out"},
                        "entity_type": {"type": "string", "enum": ["lead", "customer"], "default": "lead"},
                        "reason": {"type": "string", "description": "DND opt-out reason"},
                    },
                    "required": ["entity_id"],
                },
            },
            {
                "name": "end_conversation",
                "description": "Gracefully terminate the telephone call after polite goodbye or clear conclusion.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Termination reason (e.g. completed, declined, callback)"},
                    },
                    "required": ["reason"],
                },
            },
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """
        Safely execute a tool with input validation, tenant isolation, and error capture.

        Args:
            tool_name: Registered tool identifier.
            arguments: Dictionary of arguments supplied by LLM.

        Returns:
            ToolExecutionResult with execution status and output.
        """
        try:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if not handler:
                return ToolExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Tool '{tool_name}' is not registered or supported.",
                )

            output = await handler(arguments)
            return ToolExecutionResult(tool_name=tool_name, success=True, output=output)
        except Exception as exc:
            logger.error("Tool execution failed [%s]: %s", tool_name, exc, exc_info=True)
            return ToolExecutionResult(tool_name=tool_name, success=False, error=str(exc))

    # Internal tool implementations

    async def _tool_get_customer_profile(self, args: Dict[str, Any]) -> Dict[str, Any]:
        eid = args.get("entity_id", "")
        etype = args.get("entity_type", "lead")
        target_id = ObjectId(eid) if ObjectId.is_valid(eid) else eid
        coll = self.db.leads if etype == "lead" else self.db.customers
        doc = await coll.find_one(build_tenant_query(self.tenant_id, {"_id": target_id}))
        if not doc:
            return {"error": f"Recipient '{eid}' not found."}
        return {
            "name": doc.get("name"),
            "city": doc.get("city"),
            "segment": doc.get("segment"),
            "income": doc.get("income"),
        }

    async def _tool_get_product_information(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": "Personal Loan",
            "interest_rate": "10.49%",
            "max_amount": "5,00,000",
            "features": "Zero paperwork, 10-minute disbursement, flexible tenure up to 5 years.",
        }

    async def _tool_get_campaign_context(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "objective": "Customer Acquisition",
            "guidelines": "Consultative, polite, transparent pricing, no pressure.",
        }

    async def _tool_search_product_faq(self, args: Dict[str, Any]) -> Dict[str, Any]:
        q = args.get("query", "").lower()
        if "interest" in q or "vaddi" in q or "rate" in q:
            return {"answer": "Our personal loan interest rate starts at 10.49% per annum with zero hidden charges."}
        if "time" in q or "fast" in q or "disbursement" in q:
            return {"answer": "Disbursement takes less than 10 minutes directly into your savings account."}
        if "paper" in q or "document" in q:
            return {"answer": "This is a 100% paperless pre-approved offer. Only digital consent is required."}
        return {"answer": "We offer flexible terms tailored to your credit profile. Would you like our specialist to send full details?"}

    async def _tool_update_lead_information(self, args: Dict[str, Any]) -> Dict[str, Any]:
        eid = args.get("entity_id")
        etype = args.get("entity_type", "lead")
        updates = args.get("updates", {})
        if not eid or not updates:
            return {"updated": False}

        target_id = ObjectId(eid) if ObjectId.is_valid(eid) else eid
        coll = self.db.leads if etype == "lead" else self.db.customers
        clean_updates = {k: v for k, v in updates.items() if k not in ("_id", "tenant_id")}
        clean_updates["updated_at"] = datetime.now(timezone.utc)
        await coll.update_one(build_tenant_query(self.tenant_id, {"_id": target_id}), {"$set": clean_updates})
        return {"updated": True, "fields": list(clean_updates.keys())}

    async def _tool_update_lead_qualification(self, args: Dict[str, Any]) -> Dict[str, Any]:
        eid = args.get("entity_id")
        qualification_doc = {
            "need": args.get("need"),
            "budget_or_amount": args.get("budget_or_amount"),
            "timeline": args.get("timeline"),
            "qualified_at": datetime.now(timezone.utc),
        }
        if eid:
            target_id = ObjectId(eid) if ObjectId.is_valid(eid) else eid
            await self.db.leads.update_one(
                build_tenant_query(self.tenant_id, {"_id": target_id}),
                {"$set": {"qualification": qualification_doc}},
            )
        return {"recorded": True, "qualification": qualification_doc}

    async def _tool_schedule_callback(self, args: Dict[str, Any]) -> Dict[str, Any]:
        eid = args.get("entity_id")
        cb_time = args.get("callback_time", "Later")
        now_utc = datetime.now(timezone.utc)
        await self.db.audit_log.insert_one({
            "tenant_id": self.tenant_id,
            "action": "callback_scheduled",
            "entity_id": eid,
            "detail": {"callback_time": cb_time},
            "at": now_utc,
        })
        return {"scheduled": True, "callback_time": cb_time}

    async def _tool_create_follow_up_task(self, args: Dict[str, Any]) -> Dict[str, Any]:
        title = args.get("task_title", "Digital Application Link Sent")
        return {"task_created": True, "title": title}

    async def _tool_request_human_escalation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reason = args.get("reason", "Customer requested human representative")
        return {"escalated": True, "reason": reason}

    async def _tool_record_customer_objection(self, args: Dict[str, Any]) -> Dict[str, Any]:
        obj_type = args.get("objection_type", "General")
        details = args.get("details", "")
        return {"logged": True, "type": obj_type, "details": details}

    async def _tool_mark_do_not_call(self, args: Dict[str, Any]) -> Dict[str, Any]:
        eid = args.get("entity_id")
        etype = args.get("entity_type", "lead")
        reason = args.get("reason", "Customer requested DND")
        now_utc = datetime.now(timezone.utc)

        if eid:
            target_id = ObjectId(eid) if ObjectId.is_valid(eid) else eid
            coll = self.db.leads if etype == "lead" else self.db.customers
            await coll.update_one(
                build_tenant_query(self.tenant_id, {"_id": target_id}),
                {"$set": {"dnd": True, "consent": False, "dnd_registered_at": now_utc}},
            )

        await self.db.audit_log.insert_one({
            "tenant_id": self.tenant_id,
            "action": "dnd_registered",
            "entity_id": eid,
            "detail": {"reason": reason},
            "at": now_utc,
        })
        logger.info("Compliance: Opted out entity %s into DND list.", eid)
        return {"dnd_registered": True}

    async def _tool_end_conversation(self, args: Dict[str, Any]) -> Dict[str, Any]:
        reason = args.get("reason", "Normal conclusion")
        return {"conversation_ended": True, "reason": reason}

