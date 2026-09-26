## What & why

<!-- One paragraph. Link the ticket. -->

## Target branch

- [ ] `feature/*` -> `qa` (functional change, will deploy to the **qa** catalog)
- [ ] `qa` -> `main` (promotion, will deploy to the **prod** catalog)
- [ ] `hotfix/*` -> `main` (emergency; back-merge to `qa` is mandatory)

## Checklist

- [ ] Unit tests added or updated for every changed behaviour
- [ ] `pytest`, `ruff`, `black` pass locally
- [ ] `databricks bundle validate --target qa` and `--target prod` pass
- [ ] No credentials, tokens, hosts or PII added to the repo
- [ ] QA/PROD config changes applied to **both** `src/retail_etl/conf/qa.yml` and `prod.yml`
- [ ] AI review comment read and either actioned or explicitly dismissed below

## AI review disposition

<!-- AI output is advisory. Summarise what you accepted/rejected and why. -->

## Rollback plan

<!-- e.g. revert this commit and re-run CD, or restore the Delta table with RESTORE VERSION AS OF -->
