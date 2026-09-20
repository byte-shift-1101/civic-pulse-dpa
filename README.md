# CivicPulse — Smart Civic Complaint & Issue Management System

CivicPulse is an end-to-end multi-channel civic complaint and municipal operations platform built for DPA Hackathon 2026. It connects citizens, municipal operators, and field workers into a single issue-resolution lifecycle.

---

## 🚀 Features

- **Multi-Channel Intake**: Progressive Web App (PWA) for citizens and automated Telephony Voice Helpline Simulator.
- **AI-Powered Triaging**: Automatic issue categorization, 1–2 sentence operational summarization, and address/landmark extraction via Groq API (with intelligent local NLP fallback).
- **Rule-Based Prioritization**: Priority score (0–100) computed dynamically using complaint age, issue category weight, nearby duplicate volume, citizen upvotes, and geographic cluster density.
- **Geospatial Intelligence**: Proximity search, interactive Leaflet map, density clustering, and NYC 311-style dataset pre-seeded for Bengaluru.
- **Strict Municipal Lifecycle**: 4-stage lifecycle state machine (`NEW` → `ASSIGNED` → `IN_PROGRESS` → `RESOLVED`) with audit trail logging.
- **Admin Dashboard**: Regional heatmaps, SLA tracking, category breakdown, priority queue, and workforce management.

---

## 🏗️ Architecture & Tech Stack

- **Backend**: Python 3.11+, FastAPI, Pydantic, Uvicorn
- **Database**: SQLite with spatial indexing and pre-seeded demo data
- **AI / LLM**: Groq API (`LLMProvider`) with fallback rule parser
- **Frontend**: Embedded Single Page Application / PWA (Tailwind CSS, Leaflet JS, Lucide Icons)

---

## 🛠️ Quick Start

### 1. Prerequisites
Ensure Python 3.11+ is installed.

### 2. Install Dependencies
```bash
pip install fastapi uvicorn pydantic httpx
```

### 3. Run Application
```bash
python run.py
```

Access the application surfaces at:
- **Progressive Web App (PWA)**: [http://localhost:8000](http://localhost:8000)
- **OpenAPI Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

*(Optional) To enable live Groq LLM inference, set environment variable `GROQ_API_KEY`:*
```bash
$env:GROQ_API_KEY="your_groq_api_key"
```

---

## 📡 API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/request-otp` | Request OTP for phone verification |
| `POST` | `/api/v1/auth/verify-otp` | Verify OTP and authenticate user |
| `GET` | `/api/v1/categories` | List active civic complaint categories |
| `GET` | `/api/v1/departments` | List municipal departments |
| `POST` | `/api/v1/complaints` | Submit a new complaint (AI analyzed & prioritized) |
| `GET` | `/api/v1/complaints` | Query/filter complaints feed |
| `POST` | `/api/v1/complaints/{id}/upvote` | Upvote a public complaint |
| `POST` | `/api/v1/admin/complaints/{id}/assign` | Assign department and worker |
| `POST` | `/api/v1/admin/complaints/{id}/status` | Update lifecycle state (`ASSIGNED`, `IN_PROGRESS`, `RESOLVED`) |
| `GET` | `/api/v1/admin/analytics` | Analytics dashboard metrics |
| `POST` | `/api/v1/webhooks/voice` | Voice helpline helpline transcript intake |

---

## 🧪 Integration Testing

Run the automated end-to-end integration test suite:
```bash
python test_integration.py
```
