#!/usr/bin/env bash
#
# Deploy Climate Hubris to AWS.
#
#   ALERT_EMAIL=you@example.com scripts/deploy.sh            everything, in order
#   scripts/deploy.sh backend | data | frontend | domain     one step
#
# Steps
#   backend   build the Lambda image, push it to ECR, deploy the CloudFormation stack
#   data      run the ingestion Lambdas once so a new stack has data
#   frontend  build the static site and upload it to Amplify Hosting
#   domain    attach climate.akash.ucsciba.org and create its Route 53 records
#
# Optional environment: MONTHLY_BUDGET_USD (default 15), BEDROCK_MODEL, LLM_PROVIDER,
# RELIEFWEB_APPNAME, REPO_URL (shown as the "Source" link).
#
set -euo pipefail

STACK="climate-hubris"
REGION="us-east-1"
ROOT_DOMAIN="akash.ucsciba.org"   # Amplify domain association
PREFIX="climate"                  # -> climate.akash.ucsciba.org
HOSTED_ZONE_NAME="ucsciba.org."
SITE_DOMAIN="${PREFIX}.${ROOT_DOMAIN}"
BRANCH="main"

cd "$(dirname "$0")/.."
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${STACK}"

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

backend() {
  : "${ALERT_EMAIL:?Set ALERT_EMAIL to the address that should receive cost alerts}"

  echo "==> ECR repository"
  aws ecr describe-repositories --repository-names "$STACK" --region "$REGION" >/dev/null 2>&1 ||
    aws ecr create-repository --repository-name "$STACK" --region "$REGION" \
      --image-scanning-configuration scanOnPush=true >/dev/null
  # Keep only the three newest images so storage stays at a few cents a month.
  aws ecr put-lifecycle-policy --repository-name "$STACK" --region "$REGION" --lifecycle-policy-text \
    '{"rules":[{"rulePriority":1,"description":"keep last 3","selection":{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":3},"action":{"type":"expire"}}]}' >/dev/null

  echo "==> Building and pushing the backend image"
  TAG=$(date -u +%Y%m%d%H%M%S)
  aws ecr get-login-password --region "$REGION" |
    docker login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com" >/dev/null
  # Lambda rejects the OCI image index that BuildKit attestations produce.
  docker build --platform linux/arm64 --provenance=false -t "${REPO_URI}:${TAG}" backend
  docker push "${REPO_URI}:${TAG}"

  echo "==> Deploying stack ${STACK}"
  aws cloudformation deploy \
    --stack-name "$STACK" --region "$REGION" \
    --template-file infra/template.yaml \
    --capabilities CAPABILITY_IAM CAPABILITY_AUTO_EXPAND \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
      "ImageUri=${REPO_URI}:${TAG}" \
      "SiteDomain=${SITE_DOMAIN}" \
      "AlertEmail=${ALERT_EMAIL}" \
      "MonthlyBudgetUsd=${MONTHLY_BUDGET_USD:-15}" \
      "LlmProvider=${LLM_PROVIDER:-bedrock}" \
      "BedrockModel=${BEDROCK_MODEL:-us.anthropic.claude-haiku-4-5-20251001-v1:0}" \
      "ReliefWebAppName=${RELIEFWEB_APPNAME:-}"
  echo "    API: $(output ApiUrl)"
}

data() {
  echo "==> Ingesting sea ice and ocean heat"
  aws lambda invoke --function-name climate-hubris-ingest-arctic --region "$REGION" \
    --cli-read-timeout 150 /dev/stdout
  echo
  echo "==> Ingesting rainfall (loads the bundled history, then fetches recent months;"
  echo "    64 boxes may not fit in one run: if it reports complete: false, the weekly schedule"
  echo "    or a second 'scripts/deploy.sh data' picks up where it stopped)"
  aws lambda invoke --function-name climate-hubris-ingest-monsoon --region "$REGION" \
    --cli-read-timeout 910 /dev/stdout
  echo
  echo "==> Running the agent once"
  aws lambda invoke --function-name climate-hubris-agent --region "$REGION" \
    --cli-binary-format raw-in-base64-out --payload '{"force": true}' \
    --cli-read-timeout 610 /dev/stdout
  echo
}

