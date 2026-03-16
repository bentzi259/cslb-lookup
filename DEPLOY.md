# Deployment Guide

## Prerequisites

- Docker
- Kubernetes cluster (Docker Desktop K8s, EKS, GKE, AKS, etc.)
- Helm 3
- kubectl configured to your target cluster
- CSLB CSV file (`MasterLicenseData.csv`) downloaded from https://www.cslb.ca.gov/onlineservices/dataportal/ContractorList

## Step 1: Clone the Repository

```bash
git clone https://github.com/bentzi259/cslb-lookup.git
cd cslb-lookup
```

## Step 2: Build the Docker Image

```bash
docker build -t cslb-lookup:latest .
```

### For cloud clusters (push to a registry)

```bash
# Tag for your registry
docker tag cslb-lookup:latest <your-registry>/cslb-lookup:latest

# Push
docker push <your-registry>/cslb-lookup:latest
```

Replace `<your-registry>` with your container registry (e.g., `ghcr.io/username`, `123456789.dkr.ecr.us-east-1.amazonaws.com`, `gcr.io/project-id`).

### For Docker Desktop K8s

No push needed — locally built images are available to the cluster automatically.

## Step 3: Deploy with Helm

### Basic deployment (CSV mode, no Firecrawl)

```bash
helm install cslb-lookup ./helm/cslb-lookup \
  --namespace default \
  --set csvRefresh.enabled=false
```

### With Firecrawl enabled

```bash
helm install cslb-lookup ./helm/cslb-lookup \
  --namespace default \
  --set secrets.firecrawlApiKey=fc-YOUR-API-KEY
```

### With a custom image registry

```bash
helm install cslb-lookup ./helm/cslb-lookup \
  --namespace default \
  --set image.repository=<your-registry>/cslb-lookup \
  --set image.tag=latest
```

### With ingress (cloud clusters)

```bash
helm install cslb-lookup ./helm/cslb-lookup \
  --namespace default \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.hosts[0].host=cslb-api.yourdomain.com \
  --set ingress.hosts[0].paths[0].path=/ \
  --set ingress.hosts[0].paths[0].pathType=Prefix
```

### All options at once (example)

```bash
helm install cslb-lookup ./helm/cslb-lookup \
  --namespace default \
  --set image.repository=<your-registry>/cslb-lookup \
  --set image.tag=latest \
  --set secrets.firecrawlApiKey=fc-YOUR-API-KEY \
  --set csvRefresh.enabled=true \
  --set csvRefresh.schedule="0 6 * * *" \
  --set persistence.storageClass=gp2 \
  --set persistence.size=2Gi \
  --set autoscaling.enabled=true \
  --set autoscaling.minReplicas=2 \
  --set autoscaling.maxReplicas=5
```

## Step 4: Verify the Deployment

```bash
# Check pod is running
kubectl get pods -l app.kubernetes.io/name=cslb-lookup

# Check logs
kubectl logs -l app.kubernetes.io/name=cslb-lookup
```

## Step 5: Load the CSV Data

The database starts empty. You must load the CSV data into the pod.

```bash
# Get the pod name
POD=$(kubectl get pods -l app.kubernetes.io/name=cslb-lookup -o jsonpath='{.items[0].metadata.name}')

# Copy the CSV file into the pod
kubectl cp /path/to/MasterLicenseData.csv default/$POD:/data/MasterLicenseData.csv

# Load it into SQLite
kubectl exec $POD -- python -m app.csv_loader /data/MasterLicenseData.csv /data/licenses.db
```

You should see output like:
```
Loading CSV: /data/MasterLicenseData.csv
Loaded 242794 records from CSV
Inserted 242794 records into temp table
Database updated successfully at /data/licenses.db
```

## Step 6: Access the API

### Option A: Port-forward (local testing)

```bash
kubectl port-forward svc/cslb-lookup 8001:8000
```

Then access at `http://localhost:8001`.

### Option B: Ingress (production)

If you enabled ingress in Step 3, the API is available at the configured host.

### Option C: NodePort

```bash
helm upgrade cslb-lookup ./helm/cslb-lookup --set service.type=NodePort
```

## Step 7: Test

```bash
# Health check
curl http://localhost:8001/health

# License lookup
curl http://localhost:8001/api/license/1041069

# Bulk lookup
curl -X POST http://localhost:8001/api/licenses \
  -H "Content-Type: application/json" \
  -d '{"license_numbers": ["1041069", "1000002"]}'

# Stats
curl http://localhost:8001/api/stats

# Swagger docs
open http://localhost:8001/docs
```

## Updating

### Update the code

```bash
git pull
docker build -t cslb-lookup:latest .
helm upgrade cslb-lookup ./helm/cslb-lookup
kubectl rollout restart deployment cslb-lookup
```

### Refresh the CSV data

```bash
POD=$(kubectl get pods -l app.kubernetes.io/name=cslb-lookup -o jsonpath='{.items[0].metadata.name}')
kubectl cp /path/to/MasterLicenseData.csv default/$POD:/data/MasterLicenseData.csv
kubectl exec $POD -- python -m app.csv_loader /data/MasterLicenseData.csv /data/licenses.db
```

### Uninstall

```bash
helm uninstall cslb-lookup
kubectl delete pvc cslb-lookup-data
```

## Cloud-Specific Notes

### AWS EKS

- Use ECR for the container registry
- Set `persistence.storageClass=gp2` (or `gp3`)
- Use ALB Ingress Controller: `ingress.className=alb`

### Google GKE

- Use Artifact Registry or GCR for the container registry
- Set `persistence.storageClass=standard` (or `premium-rwo`)
- Use GKE Ingress: `ingress.className=gce`

### Azure AKS

- Use ACR for the container registry
- Set `persistence.storageClass=managed-premium` (or `managed-csi`)
- Use AGIC: `ingress.className=azure-application-gateway`

### Docker Desktop (local)

- No registry needed — local images are available automatically
- Default storage class works out of the box
- Use port-forward to access the API
