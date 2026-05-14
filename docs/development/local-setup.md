# Local Setup Guide

Follow these onboarding instructions to configure the **AI Dashboard** application for local debugging.

---

## 1. System Prerequisites

Ensure host machines have the following toolchains installed:
- **Python**: Version `3.13+` managed via **`uv`**.
- **Node.js**: Version `18+` leveraging **`pnpm`**.
- **Docker Desktop**: Required to host local session storage instances.

---

## 2. Bootstrapping Steps

### A. Clone Repository & Setup Environments
```bash
git clone https://github.com/Hari31416/gen-dashboard.git
cd gen-dashboard

# Establish local environment configurations from sample file baselines
cp backend/.env.example backend/.env
```

### B. Automated Dependencies Bootstrapping
The project root provides developer experience shortcuts using the Makefile:

```bash
# Installs backend packages via `uv` and frontend node_modules using `pnpm`
make setup
```

---

## 3. Launching Application Services

### A. Start MongoDB Session Subsystem
```bash
# Launches local MongoDB engine instance via docker-compose
make up
```

### B. Run API Server and Frontend Client Concurrent Dev Servers
```bash
# Concurrently boots FastAPI gateway (8000) and React UI workspace (5173)
make start
```

Once running, navigate to `http://localhost:5173` to interact with the platform.