frontend() {
  APP_ID=$(output AmplifyAppId)
  API_URL=$(output ApiUrl)

  echo "==> Building the site against ${API_URL}"
  (cd frontend && npm ci --no-audit --no-fund &&
    NEXT_PUBLIC_API_URL="$API_URL" NEXT_PUBLIC_REPO_URL="${REPO_URL:-}" npm run build)

  echo "==> Uploading to Amplify app ${APP_ID}"
  rm -f dist.zip
  (cd frontend/out && zip -r -q ../../dist.zip .)
  DEPLOYMENT=$(aws amplify create-deployment --app-id "$APP_ID" --branch-name "$BRANCH" --region "$REGION" --output json)
  UPLOAD_URL=$(echo "$DEPLOYMENT" | python3 -c "import sys,json;print(json.load(sys.stdin)['zipUploadUrl'])")
  JOB=$(echo "$DEPLOYMENT" | python3 -c "import sys,json;print(json.load(sys.stdin)['jobId'])")
  curl -s -H "Content-Type: application/zip" --upload-file dist.zip "$UPLOAD_URL"
  aws amplify start-deployment --app-id "$APP_ID" --branch-name "$BRANCH" --job-id "$JOB" --region "$REGION" >/dev/null
  while true; do
    STATUS=$(aws amplify get-job --app-id "$APP_ID" --branch-name "$BRANCH" --job-id "$JOB" --region "$REGION" \
      --query "job.summary.status" --output text)
    echo "    status: $STATUS"
    case "$STATUS" in
      SUCCEED) break ;;
      FAILED | CANCELLED) echo "Deployment $STATUS"; exit 1 ;;
    esac
    sleep 5
  done
  rm -f dist.zip
  echo "    Live at https://${BRANCH}.$(output AmplifyDefaultDomain)"
}

upsert_cname() {
  # $1 = record name, $2 = target
  aws route53 change-resource-record-sets --hosted-zone-id "$ZONE_ID" --change-batch \
    "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"$1\",\"Type\":\"CNAME\",\"TTL\":300,\"ResourceRecords\":[{\"Value\":\"$2\"}]}}]}" \
    >/dev/null
  echo "    CNAME $1 -> $2"
}

domain() {
  APP_ID=$(output AmplifyAppId)
  ZONE_ID=$(aws route53 list-hosted-zones-by-name --dns-name "$HOSTED_ZONE_NAME" \
    --query "HostedZones[0].Id" --output text | sed 's|/hostedzone/||')

  echo "==> Attaching ${SITE_DOMAIN} to Amplify app ${APP_ID}"
  aws amplify get-domain-association --app-id "$APP_ID" --domain-name "$ROOT_DOMAIN" --region "$REGION" >/dev/null 2>&1 ||
    aws amplify create-domain-association --app-id "$APP_ID" --domain-name "$ROOT_DOMAIN" --region "$REGION" \
      --sub-domain-settings "prefix=${PREFIX},branchName=${BRANCH}" >/dev/null

  # Amplify only writes DNS records itself when a hosted zone is named exactly like the
  # domain. Ours lives in the parent zone (ucsciba.org), so copy the records it asks for.
  for _ in $(seq 1 60); do
    ASSOCIATION=$(aws amplify get-domain-association --app-id "$APP_ID" --domain-name "$ROOT_DOMAIN" \
      --region "$REGION" --output json)
    STATUS=$(echo "$ASSOCIATION" | python3 -c "import sys,json;print(json.load(sys.stdin)['domainAssociation']['domainStatus'])")
    VERIFY=$(echo "$ASSOCIATION" | python3 -c "import sys,json;print(json.load(sys.stdin)['domainAssociation'].get('certificateVerificationDNSRecord') or '')")
    TARGET=$(echo "$ASSOCIATION" | python3 -c "import sys,json;print(json.load(sys.stdin)['domainAssociation']['subDomains'][0].get('dnsRecord') or '')")
    echo "    status: $STATUS"
    if [ -n "$VERIFY" ] && [ -z "${VERIFY_DONE:-}" ]; then
      upsert_cname "$(echo "$VERIFY" | awk '{print $1}')" "$(echo "$VERIFY" | awk '{print $3}')"
      VERIFY_DONE=1
    fi
    if [ -n "$TARGET" ] && [ "$(echo "$TARGET" | awk '{print $3}')" != "<pending>" ] && [ -z "${TARGET_DONE:-}" ]; then
      upsert_cname "${SITE_DOMAIN}." "$(echo "$TARGET" | awk '{print $3}')"
      TARGET_DONE=1
    fi
    case "$STATUS" in
      AVAILABLE) echo "    Live at https://${SITE_DOMAIN}"; return ;;
      FAILED) echo "Domain association failed"; exit 1 ;;
    esac
    sleep 20
  done
  echo "Still verifying. Re-run 'scripts/deploy.sh domain' in a few minutes."
}

case "${1:-all}" in
  backend) backend ;;
  data) data ;;
  frontend) frontend ;;
  domain) domain ;;
  all) backend; data; frontend; domain ;;
  *) echo "usage: $0 [backend|data|frontend|domain|all]"; exit 2 ;;
esac
