# TARA — Project Structure & Codebase Map

This document provides a comprehensive map of the **TARA (Targeted Acquisition & Reach Agent)** codebase.

---

## 1. Top-Level Organization

```
APP/
├── backend/                  # FastAPI backend, async workers & voice engine
│   ├── app/                  # Application core logic & modules
│   ├── scripts/              # Verification, maintenance & test scripts
│   ├── tests/                # Automated pytest test suites (131 tests)
│   ├── requirements.txt      # Python dependencies
│   └── .env.example          # Template for backend environment variables
├── frontend/                 # React 18 + Vite enterprise SaaS frontend
│   ├── public/               # Static assets (including Gnani official logo)
│   ├── src/                  # React source code (pages, components, context)
│   ├── package.json          # Node dependencies & build scripts
│   └── tailwind.config.js    # Tailwind design system configuration
├── docs/                     # Architectural, deployment, and QA documentation
│   ├── assets/               # Logos and architecture diagrams
│   ├── audits/               # Forensic audit reports from development phases
│   ├── ARCHITECTURE.md       # Voice pipeline & system architecture
│   ├── DEPLOYMENT_GUIDE.md   # Production deployment walkthrough
│   ├── TESTING_GUIDE.md      # Testing and QA execution instructions
│   ├── PROJECT_STRUCTURE.md  # Codebase structure map (this file)
│   ├── CHALLENGE_SUBMISSION.md # Gnani AI Internship submission report
│   └── DEMO_SCRIPT.md        # 60-second video demo walkthrough
├── README.md                 # Primary project overview and quickstart
├── TARA_Solution_Pitch.pdf   # Executive solution pitch deck
└── .gitignore                # Production git ignore configuration
```

---

## 2. Backend Architecture (`backend/`)

```
backend/app/
├── core/
│   ├── config.py             # Pydantic v2 application settings & environment parser
│   ├── security.py           # JWT token generation, password hashing & auth guards
│   └── database.py           # Motor async MongoDB client & connection pooling
├── models/                   # MongoDB collection schemas & data models
│   ├── tenant.py             # Multi-tenant workspace entities
│   ├── user.py               # User identity, roles, and credentials
│   ├── customer.py           # Customer profiles, propensity scores & history
│   ├── campaign.py           # Outbound voice campaigns & recipient snapshots
│   └── call.py               # Call sessions, transcripts, audio logs & outcomes
├── schemas/                  # Pydantic request & response validation schemas
│   ├── auth.py               # Login, registration, token schemas
│   ├── customers.py          # Customer creation, filtering, update schemas
│   ├── campaigns.py          # Wizard configuration, schedule & audience schemas
│   └── outcomes.py           # Call results, transcripts, analytics summaries
├── routers/                  # FastAPI REST & WebSocket endpoints
│   ├── auth.py               # Authentication endpoints (/api/auth)
│   ├── customers.py          # Customer intelligence CRUD (/api/customers)
│   ├── campaigns.py          # Campaign management & launch (/api/campaigns)
│   ├── media_streams.py      # Twilio Media Streams WebSocket (/api/media-stream)
│   ├── webhooks.py           # Telephony status callbacks (/api/webhooks)
│   └── workspace.py          # Provider health checks & workspace metrics
├── providers/                # External provider integrations & drivers
│   ├── twilio_voice.py       # Twilio REST client & TwiML generation
│   ├── twilio_webhook_mapper.py # Maps Twilio events to internal call states
│   └── speech/
│       ├── audio_transcoder.py # 8kHz &mu;-law <-> 16kHz Linear PCM transcoding
│       ├── gnani_prisma.py   # Gnani Prisma STT streaming ASR integration
│       └── gnani_timbre.py   # Gnani Timbre TTS speech synthesis integration
└── services/                 # Core domain business logic
    ├── campaign_execution.py # Outbound call dispatch loop & batch processor
    ├── campaign_scheduler.py # Background async scheduler for campaigns & retries
    ├── campaign_retry.py     # Retry candidate evaluation & exponential backoff
    ├── campaign_validation.py# Audience validation & snapshot generation
    ├── campaign_analytics.py # KPI computation (Answer Rate, Qualification Rate)
    ├── customer_intelligence.py # Lead scoring & propensity engine
    ├── compliance.py         # Calling hour window & DND regulatory compliance
    └── conversation/
        ├── agent.py          # Conversational state machine & turn coordinator
        └── prompt_builder.py # Contextual LLM prompt assembly (Groq engine)
```

