# TARA 2.0 — Quality Assurance & Testing Guide

This guide details the testing methodology, automated test suites, and manual verification procedures for **TARA 2.0 (Targeted Acquisition & Reach Agent)**.

---

## 1. Test Suite Summary

TARA 2.0 includes a comprehensive automated test suite consisting of **131 tests across 21 test suites**, achieving **100% pass rate**.

| Test Module | Test File | Test Count | Key Functionality Verified |
| :--- | :--- | :--- | :--- |
| **Audio Transcoding** | `test_audio_transcoder.py` | 8 | 8kHz &mu;-law to 16kHz PCM transcoding, sample rate conversion, chunk alignment |
| **Gnani Prisma STT** | `test_gnani_prisma.py` | 3 | Streaming ASR payload formatting, WebSocket connectivity, multilingual handling |
| **Gnani Timbre TTS** | `test_gnani_timbre.py` | 4 | Speech synthesis requests, voice selection, audio streaming, format conversions |
| **Intelligent Agent** | `test_intelligent_agent.py` | 20 | Multi-turn state machine, Groq LLM prompt assembly, intent detection, tool calling |
| **Media Streams** | `test_media_streams.py` | 3 | Bi-directional WebSocket handshake, audio buffering, event handling (`start`/`media`/`stop`) |
| **Twilio Voice API** | `test_twilio_voice.py` | 5 | TwiML generation, outbound call dispatching, call termination, error handling |
| **Twilio Webhooks** | `test_twilio_webhooks.py` | 3 | Twilio status callback mapping, status transitions, signature verification |
| **Voice Response** | `test_voice_response.py` | 6 | Dynamic TwiML construction, fallback speech, hangup flows |
| **Campaign Execution** | `test_campaign_execution.py` | 34 | Dispatch loop, crash recovery for in-flight calls, auto-completion, retry handling |
| **Campaign Configuration** | `test_campaigns_config_audience.py` | 5 | Audience segmentation, snapshot creation, parameter validation |
| **Campaign Lifecycle** | `test_campaigns_launch_lifecycle.py` | 3 | Launch, pause, resume, cancel, and complete transitions |
| **Communication Layer** | `test_communication.py` | 6 | Voice provider abstraction, multi-channel dispatch, retry scheduling |
| **Lead Scoring API** | `test_scoring_api.py` | 4 | Propensity scoring endpoints, weights validation, recalculation triggers |
| **Scoring Math** | `test_scoring_math.py` | 5 | Deterministic score formula calculations, demographic and engagement weights |
| **Data Import** | `test_data_import.py` | 4 | CSV/JSON customer import, schema mapping, duplicate detection |
| **Data Governance** | `test_data_import_governance.py` | 3 | DND filtering, consent recording, data validation caps |
| **Tenant Isolation** | `test_tenant_isolation.py` | 6 | Multi-tenant database querying, strict workspace boundary enforcement |
| **Call Outcomes** | `test_outcomes.py` | 6 | Post-call outcome recording, interest classification, cost tracking |
| **Audit Dashboard** | `test_audit_dashboard.py` | 3 | KPI aggregations, contact rates, qualification metrics, empty-state resilience |
| **Total Passed** | **21 Suites** | **131 Tests** | **Zero Failures, Zero Flaky Tests** |

---

## 2. Running Automated Backend Tests

### Run the Complete Test Suite
```bash
cd backend
python -m pytest tests/ -v
```

### Run Tests with Coverage Report
```bash
python -m pytest tests/ --cov=app --cov-report=term-missing
```

### Run Specific Test Categories
```bash
# Test Gnani Voice AI components only
python -m pytest tests/test_gnani_prisma.py tests/test_gnani_timbre.py -v

# Test Conversation Intelligence & Agent Reasoning
python -m pytest tests/test_intelligent_agent.py -v

# Test Campaign Execution & Crash Recovery
python -m pytest tests/test_campaign_execution.py -v
```

---

## 3. Frontend Verification & Build

### Running Frontend Production Build
```bash
cd frontend
npm run build
```
Expected output:
```
✓ 1548 modules transformed.
dist/index.html                   1.10 kB │ gzip:   0.60 kB
dist/assets/index.css            48.56 kB │ gzip:   8.94 kB
dist/assets/index.js            519.05 kB │ gzip: 125.55 kB
✓ built in ~27s
```

---

## 4. End-to-End Live Simulation Testing

TARA includes a dedicated verification script to simulate and test outbound calls without placing live telecommunication charges:

### Command:
```bash
cd backend
python scripts/manual_test_call.py --to "+919876543210" --language "te-IN" --campaign-id "test-campaign"
```

### Simulation Checklist:
1. **Twilio Outbound Handshake:** Verifies that Twilio REST client creates an outbound call with the `<Connect><Stream>` payload.
2. **Media Stream Connection:** Simulates incoming WebSocket frames (`start`, `media`, `stop`).
3. **Prisma STT Recognition:** Injects sample audio frames and verifies transcribed Telugu/Hindi/English utterances.
4. **Groq Conversation Decision:** Asserts that system prompts produce contextual responses matching customer intent.
5. **Timbre TTS Synthesis:** Asserts that synthetic speech is returned and properly transcoded to 8kHz &mu;-law chunks.
6. **Outcome Persistence:** Asserts that MongoDB stores the completed call with duration, cost, and qualification status.

---

## 5. Critical Edge-Case Audits

The platform has been audited and verified for the following critical edge cases:

1. **In-Flight Crash Recovery:** If the backend terminates while a call is in the `CALLING` or `IN_PROGRESS` state, the background scheduler reconciles the call state with Twilio's live status upon restart before determining retry eligibility. It will **never** blindly re-dial an active conversation.
2. **Calling Window & DND Enforcement:** Every recipient is subjected to a final compliance gate immediately before dispatch. Calls outside the configured calling window (`09:00` - `21:00` in `Asia/Kolkata`) or flagged as DND are automatically deferred or blocked.
3. **Webhook Idempotency:** Twilio status callbacks are deduplicated using unique event hashes and transition guards, preventing duplicate counter increments or conflicting call states.
4. **Graceful Fallback on Network Interruption:** If Gnani API or Groq encounters transient network latency, TARA plays a pre-synthesized regional apology phrase ("దయచేసి ఒక్క క్షణం వేచి ఉండండి...") without terminating the call.
