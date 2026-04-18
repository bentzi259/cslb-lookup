# CI/CD: deploy.yml

Triggered on push to `main` (or manually via "Run workflow"). The pipeline:

1. **build** — builds the Docker image once, pushes the same bytes to:
   - ECR (`310859635502.dkr.ecr.us-east-1.amazonaws.com/cslb-lookup:staging-<sha>`) for staging
   - ACR (`cslblookupcr.azurecr.io/cslb-lookup:prod-<sha>`) for production
2. **deploy-staging** — `helm upgrade --install` to EKS `carrify-staging` namespace `cslb-lookup`, then runs a `/health` smoke test
3. **deploy-production** — `helm upgrade --install` to AKS `general-cluster` namespace `cslb-lookup`. **Requires staging to succeed first AND manual approval via the `production` GitHub Environment.**

## Required GitHub secrets

Set these under **Settings → Secrets and variables → Actions**:

| Secret | Used in | Description |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | build, deploy-staging | IAM user with `ecr:*` on `cslb-lookup` repo + `eks:DescribeCluster` on `carrify-staging` |
| `AWS_SECRET_ACCESS_KEY` | build, deploy-staging | Paired secret for above |
| `ACR_USERNAME` | build | ACR admin username (or service principal app ID) |
| `ACR_PASSWORD` | build | ACR admin password (or SP secret) |
| `AZURE_CREDENTIALS` | deploy-production | JSON output from `az ad sp create-for-rbac --sdk-auth` with `Contributor` on the AKS resource group |
| `STAGING_API_KEY` | deploy-staging | API key for `X-API-Key` header on staging |
| `PROD_API_KEY` | deploy-production | API key for `X-API-Key` header on production |

## GitHub Environments

Two environments must exist:
- **staging** — no protection rules; auto-deploys after build succeeds
- **production** — add a "Required reviewers" protection rule to require manual approval before prod deploys

## Local equivalent

What this workflow automates manually looks like:

```bash
# 1. Build + push to both registries
TAG="$(git rev-parse HEAD)"
docker build -t 310859635502.dkr.ecr.us-east-1.amazonaws.com/cslb-lookup:staging-$TAG .
docker tag 310859635502.dkr.ecr.us-east-1.amazonaws.com/cslb-lookup:staging-$TAG cslblookupcr.azurecr.io/cslb-lookup:prod-$TAG
docker push 310859635502.dkr.ecr.us-east-1.amazonaws.com/cslb-lookup:staging-$TAG
docker push cslblookupcr.azurecr.io/cslb-lookup:prod-$TAG

# 2. Deploy staging
aws eks update-kubeconfig --region us-east-1 --name carrify-staging
helm upgrade cslb-lookup ./helm/cslb-lookup -n cslb-lookup \
  --set image.repository=310859635502.dkr.ecr.us-east-1.amazonaws.com/cslb-lookup \
  --set image.tag=staging-$TAG

# 3. After staging verified, deploy prod
kubectl config use-context general-cluster
helm upgrade cslb-lookup ./helm/cslb-lookup -n cslb-lookup \
  --set image.repository=cslblookupcr.azurecr.io/cslb-lookup \
  --set image.tag=prod-$TAG
```