---

## 3. Frontend Architecture (`frontend/`)

```
frontend/src/
├── components/               # Reusable UI widgets & component library
│   ├── Layout.jsx            # Enterprise sidebar layout with Gnani branding
│   ├── campaigns/
│   │   ├── WizardStep1Basics.jsx     # Step 1: Campaign details & objectives
│   │   ├── WizardStep2Audience.jsx   # Step 2: Customer segmentation & filters
│   │   ├── WizardStep3VoiceAgent.jsx # Step 3: Gnani voice & language selection
│   │   ├── WizardStep4Schedule.jsx   # Step 4: Calling window & retry settings
│   │   └── WizardStep5ReviewLaunch.jsx # Step 5: Snapshot preview & launch
│   ├── customers/
│   │   ├── CustomerTable.jsx         # Searchable, filterable customer data grid
│   │   └── CustomerDetailModal.jsx   # Profile view with propensity score history
│   └── outcomes/
│       └── CallDetailDrawer.jsx      # Slide-out drawer with audio playback & transcript
├── pages/                    # Route-level page views
│   ├── Dashboard.jsx         # Executive dashboard with KPIs & provider status
│   ├── Campaigns.jsx         # Campaign overview & status tracking
│   ├── CampaignDetail.jsx    # Campaign-specific metrics, recipient list & progress
│   ├── CampaignWizard.jsx    # Multi-step campaign creation workflow
│   ├── Customers.jsx         # Customer intelligence management
│   ├── Leads.jsx             # High-propensity lead pipeline
│   ├── Conversations.jsx     # Call transcripts & sentiment analysis
│   ├── LiveCalls.jsx         # Active in-flight calls monitor
│   ├── Analytics.jsx         # Deep-dive campaign & conversion analytics
│   ├── Settings.jsx          # Telephony, Gnani API, and compliance settings
│   └── Login.jsx             # Secure authentication view
├── context/
│   └── AuthContext.jsx       # Global authentication state, JWT storage & user roles
├── services/
│   └── api.js                # Axios client with interceptors & error handlers
├── App.jsx                   # React Router configuration and application shell
└── main.jsx                  # React application entry point
```

---

## 4. Test Suite Map (`backend/tests/`)

All 131 test cases are organized across 21 modular files:

- **`test_audio_transcoder.py`**: Audio sample rate, channel count, and codec conversion.
- **`test_gnani_prisma.py`**: Gnani Prisma STT streaming payloads and responses.
- **`test_gnani_timbre.py`**: Gnani Timbre TTS speech synthesis requests and audio handling.
- **`test_intelligent_agent.py`**: Conversation turns, Groq LLM reasoning, and tool calls.
- **`test_media_streams.py`**: Twilio WebSocket media streaming protocol.
- **`test_twilio_voice.py`**: Outbound calling and TwiML instructions.
- **`test_twilio_webhooks.py`**: Twilio status webhook ingestion and idempotency.
- **`test_voice_response.py`**: Dynamic speech responses and fallback handling.
- **`test_campaign_execution.py`**: Outbound call dispatch, crash recovery, and auto-completion.
- **`test_campaigns_config_audience.py`**: Audience filters, snapshots, and campaign validation.
- **`test_campaigns_launch_lifecycle.py`**: Campaign state transitions (Start, Pause, Resume, Cancel).
- **`test_communication.py`**: Voice provider abstraction and retry scheduling.
- **`test_scoring_api.py`**: Propensity scoring API endpoints.
- **`test_scoring_math.py`**: Mathematical correctness of lead scoring formulas.
- **`test_data_import.py`**: Customer data ingestion and schema validation.
- **`test_data_import_governance.py`**: DND registry checks and data governance caps.
- **`test_tenant_isolation.py`**: Multi-tenant data segregation.
- **`test_outcomes.py`**: Call outcome classification and cost tracking.
- **`test_audit_dashboard.py`**: Dashboard KPI aggregations and empty-state safety.

