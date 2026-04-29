# Deployment Guide: Vercel + Render

This lite project is split into three deployable parts:

- Frontend: `Frontend/Document Processing Intelligent Agent` -> Vercel
- Backend API: `Backend` -> Render Docker Web Service
- Algorithm API: `Algorithm` -> Render Docker Web Service

## 1. Repository

Push this lite folder to a Git repository. Do not commit real secrets.

The large model file is about 480 MB. A normal GitHub repository will reject files over 100 MB. Use one of these approaches:

1. Git LFS for `Algorithm/model_6_focus/model.safetensors`.
2. A private model store and modify the Algorithm Dockerfile to download the model during build/startup.
3. Build and push a Docker image to a registry, then deploy that image on Render.

For the first deployment, Git LFS is usually the quickest path.

## 2. Render: algorithm service

Create a Render Docker Web Service from the `Algorithm` root directory, or use `render.yaml` as a Blueprint.

Important settings:

- Root Directory: `Algorithm`
- Runtime: Docker
- Health Check Path: `/health`
- Instance plan: avoid the free plan for this service. The model plus Torch/Transformers needs more memory than a tiny instance usually provides.

Environment variables:

- `SERVICE_TOKEN`: choose a shared secret, for example a long random string.
- `TESSERACT_CMD=/usr/bin/tesseract`
- `DEBUG_MODE=false`

After deployment, copy the public URL, for example:

`https://docs-agent-algorithm.onrender.com`

## 3. Render: backend service

Create a Render Docker Web Service from the `Backend` root directory, or use `render.yaml` as a Blueprint.

Important settings:

- Root Directory: `Backend`
- Runtime: Docker
- Health Check Path: `/api/health`
- Instance plan: starter or higher.

Environment variables:

- `ALGORITHM_API_URL`: the algorithm service URL from step 2.
- `ALGORITHM_SERVICE_TOKEN`: exactly the same value as algorithm `SERVICE_TOKEN`.
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `SECRET_KEY`
- `DEEPSEEK_API_KEY` if chat/LLM cleanup is used.

Use a managed PostgreSQL database. The current code expects separate PostgreSQL fields rather than a single `DATABASE_URL`.

After deployment, test:

`https://YOUR-BACKEND-SERVICE.onrender.com/api/health`

## 4. Vercel: frontend

Create a Vercel Project from this repository and set the Root Directory to:

`Frontend/Document Processing Intelligent Agent`

Build settings:

- Framework: Vite
- Install Command: `npm ci`
- Build Command: `npm run build`
- Output Directory: `dist`

Environment variables:

- `VITE_API_URL=https://YOUR-BACKEND-SERVICE.onrender.com`
- `VITE_SSE_URL=https://YOUR-BACKEND-SERVICE.onrender.com/api/agent/stream`
- `VITE_SSE_TASK_PARAM=processId`

Deploy the frontend after the backend URL is known.

## 5. Recommended deployment order

1. Deploy Algorithm on Render.
2. Deploy Backend on Render and point it to Algorithm.
3. Deploy Frontend on Vercel and point it to Backend.
4. Upload a small PDF and watch SSE progress.

## 6. Known caveats

- The algorithm service currently processes only the first page of a PDF.
- Field confidence is currently hardcoded in the extraction layer.
- The backend currently expects PostgreSQL split variables, not `DATABASE_URL`.
- Render/Vercel URLs are unknown until services are created, so placeholders must be replaced after the first deployment.
