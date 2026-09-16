# Deployment Notes

AgentGuard is ready to run as a containerized FastAPI + Next.js + PostgreSQL stack, but this
repository has not been deployed from this workspace.

## Production Environment

Required:

- `AGENTGUARD_DATABASE_URL`
- `AGENTGUARD_AUTH_REQUIRED=true`
- `AGENTGUARD_BOOTSTRAP_API_KEY` for initial administrative access
- `AGENTGUARD_MAX_INGESTION_BYTES`
- `AGENTGUARD_MAX_TRACE_SPANS`
- `AGENTGUARD_API_URL` for the web app server-side API URL

Recommended:

- terminate TLS at a managed ingress or reverse proxy;
- keep provider API keys in a secret manager and store only `api_key_secret_ref` in AgentGuard;
- run Alembic migrations before starting the API container;
- configure database backups and retention policies.

## CI Release Gate

Use the release gate endpoint from any CI system:

```bash
curl -fsS \
  -H "x-agentguard-api-key: $AGENTGUARD_API_KEY" \
  "$AGENTGUARD_API_URL/api/v1/ci/release-gate?baseline_version_id=$BASELINE_VERSION_ID&candidate_version_id=$CANDIDATE_VERSION_ID" \
  | tee agentguard-release-gate.json
```

The response contains `passed`, `exit_code`, and the complete release decision. CI should fail the
job when `passed` is false.

## Not Yet Included

This checkpoint does not deploy the website, provision cloud infrastructure, or install a hosted
secret manager. Those steps should be done after choosing the target platform.
