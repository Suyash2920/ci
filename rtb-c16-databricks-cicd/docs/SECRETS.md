# Secrets & Variables Reference

> **Rule:** nothing in this table may ever appear in a committed file.
> `gitleaks`, `bandit` and the workflow validator all fail the build if it does.

## Repository secrets
**Settings → Secrets and variables → Actions → Secrets → New repository secret**

| Name | Required | Where to get it | Used by |
| --- | --- | --- | --- |
| `DATABRICKS_HOST` | **yes** | Workspace URL, e.g. `https://dbc-xxxxxxxx-xxxx.cloud.databricks.com` (no trailing slash) | CI validate + both CD pipelines |
| `DATABRICKS_TOKEN` | **yes** | Workspace → avatar → **Settings → Developer → Access tokens → Generate new token** | CI validate + both CD pipelines |
| `DATABRICKS_WAREHOUSE_ID` | **yes** | **SQL Warehouses → Serverless Starter Warehouse → Connection details → HTTP path**, last segment | Post-deploy smoke tests |
| `SONAR_TOKEN` | optional* | SonarCloud/SonarQube → My Account → Security | CI (`test` job) |
| `SONAR_HOST_URL` | optional* | `https://sonarcloud.io` or your server URL | CI (`test` job) |
| `OPENAI_API_KEY` | optional | <https://platform.openai.com/api-keys> | All GenAI steps |
| `TEAMS_WEBHOOK_URL` | optional | Teams channel → Connectors → Incoming Webhook | `CD — PROD` notify job |

\* If unset, the Sonar steps are skipped and CI still passes.
`GITHUB_TOKEN` is injected by GitHub automatically — the GenAI scripts fall back
to **GitHub Models** with it, so AI works with **zero** paid keys.

## Environments

The CD workflows call a reusable workflow with `secrets: inherit`, and the deploy
job declares `environment: qa` / `environment: prod`. That means:

- **Databricks Free Edition (one workspace):** keep the three `DATABRICKS_*`
  values as **repository** secrets. The environments still provide the approval
  gate and the deployment-branch restriction; isolation comes from the catalog.
- **Paid tier (separate workspaces):** override `DATABRICKS_HOST`,
  `DATABRICKS_TOKEN` and `DATABRICKS_WAREHOUSE_ID` as **environment** secrets on
  `prod`. Environment secrets take precedence — **no workflow change is needed**.

Create the environments under **Settings → Environments**:

| Environment | Protection rules |
| --- | --- |
| `qa` | Deployment branch rule: `qa` only |
| `prod` | Required reviewers (1+), wait timer 5 min, deployment branch rule: `main` only |

## Quick CLI setup

```bash
gh secret set DATABRICKS_HOST          --body "https://dbc-xxxxxxxx-xxxx.cloud.databricks.com"
gh secret set DATABRICKS_TOKEN         # paste the PAT when prompted
gh secret set DATABRICKS_WAREHOUSE_ID  --body "<warehouse id>"

gh secret set SONAR_TOKEN
gh secret set SONAR_HOST_URL --body "https://sonarcloud.io"

# Optional
gh secret set OPENAI_API_KEY
gh secret set TEAMS_WEBHOOK_URL
```

## Token hygiene

- Use the **shortest viable expiry** on the Databricks PAT (90 days) and diarise rotation.
- Workflows declare least-privilege `permissions:` at the top; only the jobs that
  need `pull-requests: write` or `contents: write` get it.
- `scripts/genai/ai_client.py` redacts credential-shaped strings before any text
  is sent to a model provider.
- Never pass a secret as a composite-action `input` — inputs are logged.
  This repo passes them as `env` only.
