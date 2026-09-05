// Multibranch pipeline. What runs depends on the branch:
//
//   any other branch  Build + Quality
//   develop           ... plus Eval and E2E
//   main              ... plus Docker and Deploy
//
// The repository has two long-lived branches, main and develop. There is no
// release/* pattern here because there are no release branches to match.
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

// ---------------------------------------------------------------------------
// THE GATE LEDGER
//
// main #21 is why this exists. Eval was skipped (no Ollama) and E2E was skipped
// (no Ollama, no npm). Neither ran. The build went UNSTABLE rather than
// FAILURE, Docker read that as "not failed", built and tagged five images as
// 21, and Deploy attempted a rollout with them. Those images came from code
// whose accuracy gate and browser tests had never executed.
//
// "Not failed" is not "passed". A gate that could not run has proved nothing,
// and everything downstream of it is unsafe.
//
// So each gate records, as its own last act, that it actually executed and
// passed. Docker and Deploy read these records and nothing else - never
// currentBuild.result, which is the signal that let main #21 through. A stage
// that throws never reaches its gatePassed() call, so the ledger cannot say a
// gate passed when it did not.
//
// The ledger is belt and braces: on main a missing prerequisite also aborts the
// build outright (see Eval). Either mechanism alone would stop this; both are
// here because the failure being prevented was silent.
gates = [:]
gateWhy = [:]

def gatePassed(String name) {
  gates[name] = true
}

def gateBlocked(String name, String why) {
  gates[name] = false
  gateWhy[name] = why
}

