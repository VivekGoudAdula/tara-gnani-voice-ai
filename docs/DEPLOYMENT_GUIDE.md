# TARA — Production Deployment & Configuration Guide

This guide describes how to deploy, configure, and operate the **TARA (Targeted Acquisition & Reach Agent)** platform in local development, staging, and enterprise cloud production environments.

---

## 1. Prerequisites & System Requirements

### Hardware & Environment
- **Operating System:** Linux (Ubuntu 22.04 LTS recommended) / macOS / Windows 11
- **Python:** Version 3.11, 3.12, or 3.13
- **Node.js:** Version 18.x or 20.x LTS with `npm`
- **MongoDB:** MongoDB Atlas cluster (v6.0+) or self-hosted MongoDB with replica set enabled (for transaction support)

### External Service Accounts & Credentials
1. **Gnani AI Services:**
   - Gnani API Key & Customer ID for **Prisma STT**
   - Gnani API Key for **Timbre TTS**
2. **Twilio Telephony:**
   - Account SID & Auth Token
   - An active Twilio Phone Number capable of Voice & Media Streams
3. **Groq Cloud:**
   - Groq API Key (for LLaMA-3.3-70b / LLaMA-3.1-8b low-latency inference)
4. **Public Hostname / Ingress (for Twilio Webhooks & Media Streams):**
   - A public HTTPS/WSS URL (e.g., domain with SSL or `ngrok` tunnel for development)

---

## 2. Environment Variables Configuration

Create a `.env` file inside the `backend/` directory based on `backend/.env.example`.

### `backend/.env` Configuration Template:

```ini
# ==============================================================================
# TARA — Application & Server Settings
# ==============================================================================
APP_NAME="TARA"
APP_ENV="production"
DEBUG=false
PORT=8000
HOST="0.0.0.0"
SECRET_KEY="your-super-secret-jwt-signing-key-here-min-32-chars"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Base URL accessible by external services (Twilio webhooks & media stream)
BASE_URL="https://api.yourdomain.com"

# ==============================================================================
# MongoDB Database Configuration
# ==============================================================================
MONGODB_URL="mongodb+srv://username:password@cluster.example.mongodb.net/?retryWrites=true&w=majority"
MONGODB_DB_NAME="tara"

# ==============================================================================
# Gnani Voice AI Services (STT & TTS)
# ==============================================================================
GNANI_API_KEY="your-gnani-api-key"
GNANI_CUSTOMER_ID="your-gnani-customer-id"
GNANI_PRISMA_STT_URL="https://prisma.gnani.ai/v1/stream"
GNANI_TIMBRE_TTS_URL="https://timbre.gnani.ai/v1/synthesize"
GNANI_DEFAULT_LANGUAGE="te-IN"

# ==============================================================================
# Telephony Provider (Twilio Voice & Media Streams)
# ==============================================================================
VOICE_PROVIDER="twilio_gnani"
TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN="your-twilio-auth-token"
TWILIO_PHONE_NUMBER="+1xxxxxxxxxx"
TWILIO_STATUS_CALLBACK_URL="https://api.yourdomain.com/api/webhooks/twilio/status"

# ==============================================================================
# Conversation Intelligence (Groq LLM)
# ==============================================================================
GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
GROQ_MODEL="llama-3.3-70b-versatile"
LLM_TEMPERATURE=0.2

# ==============================================================================
# Campaign & Compliance Settings
# ==============================================================================
CALL_WINDOW_START="09:00"
CALL_WINDOW_END="21:00"
CALL_WINDOW_TIMEZONE="Asia/Kolkata"
MAX_CONCURRENT_CALLS=10
DEFAULT_CALL_RETRY_LIMIT=3
DEFAULT_CALL_RETRY_INTERVAL_MINUTES=60
```

---

## 3. Local Development Setup

### Backend Setup:
```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate a virtual environment
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

# 3. Install production and test dependencies
pip install -r requirements.txt

# 4. Start the FastAPI development server with auto-reload
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend server starts on `http://localhost:8000`.
- API Documentation (Swagger): `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`
- Provider Status: `http://localhost:8000/api/workspace/providers-health`

### Frontend Setup:
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node dependencies
npm install

# 3. Start the Vite development server
npm run dev
```

The React frontend starts on `http://localhost:5173`.

---

## 4. Twilio Telephony & Webhook Configuration

Twilio requires a public HTTPS/WSS endpoint to route incoming calls and stream audio.

### Using ngrok for Local Development:
```bash
ngrok http 8000
```
Copy the Forwarding URL (e.g., `https://abc1234.ngrok-free.app`). Update `BASE_URL` and `TWILIO_STATUS_CALLBACK_URL` in `backend/.env`.

### Configuring Twilio Console:
1. Log in to **Twilio Console** $\rightarrow$ **Phone Numbers** $\rightarrow$ **Manage Active Numbers**.
2. Select your Twilio phone number.
3. Under **Voice & Fax**:
   - Set **A CALL COMES IN** to: `Webhook`
   - URL: `https://your-public-url.com/api/media-stream/twiml`
   - HTTP Method: `POST`
   - Set **STATUS CALLBACK URL** to: `https://your-public-url.com/api/webhooks/twilio/status`
   - HTTP Method: `POST`
4. Save configuration.

---

## 5. Production Cloud Deployment (Docker & Linux VM)

### Option A: Standard Systemd Service on Ubuntu Linux VM

#### 1. Backend Systemd Service (`/etc/systemd/system/tara-backend.service`):
```ini
[Unit]
Description=TARA FastAPI Application
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/tara/backend
EnvironmentFile=/opt/tara/backend/.env
ExecStart=/opt/tara/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tara-backend
```

#### 2. Frontend Production Build & Nginx Hosting:
```bash
# Build production bundle
cd /opt/tara/frontend
npm run build

# Copy artifacts to web root
sudo mkdir -p /var/www/tara
sudo cp -r dist/* /var/www/tara/
```

#### 3. Nginx Reverse Proxy Configuration (`/etc/nginx/sites-available/tara`):
```nginx
server {
    listen 80;
    server_name tara.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tara.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/tara.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tara.yourdomain.com/privkey.pem;

    # Frontend Single Page App
    location / {
        root /var/www/tara;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend REST APIs
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Bi-directional Twilio WebSockets
    location /api/media-stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

---

## 6. Verification & Smoke Testing

After deployment, run the following health checks:

1. **Verify Backend Health:**
   ```bash
   curl -s https://tara.yourdomain.com/health | jq
   # Expected output: {"status": "ok", "app": "TARA", "database": "connected"}
   ```

2. **Verify Provider Health:**
   ```bash
   curl -s https://tara.yourdomain.com/api/workspace/providers-health | jq
   # Verifies Twilio, Gnani Prisma STT, Gnani Timbre TTS, and Groq LLM statuses.
   ```

3. **Execute In-Flight Campaign Verification:**
   Launch a test 1-recipient campaign from the UI or run:
   ```bash
   python backend/scripts/manual_test_call.py --to "+919876543210" --campaign-id "test-campaign"
   ```

