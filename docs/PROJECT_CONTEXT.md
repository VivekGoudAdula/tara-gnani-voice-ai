# PROJECT CONTEXT: TARA

## 0. Development & Submission Context
- **Target Submission:** Gnani AI Internship Challenge.
- **Project Name:** TARA (Targeted Acquisition & Reach Agent).
- **Core Directive:** Deliver a stable, fully functional, properly branded, deployed and demonstrable Gnani-powered Voice AI platform.
- **Speech Technologies:** Gnani Prisma (STT) + Gnani Timbre (TTS).
- **Telephony & Transport:** Twilio Voice + Twilio Media Streams (8kHz $\mu$-law bi-directional WebSocket streaming).
- **Conversation Intelligence:** Groq LLM (sub-250ms streaming conversational reasoning).

## 1. What We Are Building
TARA = Targeted Acquisition & Reach Agent. An enterprise multilingual Voice AI customer acquisition and engagement SaaS platform designed for Indian banks and financial institutions.
It scores customers and leads for financial product fit (propensity intelligence), manages targeted voice campaigns, configures persona and policy parameters, conducts human-like conversations across Indian languages (Telugu, Hindi, Indian English), and updates CRM customer profiles and campaign outcomes in real time.

## 2. Technology Architecture
```
Twilio Voice (PSTN)
       ↕ (8kHz mulaw bi-directional audio)
TARA FastAPI Gateway (/api/voice/stream)
       ↕ (audio chunks / text)
Gnani Prisma (Streaming Speech-to-Text)
       ↕ (user utterance)
TARA Intelligent Agent & Conversation Orchestrator
       ↕ (reasoning & context)
Groq LLM Engine (Fast Inference)
       ↕ (agent reply text)
Gnani Timbre (Streaming Text-to-Speech)
       ↕ (synthesized audio stream)
Twilio Voice (Playback to Subscriber)
```

## 3. Technology Stack — Non-Negotiable Core
- **Frontend:** React 18, Vite, Tailwind CSS, Lucide icons.
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, Motor (Async MongoDB driver).
- **Database:** MongoDB Atlas (collections: `tenants`, `users`, `products`, `customers`, `leads`, `product_matches`, `campaigns`, `campaign_configs`, `campaign_recipients`, `communications`, `audit_log`, `webhook_events`, `scoring_runs`).
- **Telephony Provider:** Twilio Outbound Voice & Media Streams.
- **Speech Recognition:** Gnani Prisma v3.0 WebSocket STT (`te-IN`, `hi-IN`, `en-IN`).
- **Speech Synthesis:** Gnani Timbre v2.5 Indian Neural TTS (`Nalini` / Indian Female voice persona).
- **LLM Reasoning:** Groq LLM (`qwen/qwen3.8-27b`).
- **Compliance & Security:** Multi-tenant row isolation via JWT, TRAI calling-hour compliance (09:00–21:00 IST), explicit consent, DND screening, and frequency capping.
