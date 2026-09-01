// Multibranch pipeline. What runs depends on the branch:
//
//   feature/*  Build + Quality
//   develop    ... plus Eval and E2E
//   main       ... plus Docker and Deploy
//
// The Eval stage is the point of this pipeline. It fails the build when line
// accuracy drops below the threshold, so a change that quietly makes the
// auditor worse cannot merge on the strength of green unit tests.

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
    PATH = "${WORKSPACE}/.venv/bin:${env.HOME}/.local/bin:${env.PATH}"
    // Ollama is expected on the agent, or reachable from it.
    BA_OLLAMA_BASE_URL = "${env.BA_OLLAMA_BASE_URL ?: 'http://localhost:11434'}"
    // The eval gate. v5 sits at 68.3%; a drop of more than three points is a
    // regression, not noise.
    EVAL_THRESHOLD = '0.65'
  }

  stages {

    stage('Build') {
      steps {
        sh 'uv sync --frozen'
        sh 'uv run pyb clean'
      }
    }

    stage('Quality') {
      parallel {
        stage('Lint') {
          steps { sh 'uv run pyb analyze' }
        }
        stage('Unit') {
          steps { sh 'uv run pyb run_unit_tests' }
        }
      }
    }

    stage('Eval') {
      when { anyOf { branch 'develop'; branch 'main'; branch pattern: 'release/.*', comparator: 'REGEXP' } }
      steps {
        // Exits 1 below the threshold, which fails the stage and the build.
        sh "uv run python eval/evaluate.py --quick --agent --second-pass --threshold ${EVAL_THRESHOLD}"
      }
    }

    stage('E2E') {
      when { anyOf { branch 'develop'; branch 'main' } }
      steps {
        // Both halves are started here, so BA_E2E_STRICT makes a missing
        // service a failure rather than the skip a laptop gets.
        sh '''
          uv run uvicorn api.main:app --port 8000 &
          echo $! > .api.pid
          cd frontend && npm ci && npm run build && npx vite preview --port 5173 &
          echo $! > .web.pid
          cd "$WORKSPACE"
          for i in $(seq 1 60); do
            curl -sf http://localhost:8000/health >/dev/null && curl -sf http://localhost:5173 >/dev/null && break
            sleep 2
          done
          BA_E2E_STRICT=1 uv run python -m unittest tests.e2e.test_flow
        '''
      }
      post {
        always {
          sh 'kill $(cat .api.pid) $(cat .web.pid) 2>/dev/null || true'
        }
      }
    }

    stage('Docker') {
      when { branch 'main' }
      steps {
        sh '''
          docker build -t bill-auditor/ingestion-service:${BUILD_NUMBER} -f services/ingestion/Dockerfile .
          docker build -t bill-auditor/retrieval-service:${BUILD_NUMBER} -f services/retrieval/Dockerfile .
          docker build -t bill-auditor/audit-service:${BUILD_NUMBER}      -f services/audit/Dockerfile .
          docker build -t bill-auditor/gateway:${BUILD_NUMBER}            -f services/gateway/Dockerfile .
          docker build -t bill-auditor/frontend:${BUILD_NUMBER} ./frontend
        '''
      }
    }

    stage('Deploy') {
      when { branch 'main' }
      steps {
        sh 'kubectl apply -f k8s/'
        sh 'kubectl -n bill-auditor rollout status deploy/gateway --timeout=180s'
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
