# TARA 2.0 — System Architecture & Voice Pipeline Specification

## 1. Executive Summary

**TARA 2.0 (Targeted Acquisition & Reach Agent)** is an enterprise-grade multilingual Voice AI customer acquisition and engagement SaaS platform designed for the **Gnani AI Internship Challenge**. TARA orchestrates end-to-end outbound and inbound conversational campaigns, executing low-latency, natural dialogues in Indian regional languages (Telugu, Hindi, and Indian English).

The system pairs telecommunication-grade WebSockets with **Gnani Prisma Speech-to-Text (STT)** and **Gnani Timbre Text-to-Speech (TTS)**, managed by an intelligent conversational state machine powered by Groq LLMs.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph TelephonyLayer ["1. Telephony Layer"]
        PSTN["Customer Phone (PSTN/Mobile)"]
        Twilio["Twilio Voice Gateway"]
        PSTN <-->|Cellular / Landline| Twilio
    end

    subgraph StreamingGateway ["2. Real-time Streaming Gateway"]
        MediaStreamWS["FastAPI Bi-directional WebSocket<br/>(/api/media-stream)"]
        AudioTranscoder["Audio Transcoder<br/>(8kHz &mu;-law &harr; 16kHz Linear PCM)"]
        Twilio <-->|WebSocket Media Streams| MediaStreamWS
        MediaStreamWS <--> AudioTranscoder
    end

    subgraph SpeechIntelligence ["3. Gnani Speech Engine"]
        PrismaSTT["Gnani Prisma STT<br/>(Real-time ASR: Telugu / Hindi / English)"]
        TimbreTTS["Gnani Timbre TTS<br/>(Multilingual Neural Speech Synthesis)"]
        AudioTranscoder -->|16kHz PCM Stream| PrismaSTT
        TimbreTTS -->|Synthesized Audio (WAV/MP3/&mu;-law)| AudioTranscoder
    end

    subgraph OrchestratorLayer ["4. TARA Conversation Orchestrator"]
        StateEngine["Conversation State Engine<br/>(Turn Management & History)"]
        ContextBuilder["Customer & Campaign Context<br/>(Propensity, Intent & DND)"]
        GroqLLM["Groq LLM Engine<br/>(LLaMA 3.3 70B / 3.1 8B)"]
        ToolExecutor["Structured Tool Calling & Actions<br/>(Bookings, Eligibility, DND Opt-Out)"]
        
        PrismaSTT -->|Transcribed Text + Confidence| StateEngine
        StateEngine --> ContextBuilder
        ContextBuilder --> GroqLLM
        GroqLLM -->|Decision & Reasoning| ToolExecutor
        GroqLLM -->|Streaming Response Text| TimbreTTS
    end

    subgraph DataStorage ["5. Enterprise Data & Governance"]
        MongoDB[("MongoDB Atlas Database<br/>(Tenants, Customers, Campaigns, Calls)")]
        Analytics["Campaign & Compliance Analytics"]
        ToolExecutor --> MongoDB
        StateEngine --> MongoDB
        MongoDB --> Analytics
    end

    subgraph FrontendApp ["6. SaaS Experience (React + Vite)"]
        Dashboard["Executive KPI Dashboard"]
        Wizard["5-Step Campaign Wizard"]
        LiveDrawer["Real-time Conversation Drawer"]
        AnalyticsUI["Audience & Conversion Analytics"]
        FrontendApp <-->|REST APIs & JWT| OrchestratorLayer
    end
