# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This project is split into two independently runnable apps:

- `Backend/` — FastAPI backend for uploads, SSE, algorithm callbacks, compliance checks, auth, and task/chat APIs.
- `Frontend/Document Processing Intelligent Agent/` — React + TypeScript + Vite frontend for the DocSmart UI.

There is also an external algorithm service referenced by Docker Compose at `../Algorithm`; it is not part of this repository.

## Common commands

### Frontend (`Frontend/Document Processing Intelligent Agent`)

Install dependencies:

```bash
npm ci
```

Run the dev server on port 5173:

```bash
npm run dev
```

Run the Vite mock mode:

```bash
npm run mock
```

Build production assets:

```bash
npm run build
```

Lint the frontend:

```bash
npm run lint
```

Preview the production build:

```bash
npm run preview
```

### Backend (`Backend`)

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the backend locally with auto-reload:

```bash
python -m uvicorn agent.main:app --host 127.0.0.1 --port 8000 --reload
```

Run the backend health check helper:

```bash
python check_health.py
```

Run all backend tests discovered by pytest:

```bash
python -m pytest
```

Run a single backend test file:

```bash
python -m pytest test_db.py
```

Useful one-off backend diagnostic scripts in `Backend/`:

```bash
python test_connection.py
python test_connection_8002.py
python test_db.py
python test_deepseek.py
```

### Full stack with Docker

From `Backend/`:

```bash
docker compose up --build
```

This starts:

- PostgreSQL on `localhost:5432`
- FastAPI backend on `localhost:8000`
- External algorithm service on `localhost:8001`
- Frontend on `localhost:5173`

## Environment and runtime assumptions

- Backend settings are loaded from `Backend/.env` via `agent/config.py`.
- Frontend dev mode assumes the backend is on `http://localhost:8000`.
- Vite proxies `/api` to the backend; SSE requests also go through this path.
- The frontend currently disables MSW in `src/main.tsx` and defaults to the real backend.
- The frontend dev flow uses a fixed bearer token in `src/config.ts` / `App.tsx`; backend routes still use auth dependencies.

## High-level architecture

### Backend request flow

The main FastAPI app is `Backend/agent/main.py`.

It wires together these main router groups:

- `api/file.py` — upload entrypoint
- `api/sse.py` — SSE stream subscription endpoint
- `api/algorithm_in.py` — algorithm callback and progress endpoints
- `api/compliance.py` — compliance APIs
- `api/action.py` — user action endpoint for agent workflows
- `api/auth.py` — authentication
- `api/task.py` — task management
- `api/chat.py` — chat/demo reasoning flow
- `api/smart_doc.py` — alternate direct OCR + DeepSeek invoice path

The primary production-style document flow is:

1. Frontend uploads a file to `POST /api/file/upload`.
2. `api/file.py` creates a `processId`, saves the file under `Backend/uploads/<processId>/`, and initializes an SSE queue.
3. The backend emits upload/process events through `agent/utils/sse.py`.
4. `agent/service/algorithm_client.py` sends the file metadata to the external algorithm service on port 8001.
5. The external service responds asynchronously by calling back into `POST /api/algorithm/callback` and optionally `/api/algorithm/progress`.
6. `api/algorithm_in.py` saves extracted fields, emits `model.process.progress` / `model.extract.complete`, and then triggers compliance checks.
7. Compliance results are emitted back to the frontend over SSE and persisted through the backend service/database layer.

### SSE/event model

The backend is event-driven from the frontend’s point of view.

- `agent/utils/sse.py` keeps one asyncio queue per `processId`.
- `GET /api/agent/stream?processId=...` subscribes the browser to that queue.
- The frontend listens for typed AG-UI-style events such as upload progress, model extraction completion, compliance completion, heartbeat, and task errors.

This event stream is the backbone of the UI; when changing backend workflow stages, update the event payloads carefully so they still map onto frontend expectations.

### Frontend architecture

The frontend is a single-page React app whose orchestration is currently centered in `src/App.tsx`.

Key frontend responsibilities:

- file upload and chat message orchestration
- SSE connection lifecycle and reconnect behavior
- normalization of incoming backend events into UI-friendly event types
- driving the chat-style progress/result UI from the event stream

Key files:

- `src/main.tsx` — app bootstrap; explicitly disables mock workers and renders the real app
- `src/config.ts` — derives API base URL, SSE URL, auth headers, and dev defaults
- `src/api/http.ts` — lightweight fetch wrapper for backend POSTs
- `src/App.tsx` — upload/chat/SSE orchestration layer and event-to-UI mapping

### Data and persistence

- SQLAlchemy session/config lives in `agent/db/session.py` and `agent/config.py`.
- Database initialization happens during FastAPI startup in `agent/main.py`.
- CRUD helpers live under `agent/db/crud/`.
- Uploaded files are stored on disk under `Backend/uploads/`.

### LangGraph status

There is a LangGraph-based workflow definition in `agent/langgraph/`, but the live upload path currently does not execute it directly.

`api/file.py` has LangGraph-related imports/state setup commented out and instead uses the external algorithm service + callback path as the actual runtime flow. Treat `agent/langgraph/` as design intent / partial implementation unless you verify that a route is actively using it.

### Alternate AI path

`api/smart_doc.py` and `ai_engine/ocr_processor.py` implement a separate direct pipeline:

- PDF upload
- Tesseract OCR
- DeepSeek extraction
- DB save

This is separate from the main callback-driven upload flow and should not be confused with the algorithm-service path.

### Incomplete or placeholder AI components

The repository contains early-stage AI plumbing that is not the main runtime path:

- `agent/service/embedding_service.py` uses a hash-based placeholder embedding
- `agent/service/vector_store.py` provides pgvector scaffolding
- `agent/api/chat.py` is a demo-style SSE reasoning flow, not a full business chat agent

Verify these paths before building on them.

## Implementation notes for future edits

- Prefer tracing changes from `api/file.py` → `service/algorithm_client.py` → `api/algorithm_in.py` → compliance services when debugging end-to-end document processing.
- When frontend progress looks wrong, inspect event names and payload shapes before changing rendering logic; most UI state is derived from SSE events rather than direct API responses.
- If Docker Compose is involved, remember that the algorithm service is expected in a sibling `../Algorithm` directory and is not available from this repository alone.
- Ignore archive leftovers such as `Frontend/__MACOSX`; they are not part of the application runtime.
