# Render Deploy

This repo is configured to deploy to Render as a single web service.

## What gets deployed

- FastAPI serves the API under `/api`.
- The Vite frontend is built during Render's build step.
- The built frontend in `web/dist` is served by the FastAPI app in production.
- New sessions start on a public demo repository, set with `TRACE_REPO_PATH`. It is cloned and analysed on a session's first request.

## Blueprint

The root `render.yaml` provisions one Python web service with these commands:

- Build: `pip install -e ".[web]" && cd web && npm ci && npm run build`
- Start: `uvicorn trace_engine.api.server:create_app --factory --host 0.0.0.0 --port $PORT`

It sets `TRACE_REPO_PATH=https://github.com/miguelgrinberg/flasky.git` so new sessions start on the same lightweight public repository in production. It also pins Python 3.11.11, selects the free plan in the Oregon region and redeploys on every commit.

The editable install (`pip install -e`) matters: the server looks for `web/dist` next to the source tree.

## Deploy steps

1. Push this repository to GitHub, GitLab, or Bitbucket.
2. In Render, create a new Blueprint instance from the repository.
3. Render will detect `render.yaml` and create the `repolens` web service.
4. After the first deploy completes, open the generated Render URL.

## Notes

- The health check is `/api/health`, which needs no session header.
- The API has no authentication, and a session can load any git URL the server can reach or any directory on the server's own filesystem. Symlinks in a repository are skipped and code snippets are read only from inside the repository being analysed, but treat a deployment as a single-purpose public demo and keep nothing else of value on the instance.
- The built front end is served from the same origin as the API, so `TRACE_CORS_ORIGINS` does not need to be set.
- The service binds to `0.0.0.0:$PORT`, which matches Render's web service requirements.
- The frontend uses `/api` by default outside local Vite development, so no extra API base URL is required for this single-service deployment.
- The startup repository is public, so users do not need your git credentials or deploy-time repository access keys.
- To enable Ask Repo with OpenAI, set `OPENAI_API_KEY` as a secret environment variable in Render. The blueprint includes the key name but does not store the secret value in the repository.
- `TRACE_LLM_MODEL` defaults to `gpt-4.1-mini` and can be overridden in Render if you want a different OpenAI-compatible model.
