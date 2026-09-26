# SonarQube Setup — Step by Step (for first-time users)

You have two options. Pick **one**.

| Option | Cost | Best for |
| --- | --- | --- |
| **A. SonarQube Cloud** (formerly SonarCloud) | Free for public repos | Fastest; nothing to host. **Recommended.** |
| **B. Self-hosted SonarQube Community** via Docker | Free | Private repos, offline demo |

Both options use the exact same `sonar-project.properties` file and the same two
GitHub Secrets: `SONAR_TOKEN` and `SONAR_HOST_URL`.

---

## What SonarQube actually does here

The CI workflow already produces two report files:

- `coverage.xml` — line/branch coverage from `pytest --cov`
- `test-results/junit.xml` — test results

SonarQube reads those, adds its own static analysis (bugs, code smells, security
hotspots, duplication) and then applies a **Quality Gate**. If the gate fails,
the `SonarQube quality gate` step fails, which fails CI, which blocks the PR.

---

## Option A — SonarQube Cloud (recommended)

### A1. Create the account
1. Go to <https://sonarcloud.io> and click **Log in** → **With GitHub**.
2. Authorise the SonarCloud GitHub App.

### A2. Create the organisation
1. Click the **+** in the top-right → **Analyze new project**.
2. If prompted, **Import an organization from GitHub**, pick your GitHub account/org.
3. Choose the **Free plan** (public repositories).
4. Note the **Organization Key** (e.g. `gajendra-goswami`). You will need it.

### A3. Create the project
1. On the **Analyze projects** screen, select your repository → **Set Up**.
2. Note the **Project Key** (usually `<org>_<repo>`).
3. Choose **Previous version** as the New Code definition (fine for this project).

### A4. Choose the analysis method
1. Open the project → **Administration** → **Analysis Method**.
2. **Turn OFF** "Automatic Analysis". This is critical — automatic analysis
   ignores your `coverage.xml`.
3. Select **GitHub Actions**. SonarCloud shows you a `SONAR_TOKEN`.

### A5. Update `sonar-project.properties`
```properties
sonar.projectKey=<paste your Project Key>
sonar.organization=<paste your Organization Key>
```
(Uncomment the `sonar.organization` line.)

### A6. Add the GitHub Secrets
In GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
| --- | --- |
| `SONAR_TOKEN` | the token from step A4 |
| `SONAR_HOST_URL` | `https://sonarcloud.io` |

### A7. Run it
Push a commit or open a PR. The `Unit tests & coverage` job runs
`SonarSource/sonarqube-scan-action@v4`, then the quality gate action.
Results appear on the SonarCloud project page and as a check on the PR.

---

## Option B — Self-hosted SonarQube Community (Docker)

Use this if the repo is private or you want a fully local demo.

### B1. Start the server
```bash
docker run -d --name sonarqube \
  -p 9000:9000 \
  -v sonarqube_data:/opt/sonarqube/data \
  -v sonarqube_logs:/opt/sonarqube/logs \
  -v sonarqube_ext:/opt/sonarqube/extensions \
  sonarqube:community
```
Wait ~2 minutes, then open <http://localhost:9000>.

> On Linux you may need: `sudo sysctl -w vm.max_map_count=524288`

### B2. First login
- Username `admin`, password `admin`. You are forced to change the password. Do it.

### B3. Create the project
1. **Create Project → Manually**.
2. Project display name: `RTB C16 Databricks CI/CD`
3. Project key: `rtb-c16-databricks-cicd` (must match `sonar.projectKey`).
4. **Set Up** → **Locally** → **Generate** a token → copy it.

### B4. Try a scan from your laptop first
```bash
# from the project root, after running the tests once
pytest --cov --cov-report=xml:coverage.xml --junitxml=test-results/junit.xml

docker run --rm \
  -e SONAR_HOST_URL="http://host.docker.internal:9000" \
  -e SONAR_TOKEN="<your token>" \
  -v "$PWD:/usr/src" \
  sonarsource/sonar-scanner-cli
```
Open <http://localhost:9000> and confirm you see coverage > 0%.

### B5. Make the server reachable from GitHub Actions
GitHub-hosted runners cannot reach `localhost`. Either:
- expose the server publicly (e.g. `ngrok http 9000`, or host it on a VM with a public URL), **or**
- register a **self-hosted runner** on the same machine and change `runs-on: ubuntu-latest`
  to `runs-on: self-hosted` in the `test` job.

### B6. Add the GitHub Secrets
| Name | Value |
| --- | --- |
| `SONAR_TOKEN` | token from step B3 |
| `SONAR_HOST_URL` | e.g. `https://abc123.ngrok-free.app` or `http://<vm-ip>:9000` |

---

## Configuring the Quality Gate

1. In Sonar: **Quality Gates → Create** → name it `Databricks ETL Gate`.
2. Add conditions **on New Code**:

| Metric | Operator | Value |
| --- | --- | --- |
| Coverage | is less than | `80%` |
| Duplicated Lines (%) | is greater than | `3%` |
| Security Hotspots Reviewed | is less than | `100%` |
| Maintainability Rating | is worse than | `A` |
| Reliability Rating | is worse than | `A` |
| Security Rating | is worse than | `A` |

3. **Projects → Select your project** to attach the gate.

The repo already enforces `fail_under = 80` locally in `pyproject.toml`, so the
local and server thresholds agree.

---

## Enforcing it on pull requests

1. GitHub → **Settings → Branches → Add branch ruleset** for `qa` and `main`.
2. Enable **Require status checks to pass** and select:
   - `Lint & static analysis`
   - `Security scanning`
   - `Unit tests & coverage`   ← this is the job that contains the Sonar gate
   - `Validate Databricks bundle (qa)` / `(prod)`
3. Enable **Require a pull request before merging** with at least 1 approval.

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Coverage shows 0% | `coverage.xml` missing or paths wrong. Ensure `pytest --cov-report=xml:coverage.xml` ran **before** the scan step, in the **same** job. |
| `Project not found` | `sonar.projectKey` in `sonar-project.properties` ≠ the key in the Sonar UI. |
| `You are running CI analysis while Automatic Analysis is enabled` | Turn off Automatic Analysis (step A4). |
| `Not authorized` / 401 | `SONAR_TOKEN` expired or wrong. Regenerate in **My Account → Security**. |
| Quality gate step hangs then times out | The server has not finished background processing; increase `timeout-minutes`. |
| New Code coverage is empty on a PR | The checkout must use `fetch-depth: 0` — it already does in `ci.yml`. |
| Sonar steps are silently skipped | `SONAR_TOKEN` secret is not set; the workflow deliberately skips Sonar so the repo still builds without it. |
