# Jenkins setup

Written for someone who has never opened Jenkins. Follow it in order.

The point of this pipeline is the **Eval** stage. It runs the auditor against
the hand-written answer key and fails the build if line accuracy drops below
0.65. Unit tests can pass while the audit quietly gets worse; this stage is
what catches that.

---

## 1. Install Jenkins

**macOS**

```bash
brew install jenkins-lts
brew services start jenkins-lts
```

**Ubuntu**

```bash
sudo apt update && sudo apt install -y openjdk-17-jre
curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc >/dev/null
echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" | sudo tee /etc/apt/sources.list.d/jenkins.list
sudo apt update && sudo apt install -y jenkins
sudo systemctl start jenkins
```

Open <http://localhost:8080>.

## 2. Unlock it

Jenkins prints a one-time password to a file. Paste it into the box on screen.

```bash
# macOS
cat ~/.jenkins/secrets/initialAdminPassword
# Ubuntu
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Choose **Install suggested plugins**, then create your admin user.

## 3. Install the plugins this pipeline needs

**Manage Jenkins → Plugins → Available plugins.** Install these, then restart:

| Plugin | Why |
|---|---|
| Pipeline | runs a `Jenkinsfile` at all |
| Multibranch Scan Webhook Trigger | one job covering every branch |
| Git | clones the repo |
| GitHub | reads branches and pull requests |
| JUnit | renders the test results |
| Timestamper | timestamps in the log, which the `Jenkinsfile` asks for |
| Workspace Cleanup | stops one build's `.venv` confusing the next |

## 4. Give the agent the tools the build calls

Jenkins runs as its own user, which does **not** inherit your shell's PATH.
Everything below must be runnable by that user.

```bash
# as the jenkins user, or install system-wide
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv
node --version                                     # node 20+ for the E2E stage
docker --version                                   # only needed on main
kubectl version --client                           # only needed on main
ollama list                                        # qwen3:8b must be pulled
```

If `ollama` runs on your laptop and Jenkins runs in a container, set
`BA_OLLAMA_BASE_URL` in **Manage Jenkins → System → Global properties →
Environment variables** to point at it, for example
`http://host.docker.internal:11434`.

## 5. Add the repository credentials

Only needed for a private repo.

1. **Manage Jenkins → Credentials → System → Global credentials → Add.**
2. Kind: **Username with password**.
3. Username: your GitHub username. Password: a GitHub personal access token
   with `repo` scope (GitHub → Settings → Developer settings → Personal access
   tokens). Not your account password.
4. ID: `github-bill-auditor`. You will pick this by name in the next step.

## 6. Create the multibranch pipeline

1. Dashboard → **New Item**.
2. Name it `bill-auditor`. Choose **Multibranch Pipeline**. OK.
3. **Branch Sources → Add source → Git.**
   - Project repository: `https://github.com/pavansai2608/bill-auditor.git`
   - Credentials: `github-bill-auditor` (skip for a public repo)
4. **Build Configuration** — Mode: by Jenkinsfile, Script Path: `Jenkinsfile`.
   That is the default and it is already correct.
5. **Scan Multibranch Pipeline Triggers** — tick *Periodically if not otherwise
   run*, interval 5 minutes. That is enough without setting up webhooks.
6. **Save.** Jenkins scans the repository and creates one job per branch.

## 7. Read a build

Click the job, then a branch, then a build number, then **Console Output**.

The stage view at the top shows every stage as a box. A red box is the stage
that failed; click it and then **Logs** to see only that stage's output.

What each stage means when it goes red:

| Stage | Red means |
|---|---|
| Build | `uv sync` failed — usually a dependency change that was not committed with `uv.lock` |
| Lint | flake8 found something. Run `uv run pyb analyze` locally to see the same output |
| Unit | a PyUnit test failed. `uv run pyb run_unit_tests` reproduces it |
| Eval | line accuracy fell below the threshold — see the next section |
| E2E | the browser flow broke, or the API or frontend did not start |
| Docker | an image failed to build |
| Deploy | `kubectl apply` failed, usually a cluster that is not running |

## 8. When the Eval stage fails

**Do not raise the threshold to make it pass.** That is the one change that
makes the whole pipeline pointless.

The log ends with a line like:

```
FAIL: line accuracy 0.610 is below the threshold 0.650
```

Then:

1. Reproduce it locally, and look at which category moved:

   ```bash
   uv run python eval/evaluate.py --quick --agent --second-pass
   ```

2. Compare against `eval/results.md`. Every recorded version is there, so you
   can see which category used to be higher.

3. Find the commit that did it. This is what the threshold is for:

   ```bash
   git bisect start
   git bisect bad HEAD
   git bisect good v5
   git bisect run uv run python eval/evaluate.py --quick --agent --second-pass --threshold 0.65
   git bisect reset
   ```

4. Fix it, or revert that commit. If it is a deliberate trade, record it in
   `KNOWN_LIMITATIONS.md` and say so in the commit message.

The one thing that must never move is the fabricated-citation count. It is 0 at
every recorded version and `tests/test_eval_scoring.py` guards how it is
counted.

## 9. Speed

The first build on an agent is slow: `uv sync` downloads the embedding and
reranker models. After that, `data/llm_cache` makes the Eval stage take a
couple of minutes instead of forty. Do not add a workspace cleanup step that
deletes it.