```

---

## 3. End-to-End Voice Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer (Phone)
    participant Twilio as Twilio PSTN Gateway
    participant Gateway as TARA Media Stream WS
    participant Transcoder as Audio Transcoder
    participant Prisma as Gnani Prisma STT
    participant TARA as Conversation Orchestrator
    participant Groq as Groq LLM
    participant Timbre as Gnani Timbre TTS
    participant DB as MongoDB Atlas

    Note over Customer, DB: 1. Outbound Call Initialization
    TARA->>DB: Query due campaign recipient & verify compliance (DND / Calling Hours)
    TARA->>Twilio: POST /Calls (TwiML with <Connect><Stream>)
    Twilio->>Customer: Dial outbound phone call
    Customer->>Twilio: Answers call

    Note over Customer, DB: 2. WebSocket Media Stream Handshake
    Twilio->>Gateway: WebSocket Upgrade (/api/media-stream)
    Gateway-->>Twilio: 101 Switching Protocols
    Twilio->>Gateway: Event: "start" (CallSid, streamSid)
    Gateway->>TARA: Initialize conversation session (customer propensity, campaign goal)

    Note over Customer, DB: 3. Dynamic Multilingual Greeting
    TARA->>Timbre: Synthesize personalized greeting in selected language
    Timbre-->>Gateway: 8kHz &mu;-law audio payload
    Gateway-->>Twilio: Event: "media" (base64 audio)
    Twilio-->>Customer: Customer hears natural AI voice

    Note over Customer, DB: 4. Real-time Customer Turn (Gnani Prisma STT)
    Customer->>Twilio: Customer speaks ("హా, చెప్పండి, ఈ ఆఫర్ వివరాలు ఏమిటి?")
    Twilio->>Gateway: Streaming &mu;-law audio chunks
    Gateway->>Transcoder: Transcode &mu;-law (8kHz) -> PCM16 (16kHz)
    Transcoder->>Prisma: Stream audio chunks to Gnani Prisma API
    Prisma-->>Gateway: Transcribed text ("హా, చెప్పండి, ఈ ఆఫర్ వివరాలు ఏమిటి?")

    Note over Customer, DB: 5. Conversation Reasoning (Groq LLM)
    Gateway->>TARA: Customer turn text received
    TARA->>Groq: Generate response with system prompt, profile & language rules
    Groq-->>TARA: Structured response ("ఖచ్చితంగా అండీ! మీ అర్హత ప్రకారం...")

    Note over Customer, DB: 6. Speech Synthesis (Gnani Timbre TTS)
    TARA->>Timbre: POST /synthesize (Language: te-IN, Voice: female, Text: ...)
    Timbre-->>Transcoder: Audio stream (WAV/Linear PCM)
    Transcoder->>Gateway: Transcode to &mu;-law (8kHz) base64
    Gateway->>Twilio: Event: "media" stream
    Twilio->>Customer: Customer hears high-quality Telugu speech

    Note over Customer, DB: 7. Post-Call Intelligence & Settlement
    Customer->>Twilio: Hangs up (Call Completed)
    Twilio->>Gateway: Event: "stop"
    Gateway->>TARA: Finalize conversation transcript
    TARA->>DB: Persist transcript, sentiment, lead qualification status, cost & duration
```

---

## 4. Latency Budget & Performance

In conversational Voice AI, conversational fluidness requires an overall **Turn Latency under 1.2 seconds**. TARA 2.0 optimizes each leg of the pipeline:

| Pipeline Stage | Target Latency | P95 Latency | Optimization Mechanism |
| :--- | :--- | :--- | :--- |
| **Twilio Media Stream Buffering** | 40ms | 80ms | 20ms chunk buffering over persistent WebSocket |
| **Audio Transcoding (&mu;-law &harr; PCM)** | 5ms | 12ms | Native Python `audioop` / struct zero-copy processing |
| **Gnani Prisma STT** | 250ms | 400ms | Direct streaming ASR endpoint with VAD (Voice Activity Detection) |
| **TARA Prompt Assembly** | 10ms | 25ms | In-memory customer state caching & template pre-compilation |
| **Groq LLM (Time To First Token)** | 180ms | 280ms | LLaMA-3.3-70b hosted on Groq LPU (Language Processing Units) |
| **Gnani Timbre TTS (First Audio Byte)**| 220ms | 350ms | Sentence-level streaming chunking; synthesize as LLM generates |
| **Total Round-Trip Turn Latency** | **~705ms** | **~1147ms** | **Sub-second interactive response time for natural dialogues** |

---

## 5. Technology Stack Breakdown

### Frontend
- **Framework:** React 18 + Vite (Production bundle: 519 kB minified, gzip: 125 kB)
- **Styling:** Tailwind CSS + Lucide React icons
- **State Management:** Custom React Context (`AuthContext`) + Local storage persistence
- **Routing:** React Router v6 with authenticated and role-based guards

### Backend API & Workers
- **Framework:** Python 3.13 + FastAPI + Uvicorn
- **Asynchronous Loop:** AsyncIO with background scheduling tasks (15s interval)
- **Database Driver:** Motor (Async driver for MongoDB Atlas) with connection pooling
- **Validation:** Pydantic v2 schemas for all payloads and configuration

### Speech & AI Infrastructure
- **Speech-to-Text (STT):** **Gnani Prisma** — High-accuracy automatic speech recognition optimized for Indian accents and regional languages.
- **Text-to-Speech (TTS):** **Gnani Timbre** — Expressive neural voice synthesis supporting regional Indian phonemes.
- **Conversation LLM:** **Groq API** (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) — Ultra-low inference latency.
- **Telephony Provider:** **Twilio Voice API** with Media Streams bi-directional audio protocol.