/** Gates from `names` that did not run and pass, each with the reason. */
def blockers(List names) {
  return names.findAll { gates[it] != true }
              .collect { "${it} - ${gateWhy[it] ?: 'did not run'}" }
}

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

    // Ports for the E2E stage's own servers, one pair per executor.
    //
    // Not the defaults, because on this agent 8000 and 5173 belong to the
    // docker-compose stack - gateway and frontend - which Docker Desktop
    // restores whenever it starts. The stage refuses to take a port it does not
    // own, which is correct and which made main #15 fail on Docker's own
    // listener. Giving it ports of its own is the intended way through: the
    // alternative is a pipeline that kills the daemon two stages before it
    // needs it.
    //
    // Offset by EXECUTOR_NUMBER because one fixed pair is not enough. This node
    // has two executors and multibranch runs main and develop at once: main #17
    // and develop #21 both wanted 8111/5111 at 13:59:44Z, main got them, and
    // develop refused a port held by another workspace - correctly, but the
    // build was red for a reason that had nothing to do with its commit.
    // Executor numbers are unique among builds running together, which is
    // exactly the property needed here.
    //
    // Both scripts read these, so run_stage.sh and the post block's
    // free_ports.sh always agree on which ports this build owns.
    BA_E2E_API_PORT = "${8100 + (env.EXECUTOR_NUMBER ?: '0').toInteger()}"
    BA_E2E_WEB_PORT = "${5100 + (env.EXECUTOR_NUMBER ?: '0').toInteger()}"
  }

  stages {

    stage('Build') {
      steps {
        // --all-extras is not optional. The base dependency group has neither
        // chromadb nor sentence-transformers, so `uv sync --frozen` alone
        // leaves an environment in which a third of the suite cannot import.
        sh 'uv sync --frozen --all-extras'
        sh 'uv run pyb clean'
        script { gatePassed('Build') }
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
            script { gatePassed('Lint') }
          }
        }
        stage('Unit') {
          // Collects tests/test_*.py only. The browser test is
          // tests/e2e/browser_flow.py, which the test_* glob no longer matches,
          // so it can no longer be dragged into this stage without its services.
          steps {
            sh 'uv run pyb --no-venvs run_unit_tests'
            script { gatePassed('Unit') }
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
      when { anyOf { branch 'develop'; branch 'main' } }
      steps {
        script {
          def ollamaUp = sh(returnStatus: true, script: "curl -sf --max-time 5 ${BA_OLLAMA_BASE_URL}/api/tags >/dev/null") == 0
          if (!ollamaUp) {
            gateBlocked('Eval', "no Ollama at ${BA_OLLAMA_BASE_URL}, so the accuracy gate never ran")
            if (env.BRANCH_NAME == 'main') {
              // Red, not yellow, and deliberately. main is the branch that
              // produces images and deploys them. A build that cannot measure
              // its own accuracy has not earned either, and yellow is the
              // colour people stop reading.
              error("Eval could not run: no Ollama at ${BA_OLLAMA_BASE_URL}. " +
                    'On main that is a failure, not a warning - this build cannot ' +
                    'prove its accuracy, so it must not produce images or deploy.')
            }
            unstable("Eval skipped: no Ollama at ${BA_OLLAMA_BASE_URL}. The accuracy gate did not run.")
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('Ollama unavailable') }
          } else {
            // Exits 1 below the threshold, which fails the stage and the build.
            // gatePassed is only reached if that command exits 0.
            sh "uv run python eval/evaluate.py --quick --agent --second-pass --threshold ${EVAL_THRESHOLD}"
            gatePassed('Eval')
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
            def lack = []
            if (!ollamaUp) { lack << "no Ollama at ${BA_OLLAMA_BASE_URL}" }
            if (!nodeUp) { lack << 'no npm on the agent' }
            gateBlocked('E2E', "${lack.join(', ')}, so the browser tests never ran")
            if (env.BRANCH_NAME == 'main') {
              error("E2E could not run: ${lack.join(', ')}. On main that is a failure - " +
                    'this build has no evidence the app works in a browser, so it must ' +
                    'not produce images or deploy.')
            }
            unstable('E2E skipped: needs both a running Ollama and npm on the agent.')
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('E2E prerequisites missing') }
          } else {
            // Everything is in the script, including cleanup, because the
            // version that lived here did not test the build it was given.
            //
            // It started both servers in the background, waited for *something*
            // to answer port 5173, and then killed a pid that was not the one
            // holding the port - `npx` forks vite as a child, so the orphan
            // survived every build and answered the next one's readiness curl
            // in under a second. develop #17 went red against that stale
            // frontend; main #11 went green after its own preview server
            // refused to start at all. Neither result was real.
            //
            // run_stage.sh frees the port first and fails if it cannot, starts
            // each server as a process-group leader, and refuses to run the
            // test unless the process holding the port is in this run's process
            // group AND is serving this run's build stamp. See its header for
            // why neither check alone is enough.
            sh 'tests/e2e/run_stage.sh'
            gatePassed('E2E')
          }
        }
      }
      post {
        always {
          // Whatever happened above, the next build must not inherit a server.
          sh 'tests/e2e/free_ports.sh'
          // The server logs are the evidence when readiness fails, and they are
          // inside the workspace, so keep a copy on the build.
          archiveArtifacts artifacts: '.e2e-logs/*.log', allowEmptyArchive: true
        }
      }
    }

    stage('Docker') {
      when { branch 'main' }
      steps {
        script {
          // Every gate, checked explicitly and by name. Not currentBuild.result:
          // main #21 was UNSTABLE with Eval and E2E both skipped, and "not
          // failed" was enough to get five images built and tagged 21.
          def missing = blockers(['Build', 'Lint', 'Unit', 'Eval', 'E2E'])
          if (missing) {
            echo '================================================================'
            echo 'Docker is BLOCKED. These gates did not run and pass:'
            missing.each { echo "    ${it}" }
            echo ''
            echo 'No image has been built and no tag has been created.'
            echo 'A gate that could not run has proved nothing, and an image'
            echo 'built past it would carry a build number implying it had.'
            echo '================================================================'
            error("Docker blocked: ${missing.size()} gate(s) did not run and pass.")
          }
          echo "Gates cleared: ${gates.findAll { it.value }.keySet().join(', ')}"

          if (sh(returnStatus: true, script: 'docker info >/dev/null 2>&1') != 0) {
            gateBlocked('Docker', 'no reachable Docker daemon on this agent')
            // main's job is to produce images and deploy them. An agent that
            // cannot do that has not run main's pipeline, whatever colour the
            // other stages are.
            error('Docker could not run: no reachable Docker daemon. On main that ' +
                  'is a failure - this build produced no images, so Deploy has ' +
                  'nothing to roll out.')
          } else {
            // Both tags on purpose. BUILD_NUMBER is the traceable one; :latest
            // is what k8s/ pins, and every manifest is imagePullPolicy
            // IfNotPresent, so without it Deploy would roll out an image this
            // build never produced.
            // The image name is listed, not derived. A loop that appended
            // "-service" to every directory built bill-auditor/gateway-service,
            // while k8s/50-gateway.yaml asks for bill-auditor/gateway - so
            // Deploy pulled a name nothing had built. The manifests are the
            // authority for these names; keep the two lists in step.
            sh '''
              set -e
              for pair in \
                "ingestion-service:services/ingestion/Dockerfile" \
                "retrieval-service:services/retrieval/Dockerfile" \
                "audit-service:services/audit/Dockerfile" \
                "gateway:services/gateway/Dockerfile"; do
                name="${pair%%:*}"
                file="${pair#*:}"
                docker build -t bill-auditor/${name}:${BUILD_NUMBER} \
                             -t bill-auditor/${name}:latest -f "$file" .
              done
              docker build -t bill-auditor/frontend:${BUILD_NUMBER} \
                           -t bill-auditor/frontend:latest ./frontend
            '''
            gatePassed('Docker')
          }
        }
      }
    }

    stage('Deploy') {
      when { branch 'main' }
      steps {
        script {
          // Deploy rolls out images. If Docker did not run and succeed, the
          // images this build claims to deploy do not exist, and rolling out
          // would either fail to pull or - worse - silently leave the cluster
          // on an older build while the stage reported success.
          def missing = blockers(['Docker'])
          if (missing) {
            echo '================================================================'
            echo 'Deploy is BLOCKED. This gate did not run and pass:'
            missing.each { echo "    ${it}" }
            echo ''
            echo 'Nothing was applied and no rollout was started.'
            echo '================================================================'
            error('Deploy blocked: Docker did not run and pass.')
          }

          if (sh(returnStatus: true, script: 'kubectl cluster-info >/dev/null 2>&1') != 0) {
            gateBlocked('Deploy', 'kubectl reached no cluster, so nothing was rolled out')
            unstable('Deploy skipped: kubectl reaches no cluster from this agent.')
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('no cluster') }
          } else if (sh(returnStatus: true, script: 'command -v minikube >/dev/null 2>&1') != 0) {
            gateBlocked('Deploy', 'minikube is not on this agent, so nothing was rolled out')
            unstable('Deploy skipped: minikube is not on this agent.')
            catchError(buildResult: 'UNSTABLE', stageResult: 'NOT_BUILT') { error('no minikube') }
          } else {
            // k8s/deploy.sh, not `kubectl apply -f k8s/`. The apply on its own
            // deployed nothing: Jenkins builds into Docker Desktop's daemon
            // and minikube runs its own, so the image never crossed; and every
            // manifest pins `:latest`, so the Deployment spec never changed and
            // no rollout ever started. The stage went green while the pods kept
            // running an image loaded by hand days earlier.
            //
            // The script loads this build's images into the node, applies the
            // manifests with the BUILD_NUMBER tag substituted, and then reads
            // back the image every pod reports. It exits 1 if any pod is not on
            // this build's tag, which is what makes the stage's green mean
            // something. Verifying `:latest` against `:latest` could not - the
            // string is identical whatever the pod is running.
            //
            // This stage is main-only (see `when` above), because loading five
            // images is minutes, not seconds, and develop must stay quick.
            sh 'k8s/deploy.sh'
            gatePassed('Deploy')
          }
        }
      }
    }

    // Prune. Runs only after a main build that genuinely got all the way
    // through, because deleting on a build that did not is how you end up with
    // a cluster that cannot pull.
    //
    // Every build produces five images. Left alone that is one more set per
    // build, for ever. The keep/delete decision is in ci/prune_images.py rather
    // than inline here, because it is the part that can be wrong in a way that
    // costs something, and it has tests.
    //
    // The rule that is not obvious is the fourth keep rule: an image referenced
    // by a live deployment survives whatever its number. The cluster does not
    // necessarily run what this build just pushed - before k8s/deploy.sh, a
    // rollout could silently not happen at all - so the live references are
    // read from the cluster at prune time and outrank the arithmetic.
    stage('Prune') {
      when { branch 'main' }
      steps {
        script {
          def needed = ['Build', 'Lint', 'Unit', 'Eval', 'E2E', 'Docker', 'Deploy']
          def missing = blockers(needed)
          if (missing) {
            gateBlocked('Prune', 'an earlier gate did not run and pass')
            echo '================================================================'
            echo 'Prune is BLOCKED. These gates did not run and pass:'
            missing.each { echo "    ${it}" }
            echo ''
            echo 'NOTHING WAS DELETED, from either daemon.'
            echo 'Deleting on a build that did not finish is how a cluster ends'
            echo 'up unable to pull the image it is running.'
            echo '================================================================'
            // Not an error(). The images are still correct and still deployed;
            // only the cleanup was withheld, and disk that was not reclaimed is
            // not a broken build. The earlier gate has already coloured it.
            return
          }

          // Deleted from both stores. Docker Desktop's daemon and minikube's
          // are separate: an image removed from one is untouched in the other,
          // which is the same separation that made Deploy silently no-op.
          // The script skips minikube on its own if no profile is running.
          sh "uv run python ci/prune_images.py --build-number ${BUILD_NUMBER}"
          gatePassed('Prune')
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
