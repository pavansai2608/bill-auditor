// Multibranch pipeline. What runs depends on the branch:
//
//   feature/*  Build + Quality
//   develop    ... plus Eval and E2E
//   main       ... plus Docker and Deploy
//
// The Eval stage is the point of this pipeline. It fails the build when line
// accuracy drops below the threshold, so a change that quietly makes the
// auditor worse cannot merge on the strength of green unit tests.
//
// Stages that need something a plain Jenkins agent does not have - a running
// Ollama, a Docker daemon, a Kubernetes cluster - probe for it first and mark
// themselves NOT_BUILT with the reason instead of failing. A stage that always
// fails teaches people to ignore red, which is the one thing this pipeline
// cannot afford.

pipeline {
  agent any

  options {
    timeout(time: 90, unit: 'MINUTES')
    timestamps()
    disableConcurrentBuilds()
  }

  environment {
    // uv keeps the virtualenv in the workspace, so agents stay clean.
    UV_PROJECT_ENVIRONMENT = "${WORKSPACE}/.venv"
    PATH = "${WORKSPACE}/.venv/bin:${env.HOME}/.local/bin:/opt/homebrew/bin:${env.PATH}"

    // Ollama is expected on the agent, or reachable from it.
    BA_OLLAMA_BASE_URL = "${env.BA_OLLAMA_BASE_URL ?: 'http://localhost:11434'}"

    // Pinned so CI is reproducible and never silently depends on a key.
    //   backend: the eval is ~400 model calls, which would spend Groq's whole
    //            daily allowance; the API would otherwise default to Groq.
    //   device:  the recorded baseline below was measured on cpu. mps and cpu
    //            agree to five decimals, but the gate should not depend on
    //            which machine picked up the job.
    BA_LLM_BACKEND = 'ollama'
    BA_TORCH_DEVICE = 'cpu'

    // The eval gate. See the block comment on the Eval stage before changing it.
    EVAL_THRESHOLD = '0.52'
  }

  stages {

    stage('Build') {
      steps {
        // --all-extras is not optional. The base dependency group has neither
        // chromadb nor sentence-transformers, so `uv sync --frozen` alone
        // leaves an environment in which a third of the suite cannot import.
        sh 'uv sync --frozen --all-extras'
        sh 'uv run pyb clean'
      }
    }

    // Parallel, and safe to be. Two things had to change for that.
    //
    // Lint is ruff, not `pyb analyze`. `analyze` declares run_unit_tests as a
    // dependency, so a parallel Lint and Unit ran the whole suite twice and had
    // two PyBuilder processes writing target/ at once. ruff touches nothing
    // PyBuilder owns, so the two stages now share no state at all - and ruff is
    // what the pre-commit hook enforces locally, so CI and the hook agree.
    //
    // Unit passes --no-venvs. Without it PyBuilder seeds its own virtualenvs
    // under .pybuilder/plugins/..., and two concurrent builds in one workspace
    // collide there: FileExistsError on one branch, OSError EINVAL on another,
    // same race. The Build stage already installed everything into .venv with
    // uv, so those seeded environments were redundant as well as racy.
    stage('Quality') {
      parallel {
        stage('Lint') {
          steps {
            sh 'uv run ruff check .'
            sh 'uv run ruff format --check .'
          }
        }
        stage('Unit') {
          // Collects tests/test_*.py only. The browser test is
          // tests/e2e/browser_flow.py, which the test_* glob no longer matches,
          // so it can no longer be dragged into this stage without its services.
          steps {
            sh 'uv run pyb --no-venvs run_unit_tests'
          }
        }
      }
    }

    // The gate.
    //
    // It runs --quick, the first 10 bills, because a full 44-bill run takes
    // about 40 minutes and does not belong in CI. The threshold is therefore a
    // quick-subset figure and must never be compared with a 44-bill one.
    //
    //   baseline   56.1% - eval/results.md, row `ci-baseline-v7-quick`
    //              (10 bills, 82 lines, 46 correct, ollama qwen3:8b on cpu)
    //   threshold  0.52  - just under three lines below it. One line is 1.22
    //              points, so 43 of 82 still passes at 52.4% and 42 fails at
    //              51.2%: ordinary drift survives, a real regression does not.
    //
    // It moves only when a new recorded row justifies it. The previous gate was
    // 0.65, set against v5's 68.3% - a figure measured on a clause index later
    // found to hold corrupted tables. See the note under that row.
    stage('Eval') {
      when { anyOf { branch 'develop'; branch 'main'; branch pattern: 'release/.*', comparator: 'REGEXP' } }
      steps {
        script {
          def ollamaUp = sh(returnStatus: true, script: "curl -sf --max-time 5 ${BA_OLLAMA_BASE_URL}/api/tags >/dev/null") == 0
          if (!ollamaUp) {
            unstable("Eval skipped: no Ollama at ${BA_OLLAMA_BASE_URL}. The accuracy gate did not run.")
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('Ollama unavailable') }
          } else {
            // Exits 1 below the threshold, which fails the stage and the build.
            sh "uv run python eval/evaluate.py --quick --agent --second-pass --threshold ${EVAL_THRESHOLD}"
          }
        }
      }
    }

    stage('E2E') {
      when { anyOf { branch 'develop'; branch 'main' } }
      steps {
        script {
          def ollamaUp = sh(returnStatus: true, script: "curl -sf --max-time 5 ${BA_OLLAMA_BASE_URL}/api/tags >/dev/null") == 0
          def nodeUp = sh(returnStatus: true, script: 'command -v npm >/dev/null') == 0
          if (!ollamaUp || !nodeUp) {
            unstable('E2E skipped: needs both a running Ollama and npm on the agent.')
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('E2E prerequisites missing') }
          } else {
            // Both halves are started here, so BA_E2E_STRICT makes a missing
            // service a failure rather than the skip a laptop gets.
            sh '''
              set -e
              uv run uvicorn api.main:app --port 8000 &
              echo $! > .api.pid
              ( cd frontend && npm ci && npm run build && npx vite preview --port 5173 ) &
              echo $! > .web.pid
              for i in $(seq 1 60); do
                curl -sf http://localhost:8000/health >/dev/null \
                  && curl -sf http://localhost:5173 >/dev/null && break
                sleep 2
              done
              BA_E2E_STRICT=1 uv run python -m unittest tests.e2e.browser_flow
            '''
          }
        }
      }
      post {
        always {
          sh 'kill $(cat .api.pid) $(cat .web.pid) 2>/dev/null || true'
          sh 'rm -f .api.pid .web.pid'
        }
      }
    }

    stage('Docker') {
      when { branch 'main' }
      steps {
        script {
          if (sh(returnStatus: true, script: 'docker info >/dev/null 2>&1') != 0) {
            unstable('Docker skipped: no reachable Docker daemon on this agent.')
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('no docker daemon') }
          } else {
            // Both tags on purpose. BUILD_NUMBER is the traceable one; :latest
            // is what k8s/ pins, and every manifest is imagePullPolicy
            // IfNotPresent, so without it Deploy would roll out an image this
            // build never produced.
            sh '''
              set -e
              for svc in ingestion retrieval audit gateway; do
                docker build -t bill-auditor/${svc}-service:${BUILD_NUMBER} \
                             -t bill-auditor/${svc}-service:latest \
                             -f services/${svc}/Dockerfile .
              done
              docker build -t bill-auditor/frontend:${BUILD_NUMBER} \
                           -t bill-auditor/frontend:latest ./frontend
            '''
          }
        }
      }
    }

    stage('Deploy') {
      when { branch 'main' }
      steps {
        script {
          if (sh(returnStatus: true, script: 'kubectl cluster-info >/dev/null 2>&1') != 0) {
            unstable('Deploy skipped: kubectl reaches no cluster from this agent.')
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('no cluster') }
          } else {
            // 00-namespace.yaml has to land before anything namespaced, and
            // `kubectl apply -f k8s/` applies in filename order, which is why
            // the manifests are numbered.
            sh 'kubectl apply -f k8s/'
            sh 'kubectl -n bill-auditor rollout status deploy/gateway --timeout=180s'
          }
        }
      }
    }
  }

  post {
    always {
      // The results table is the project's headline output, so every build
      // keeps a copy of it.
      archiveArtifacts artifacts: 'eval/results.md', allowEmptyArchive: true
      junit testResults: 'target/reports/**/*.xml', allowEmptyResults: true
    }
    failure {
      echo 'If the Eval stage is the red one, read JENKINS_SETUP.md section 8 before changing the threshold.'
    }
  }
}
