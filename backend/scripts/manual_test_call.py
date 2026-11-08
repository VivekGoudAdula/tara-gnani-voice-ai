"""Guarded manual test script for executing a real voice call via TARA 2.0 Gnani + Twilio Voice AI."""

import asyncio
import os
import sys
import time
from pathlib import Path
import httpx

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.core.config import settings
from app.core.security import mask_phone


async def main() -> None:
    """Execute manual test call for an allowlisted lead and poll outcome."""
    # 1. Guard against accidental execution outside TEST_MODE
    if not settings.test_mode:
        print("ERROR: Refusing to run. TEST_MODE must be enabled (true) in .env for manual test calls.")
        sys.exit(1)

    allowlist = [num.strip() for num in settings.test_allowlist.split(",") if num.strip()]
    if not allowlist:
        print("ERROR: TEST_ALLOWLIST in .env is empty. Add your verified test phone number before running.")
        sys.exit(1)

    base_url = "http://localhost:8000"
    print(f"--- TARA Manual Call Test Runner ---")
    print(f"Target Server: {base_url}")
    print(f"Test Mode: {settings.test_mode}")
    print(f"Allowlisted Numbers: {[mask_phone(num) for num in allowlist]}")

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # 2. Authenticate as employee@testbank.com
        print("\nLogging in as employee@testbank.com...")
        login_resp = await client.post(
            "/api/auth/login",
            json={"email": "employee@testbank.com", "password": settings.seed_password},
        )
        if login_resp.status_code != 200:
            print(f"Login failed ({login_resp.status_code}): {login_resp.text}")
            sys.exit(1)

        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("Authentication successful.")

        # 3. Retrieve Test Bank leads
        print("Fetching leads for Test Bank...")
        leads_resp = await client.get("/api/leads?page_size=100", headers=headers)
        if leads_resp.status_code != 200:
            print(f"Failed to fetch leads: {leads_resp.text}")
            sys.exit(1)

        leads = leads_resp.json().get("items", [])
        target_lead = None
        for lead in leads:
            if lead.get("phone") in allowlist:
                target_lead = lead
                break

        if not target_lead:
            print(
                f"No lead found matching TEST_ALLOWLIST. (Total leads inspected: {len(leads)}).\n"
                f"Please update an existing lead or seed one matching your allowlisted phone."
            )
            sys.exit(1)

        print(
            f"Selected lead: ID={target_lead['id']}, Name={target_lead['name']}, "
            f"Phone={mask_phone(target_lead['phone'])}, Language={target_lead['language']}"
        )

        # 4. Dispatch Call via POST /api/communication/send
        print("\nDispatching call via POST /api/communication/send...")
        send_payload = {
            "channel": "voice",
            "recipient_ref": {"type": "lead", "id": target_lead["id"]},
            "content": {
                "language": target_lead.get("language") or "telugu",
                "variables": {
                    "product_name": "Personal Loan",
                    "objective": "Verify pre-approved personal loan offer eligibility and collect callback time",
                    "questions_to_collect": "loan amount, preferred callback time",
                    "tone": "Professional and helpful",
                    "bank_name": "Test Bank",
                },
            },
            "metadata": {"test_run": True},
        }

        dispatch_resp = await client.post("/api/communication/send", json=send_payload, headers=headers)
        print(f"Dispatch HTTP Status: {dispatch_resp.status_code}")
        data = dispatch_resp.json()
        print(f"Response: {data}")

        comm_id = data.get("communication_id")
        if not comm_id:
            print("No communication_id returned. Exiting.")
            sys.exit(1)

        if data.get("status") == "BLOCKED":
            print(f"Dispatch BLOCKED by compliance gate. Reason: {data.get('blocked_reason')}")
            sys.exit(0)

        # 5. Poll GET /api/communications/{id} every 5s for up to 3 minutes
        print(f"\nPolling outcome for communication ID: {comm_id} (up to 3 minutes)...")
        max_attempts = 36  # 36 * 5s = 180s
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(5)
            poll_resp = await client.get(f"/api/communications/{comm_id}", headers=headers)
            if poll_resp.status_code != 200:
                print(f"[{attempt}/{max_attempts}] Poll failed: {poll_resp.status_code}")
                continue

            comm = poll_resp.json()
            curr_status = comm.get("status")
            provider_status = comm.get("provider_status")
            print(f"[{attempt * 5}s] Status: {curr_status} | Provider Status: {provider_status}")

            if curr_status in ("COMPLETED", "FAILED", "NO_ANSWER", "BUSY", "CANCELLED"):
                print("\n=== Final Communication Outcome ===")
                print(f"Status: {curr_status}")
                print(f"Provider Ref: {comm.get('provider_ref')}")
                outcome = comm.get("outcome") or {}
                print(f"Duration: {outcome.get('duration_seconds')} seconds")
                print(f"Hangup Reason: {outcome.get('hangup_reason')}")
                print(f"Interest Level: {outcome.get('interest_level')}")
                print(f"Preferred Callback: {outcome.get('preferred_callback_time')}")
                print(f"Transcript: {outcome.get('transcript')}")
                return

        print("\nPolling window (3 minutes) completed without terminal status update.")


if __name__ == "__main__":
    asyncio.run(main())
