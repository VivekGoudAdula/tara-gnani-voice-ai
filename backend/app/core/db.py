"""MongoDB connection, index initialization, and tenant isolation helpers."""

import logging
from typing import Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings

logger = logging.getLogger("tara.db")

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


def get_db() -> AsyncIOMotorDatabase:
    """Return the active MongoDB database instance."""
    if db is None:
        raise RuntimeError("Database not initialized. Call init_db first.")
    return db


_indexes_verified_dbs: set[str] = set()


async def init_db(db_name: str | None = None) -> None:
    """Initialize MongoDB client and create necessary indexes."""
    global client, db
    logger.info("Connecting to MongoDB at %s", settings.mongo_uri.split("@")[-1])
    client = AsyncIOMotorClient(settings.mongo_uri)
    target_db = db_name or settings.mongo_db_name
    db = client[target_db]

    # Verify connection
    await client.admin.command("ping")

    if target_db in _indexes_verified_dbs:
        return

    # Ensure required indexes
    await db.users.create_index("email", unique=True)
    await db.tenants.create_index("slug", unique=True)

    await db.leads.create_index([("tenant_id", 1), ("phone", 1)])
    await db.leads.create_index([("tenant_id", 1), ("language", 1)])
    await db.leads.create_index([("tenant_id", 1), ("consent", 1)])
    await db.leads.create_index([("tenant_id", 1), ("dnd", 1)])

    await db.customers.create_index([("tenant_id", 1), ("phone", 1)])
    await db.customers.create_index([("tenant_id", 1), ("language", 1)])
    await db.customers.create_index([("tenant_id", 1), ("consent", 1)])
    await db.customers.create_index([("tenant_id", 1), ("dnd", 1)])

    await db.products.create_index([("tenant_id", 1), ("active", 1)])

    # Communications and Webhook indexes
    await db.communications.create_index([("tenant_id", 1), ("recipient_id", 1), ("created_at", -1)])
    await db.communications.create_index([("tenant_id", 1), ("status", 1)])
    await db.communications.create_index([("provider_ref", 1)], sparse=True)
    await db.communications.create_index(
        [("tenant_id", 1), ("idempotency_key", 1)],
        unique=True,
        partialFilterExpression={"idempotency_key": {"$type": "string"}},
    )
    await db.webhook_events.create_index([("provider_ref", 1)])

    # Scoring and Product Matching indexes
    await db.scoring_runs.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.product_matches.create_index([
        ("tenant_id", 1), ("entity_type", 1), ("product_id", 1), ("is_latest", 1), ("band", 1)
    ])
    await db.product_matches.create_index([("tenant_id", 1), ("entity_id", 1), ("is_latest", 1)])
    await db.product_matches.create_index(
        [("scoring_run_id", 1), ("entity_id", 1), ("product_id", 1)],
        unique=True,
    )

    # Campaign indexes
    await db.campaigns.create_index([("tenant_id", 1), ("status", 1), ("updated_at", -1)])
    await db.campaign_recipients.create_index([("tenant_id", 1), ("campaign_id", 1), ("status", 1)])
    await db.campaign_recipients.create_index([("campaign_id", 1), ("entity_id", 1)], unique=True)
    await db.campaign_configs.create_index([("campaign_id", 1), ("channel", 1), ("version", -1)])
    await db.communications.create_index([("tenant_id", 1), ("campaign_id", 1), ("recipient_id", 1)])

    # Import and Audit indexes
    await db.import_batches.create_index([("tenant_id", 1), ("created_at", -1)])
    await db.import_batch_rows.create_index([("batch_id", 1), ("tenant_id", 1)])
    await db.audit_log.create_index([("tenant_id", 1), ("at", -1)])

    _indexes_verified_dbs.add(target_db)

    logger.info("MongoDB initialized with database '%s' and indexes verified.", target_db)


async def close_db() -> None:
    """Close MongoDB client connection."""
    global client
    if client is not None:
        client.close()
        logger.info("MongoDB connection closed.")


def build_tenant_query(tenant_id: str, extra_query: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Enforce tenant scoping on all database queries.

    Accepts tenant_id and optional additional query criteria.
    Matches either string or ObjectId representation for robust backward compatibility.
    """
    clean_tenant_id = str(tenant_id).strip()
    tenant_matcher: Any = clean_tenant_id
    if ObjectId.is_valid(clean_tenant_id):
        tenant_matcher = {"$in": [clean_tenant_id, ObjectId(clean_tenant_id)]}

    base_query: dict[str, Any] = {"tenant_id": tenant_matcher}

    if not extra_query:
        return base_query

    # Combine queries safely
    combined_query: dict[str, Any] = {**base_query}
    for key, val in extra_query.items():
        if key == "tenant_id":
            # Never allow caller to override tenant_id
            continue
        combined_query[key] = val

    return combined_query


def doc_to_dict(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert MongoDB document ObjectId fields to strings for serialization."""
    if doc is None:
        return None
    res = dict(doc)
    if "_id" in res:
        res["id"] = str(res.pop("_id"))
    if "tenant_id" in res and isinstance(res["tenant_id"], ObjectId):
        res["tenant_id"] = str(res["tenant_id"])
    return res
