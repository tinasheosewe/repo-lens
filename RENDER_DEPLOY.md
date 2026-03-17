# Render Deploy

This repo is configured to deploy to Render as a single web service.

## What gets deployed

- FastAPI serves the API under `/api`.
- The Vite frontend is built during Render's build step.
- The built frontend in `web/dist` is served by the FastAPI app in production.
- The deployed app preloads the checked-out RepoLens repository for analysis from the local filesystem.

## Blueprint

The root `render.yaml` provisions one Python web service with these commands:

- Build: `pip install -e ".[web]" && cd web && npm ci && npm run build`
- Start: `uvicorn trace_engine.api.server:create_app --factory --host 0.0.0.0 --port $PORT`

It also sets `TRACE_REPO_PATH=.` so the app analyzes the repository already present in the Render build workspace.

## Deploy steps

1. Push this repository to GitHub, GitLab, or Bitbucket.
2. In Render, create a new Blueprint instance from the repository.
3. Render will detect `render.yaml` and create the `repolens` web service.
4. After the first deploy completes, open the generated Render URL.

## Notes

- The health check is `/api/status`.
- The service binds to `0.0.0.0:$PORT`, which matches Render's web service requirements.
- The frontend uses `/api` by default outside local Vite development, so no extra API base URL is required for this single-service deployment.
- No startup clone is required in Render, so other users do not need your git credentials or deploy-time repository access keys.