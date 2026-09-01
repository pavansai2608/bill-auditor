# Kubernetes

Targets minikube. Eight manifests, applied in filename order.

## Start a cluster with enough room

The audit service and Ollama are the hungry ones. Less than 8 GB and the model
pod will be evicted.

```bash
minikube start --memory=8192 --cpus=4 --disk-size=40g
```

## Build the images into the cluster

minikube has its own Docker daemon, so images built on your laptop are not
visible to it unless you either build inside it or load them in.

```bash
# Point your shell at minikube's docker, then build there directly.
eval $(minikube docker-env)
docker build -t bill-auditor/ingestion-service:latest -f services/ingestion/Dockerfile .
docker build -t bill-auditor/retrieval-service:latest -f services/retrieval/Dockerfile .
docker build -t bill-auditor/audit-service:latest      -f services/audit/Dockerfile .
docker build -t bill-auditor/gateway:latest            -f services/gateway/Dockerfile .
docker build -t bill-auditor/frontend:latest --build-arg VITE_API_BASE=http://$(minikube ip):30800 ./frontend
```

`imagePullPolicy: IfNotPresent` in every deployment is what stops Kubernetes
trying to pull these from a registry that does not have them.

## Deploy

```bash
kubectl apply -f k8s/
kubectl -n bill-auditor get pods -w
```

The first start is slow: Ollama has to pull `qwen3:8b` into its volume.

```bash
kubectl -n bill-auditor exec deploy/ollama -- ollama pull qwen3:8b
```

## Reach it

```bash
minikube ip                                    # e.g. 192.168.49.2
open "http://$(minikube ip):30173"             # the app
curl "http://$(minikube ip):30800/health"      # the gateway, and its dependencies
```

`GET /health` on the gateway reports every dependency, so one call says what is
down.

## Logs

```bash
kubectl -n bill-auditor logs -f deploy/audit-service
kubectl -n bill-auditor logs -f deploy/retrieval-service
kubectl -n bill-auditor describe pod -l app=audit-service   # for a pod that will not start
```

## Index the clauses once

The images ship `data/clauses.json`, but the embeddings live on a volume and
start empty:

```bash
kubectl -n bill-auditor exec deploy/ingestion-service -- \
  python -c "from core import ingest; ingest.run(force=True)"
```

## Point at a hosted model instead of running one

`BA_OLLAMA_BASE_URL` in `01-config.yaml` is the only thing that decides where
the judge model lives. Point it elsewhere, scale Ollama to zero, and no pod in
the cluster runs an 8B model:

```bash
kubectl -n bill-auditor edit configmap bill-auditor-config   # change BA_OLLAMA_BASE_URL
kubectl -n bill-auditor scale deploy/ollama --replicas=0
kubectl -n bill-auditor rollout restart deploy/audit-service
```

## Tear down

```bash
kubectl delete -f k8s/
minikube stop            # or: minikube delete, to drop the volumes too
```
