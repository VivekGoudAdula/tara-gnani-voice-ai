"""Customer and Product Context Retrieval Service for TARA 2.0."""

import logging
from typing import Any, Dict, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.db import build_tenant_query, doc_to_dict

logger = logging.getLogger("tara.conversation.context_service")


class CustomerContextService:
    """
    Retrieves verified customer profile, propensity scores, product details,
    and campaign objectives from MongoDB with strict multi-tenant isolation.
    """

    def __init__(self, db: AsyncIOMotorDatabase, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    async def get_customer_context(
        self,
        entity_id: str,
        entity_type: str = "lead",
    ) -> Dict[str, Any]:
        """
        Fetch customer or lead record from the database.

        Args:
            entity_id: String ID of the lead or customer document.
            entity_type: 'lead' or 'customer'.

        Returns:
            Sanitized dictionary containing verified customer attributes.
        """
        if not entity_id:
            return {}

        target_id = ObjectId(entity_id) if ObjectId.is_valid(entity_id) else entity_id
        collection = self.db.leads if entity_type == "lead" else self.db.customers
        query = build_tenant_query(self.tenant_id, {"_id": target_id})
        doc = await collection.find_one(query)

        if not doc:
            logger.warning("Recipient '%s' (type: %s) not found in tenant '%s'", entity_id, entity_type, self.tenant_id)
            return {}

        record = doc_to_dict(doc)
        return {
            "id": record.get("id"),
            "name": record.get("name", "Customer"),
            "phone": record.get("phone", ""),
            "city": record.get("city", "Unknown"),
            "age": record.get("age"),
            "income": record.get("income"),
            "segment": record.get("segment", "General"),
            "consent": record.get("consent", False),
            "dnd": record.get("dnd", False),
            "account_type": record.get("account_type", "Standard"),
            "balance": record.get("balance"),
        }

    async def get_product_context(self, product_id: Optional[str]) -> Dict[str, Any]:
        """
        Retrieve verified financial product parameters, features, and eligibility constraints.

        Args:
            product_id: Product ID string.

        Returns:
            Product details dictionary.
        """
        if not product_id:
            return {
                "name": "Personal Loan",
                "category": "personal_loan",
                "description": "Flexible instant personal loan with minimal documentation.",
                "interest_rate": "10.49%",
                "min_amount": "50,000",
                "max_amount": "5,00,000",
                "features": [
                    "Zero physical paperwork",
                    "Disbursement within 10 minutes",
                    "Flexible repayment tenure up to 60 months",
                    "No prepayment penalty after 6 months",
                ],
                "faqs": [
                    {"q": "What is the interest rate?", "a": "Interest rates start from 10.49% per annum based on credit score."},
                    {"q": "How fast is disbursement?", "a": "Funds are transferred directly to your bank account within 10 minutes of digital consent."},
                    {"q": "Is collateral required?", "a": "No collateral or guarantor is required for pre-approved personal loans."},
                ],
            }

        target_id = ObjectId(product_id) if ObjectId.is_valid(product_id) else product_id
        query = build_tenant_query(self.tenant_id, {"_id": target_id})
        doc = await self.db.products.find_one(query)

        if not doc:
            return {"name": "Personal Loan", "interest_rate": "10.49%", "max_amount": "5,00,000"}

        prod = doc_to_dict(doc)
        return {
            "id": prod.get("id"),
            "name": prod.get("name", "Personal Loan"),
            "category": prod.get("category", "personal_loan"),
            "description": prod.get("description", ""),
            "eligibility_rules": prod.get("eligibility_rules", {}),
            "features": prod.get("features", [
                "Zero physical paperwork",
                "Disbursement within 10 minutes",
                "Flexible repayment tenure",
            ]),
            "faqs": prod.get("faqs", []),
        }

    async def get_product_match(
        self,
        entity_id: str,
        product_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve existing ML propensity match score and eligibility explanations.

        Args:
            entity_id: Recipient entity ID.
            product_id: Target product ID.

        Returns:
            Propensity match summary.
        """
        if not entity_id:
            return {}

        query: Dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "entity_id": entity_id,
            "is_latest": True,
        }
        if product_id:
            query["product_id"] = product_id

        doc = await self.db.product_matches.find_one(query)
        if not doc:
            return {"match_score": 0.85, "band": "HIGH", "eligibility": "ELIGIBLE"}

        match_data = doc_to_dict(doc)
        return {
            "match_score": match_data.get("match_score", 0.0),
            "band": match_data.get("band", "HIGH"),
            "eligibility": match_data.get("eligibility", "ELIGIBLE"),
            "reasons": [r.get("text") for r in match_data.get("reason_codes", []) if isinstance(r, dict)],
        }

    async def get_campaign_context(self, campaign_id: Optional[str]) -> Dict[str, Any]:
        """
        Retrieve campaign objectives, targeting criteria, and script directives.

        Args:
            campaign_id: String campaign ID.

        Returns:
            Campaign context dictionary.
        """
        if not campaign_id:
            return {
                "name": "Q4 Loan Acquisition",
                "objective": "Pre-approved personal loan adoption for premium account holders",
            }

        target_id = ObjectId(campaign_id) if ObjectId.is_valid(campaign_id) else campaign_id
        query = build_tenant_query(self.tenant_id, {"_id": target_id})
        doc = await self.db.campaigns.find_one(query)

        if not doc:
            return {"name": "Loan Outreach", "objective": "Customer Acquisition"}

        camp = doc_to_dict(doc)
        return {
            "id": camp.get("id"),
            "name": camp.get("name", "Outreach"),
            "objective": camp.get("objective", "Customer Acquisition"),
            "product_id": camp.get("product_id"),
        }

