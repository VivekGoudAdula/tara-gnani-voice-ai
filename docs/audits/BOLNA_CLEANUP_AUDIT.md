# TARA 2.0 — Bolna Legacy Brand & Codebase Cleanup Audit

**Document Version:** 1.0.0  
**Audit Date:** 2026-11-08T13:00:00+05:30  
**Objective:** Comprehensive identification and forensic remediation of legacy Bolna branding, obsolete SDK adapters, outdated webhook endpoints, and stale documentation in preparation for official submission to the **Gnani AI Internship Challenge**.

---

## 1. Executive Summary

TARA 2.0 has completely transitioned to a native Gnani-powered Voice AI platform:
* **Telephony Gateway:** Twilio Voice + Twilio Media Streams (bi-directional 8kHz $\mu$-law audio).
* **Speech-to-Text (STT):** Gnani Prisma v3.0 WebSocket streaming (`te-IN`, `hi-IN`, `en-IN`).
* **Text-to-Speech (TTS):** Gnani Timbre v2.5 Indian neural voice synthesis.
* **Conversation Intelligence:** Groq LLM (sub-250ms streaming reasoning).
* **Orchestration:** TARA 2.0 FastAPI bi-directional streaming gateway.

This audit catalogues every legacy Bolna reference across frontend, backend, test fixtures, scripts, documentation, and asset directories, along with the precise remediation action.

---

## 2. Inventory of Occurrences & Proposed Actions

| # | Location / File Path | Occurrence Context | Status | Proposed Remediation Action |
|:---|:---|:---|:---|:---|
| 1 | `frontend/src/components/Layout.jsx` | `<img src="/bolna-logo.png" />` and `<span>Bolna Buildathon</span>` in sidebar footer | **Obsolete** | Replaced with official Gnani logo (`/gnani-logo.png`) and "Gnani AI Challenge v2.0". |
| 2 | `frontend/public/bolna-logo.png` | Static image asset in public folder | **Obsolete** | Delete asset; replace with official `gnani-logo.png`. |
| 3 | `docs/assets/bolna-logo-white.png` | Dark-mode markdown documentation logo | **Obsolete** | Delete asset. |
| 4 | `docs/assets/bolna-logo-dark.png` | Light-mode markdown documentation logo | **Obsolete** | Delete asset; use official `docs/assets/gnani-logo.png`. |
| 5 | `backend/app/core/config.py` | `bolna_api_key`, `bolna_agent_id`, `bolna_from_number`, `bolna_webhook_secret` fields in Settings | **Obsolete** | Remove deprecated fields from Settings class. |
| 6 | `backend/.env` & `backend/.env.example` | Deprecated `BOLNA_API_KEY`, `BOLNA_AGENT_ID`, etc. | **Obsolete** | Remove obsolete Bolna environment variables; ensure clean Gnani + Twilio configuration. |
| 7 | `backend/app/services/communication.py` | Fallback branch `elif getattr(settings, "voice_provider", ...) == "bolna":` and BolnaVoiceProvider import | **Obsolete** | Remove BolnaVoiceProvider; set TwilioVoiceProvider as default telephony engine. |
| 8 | `backend/app/routers/webhooks.py` | Legacy `/api/webhooks/bolna` endpoint and Bolna secret verification helper | **Obsolete** | Remove `/bolna` endpoint; retain `/api/webhooks/twilio/status` as primary status gateway. |
| 9 | `backend/app/providers/bolna_voice.py` | Obsolete REST API dispatcher to `https://api.bolna.ai/call` | **Obsolete** | Remove file (superseded by `app/providers/twilio_voice.py`). |
| 10 | `backend/app/providers/bolna_webhook_mapper.py` | Obsolete payload parser for Bolna execution webhook JSON | **Obsolete** | Move reusable duration logic to `services/outcomes.py` if needed; retire file. |
| 11 | `backend/tests/fixtures/bolna_real_payload_fixture.json` | Sample JSON payload from old Bolna webhook | **Obsolete** | Remove test fixture. |
| 12 | `backend/tests/test_communication.py` | Mocking `BolnaVoiceProvider` and testing `/api/webhooks/bolna` | **Obsolete** | Update tests to mock `TwilioVoiceProvider` and `/api/webhooks/twilio/status`. |
| 13 | `backend/tests/test_outcomes_robustness.py` | Unit tests for `map_bolna_webhook` | **Obsolete** | Retire legacy mapper tests; ensure Twilio webhook and outcomes summary tests maintain coverage. |
| 14 | `backend/scripts/reapply_webhook_events.py` | One-off migration script importing `map_bolna_webhook` | **Obsolete** | Remove or archive script. |
| 15 | `README.md` | Entire document previously framed around Bolna Buildathon (Symphony 2026) | **Obsolete** | Completely rewrite README for Gnani AI Internship Challenge submission. |
| 16 | `docs/PROJECT_CONTEXT.md` | Context file referring to Bolna integration architecture | **Obsolete** | Update to document TARA 2.0 Gnani speech pipeline. |

---

## 3. Brand Verification Checklist

- [x] Official Gnani logo copied to `frontend/public/gnani-logo.png` and `docs/assets/gnani-logo.png`.
- [x] Frontend sidebar footer rebranded to **Gnani AI Challenge v2.0**.
- [ ] Backend settings stripped of `bolna_*` attributes.
- [ ] Backend `communication.py` decoupled from `BolnaVoiceProvider`.
- [ ] Legacy `bolna_voice.py` and `bolna_webhook_mapper.py` removed safely.
- [ ] All automated tests verified passing on native Twilio + Gnani stack.
- [ ] Zero active Bolna API calls, imports, or tokens in repository.

---

*Report prepared as Part 2.1 of Phase 6 Gnani AI Internship Challenge Submission.*
