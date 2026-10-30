# AWS Setup Guide — Music Platform

This document covers everything needed to reproduce the AWS infrastructure
for this project from scratch. The architecture, Lambda code, IAM policy,
DynamoDB schema, and API Gateway wiring were designed and built with
[Amazon Q Developer](https://aws.amazon.com/q/developer/) — the AI assistant
built into the IDE that wrote the Lambda handlers, debugged the DynamoDB GSI
constraints, fixed the CORS headers, hardened the WAF, and generally did the
heavy lifting throughout.

---

## Prerequisites

- AWS CLI installed and configured (`aws configure`)
- Python 3.12
- An AWS account with permissions to create Lambda, DynamoDB, API Gateway,
  IAM, WAFv2, and Secrets Manager resources

---

## 1. DynamoDB Table

```bash
aws dynamodb create-table \
  --table-name music-tracks \
  --attribute-definitions \
    AttributeName=track_id,AttributeType=S \
    AttributeName=genre,AttributeType=S \
    AttributeName=content_type,AttributeType=S \
    AttributeName=artist_id,AttributeType=S \
    AttributeName=album_id,AttributeType=S \
    AttributeName=track_number,AttributeType=N \
  --key-schema \
    AttributeName=track_id,KeyType=HASH \
  --global-secondary-indexes \
    "[
      {
        \"IndexName\": \"GenreIndex\",
        \"KeySchema\": [{\"AttributeName\":\"genre\",\"KeyType\":\"HASH\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"ContentTypeIndex\",
        \"KeySchema\": [{\"AttributeName\":\"content_type\",\"KeyType\":\"HASH\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"ArtistIndex\",
        \"KeySchema\": [{\"AttributeName\":\"artist_id\",\"KeyType\":\"HASH\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      },
      {
        \"IndexName\": \"AlbumIndex\",
        \"KeySchema\": [
          {\"AttributeName\":\"album_id\",\"KeyType\":\"HASH\"},
          {\"AttributeName\":\"track_number\",\"KeyType\":\"RANGE\"}
        ],
        \"Projection\": {\"ProjectionType\":\"ALL\"}
      }
    ]" \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

> **Note:** `track_number` is a GSI sort key — never write it as `null`.
> Omit the field entirely if the value is not known.

---

## 2. IAM Role for Lambda

Create the trust policy file `lambda-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "lambda.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
```

Create the role:

```bash
aws iam create-role \
  --role-name music-lambda-role \
  --assume-role-policy-document file://lambda-trust-policy.json
```

Attach the permissions policy (`lambda-policy.json` in this repo):

```bash
aws iam put-role-policy \
  --role-name music-lambda-role \
  --policy-name music-lambda-policy \
  --policy-document file://lambda-policy.json
```

The policy grants: `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`,
`dynamodb:Query`, `dynamodb:Scan` on the `music-tracks` table and all its GSIs,
plus `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`.

---

## 3. Lambda Functions

Each function is a single `.py` file zipped and deployed. All share the same
role and environment variables.

### Package a function

```bash
cd backend/api
zip <name>.zip <name>.py
```

### Deploy

Replace `<name>` and `<handler>` for each function below.

```bash
aws lambda create-function \
  --function-name music-<name> \
  --runtime python3.12 \
  --role arn:aws:iam::<ACCOUNT_ID>:role/music-lambda-role \
  --handler <name>.handler \
  --zip-file fileb://<name>.zip \
  --environment "Variables={DYNAMODB_TABLE=music-tracks}" \
  --timeout 30 \
  --memory-size 256 \
  --region us-east-1
```

### Functions

| Function name   | File            | Handler          | Purpose                        |
|-----------------|-----------------|------------------|--------------------------------|
| `music-search`  | `search.py`     | `search.handler` | Text / genre / type search     |
| `music-track`   | `track.py`      | `track.handler`  | Single track by ID             |
| `music-stats`   | `stats.py`      | `stats.handler`  | Catalog stats                  |
| `music-artists` | `artists.py`    | `artists.handler`| Artist search                  |
| `music-albums`  | `albums.py`     | `albums.handler` | Album search                   |
| `music-radio`   | `radio.py`      | `radio.handler`  | Randomised genre radio         |

### Update an existing function

```bash
aws lambda update-function-code \
  --function-name music-<name> \
  --zip-file fileb://<name>.zip \
  --region us-east-1
```

---

## 4. API Gateway (REST API)

### Create the API

```bash
aws apigateway create-rest-api \
  --name music-api \
  --region us-east-1
```

Note the `id` returned — this is your `<API_ID>`.

Get the root resource ID:

```bash
aws apigateway get-resources \
  --rest-api-id <API_ID> \
  --region us-east-1
```

### Create resources and wire Lambda

For each route, the pattern is:

```bash
# 1. Create resource
aws apigateway create-resource \
  --rest-api-id <API_ID> \
  --parent-id <PARENT_ID> \
  --path-part <path-part> \
  --region us-east-1

# 2. Add GET method (no auth)
aws apigateway put-method \
  --rest-api-id <API_ID> \
  --resource-id <RESOURCE_ID> \
  --http-method GET \
  --authorization-type NONE \
  --region us-east-1

# 3. Wire Lambda proxy integration
aws apigateway put-integration \
  --rest-api-id <API_ID> \
  --resource-id <RESOURCE_ID> \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:<ACCOUNT_ID>:function:music-<name>/invocations" \
  --region us-east-1

# 4. Grant invoke permission
aws lambda add-permission \
  --function-name music-<name> \
  --statement-id apigw-<name>-get \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:<ACCOUNT_ID>:<API_ID>/*/GET/<path>" \
  --region us-east-1
```

### Routes

| Path              | Function        |
|-------------------|-----------------|
| `/stats`          | `music-stats`   |
| `/tracks/{id}`    | `music-track`   |
| `/tracks/search`  | `music-search`  |
| `/artists/search` | `music-artists` |
| `/albums/search`  | `music-albums`  |
| `/radio`          | `music-radio`   |

> `/tracks/search` must be created before `/tracks/{id}` — API Gateway matches
> literal path parts before path parameters.

### Deploy to a stage

```bash
aws apigateway create-deployment \
  --rest-api-id <API_ID> \
  --stage-name v1 \
  --region us-east-1
```

Your base URL will be:
`https://<API_ID>.execute-api.us-east-1.amazonaws.com/v1`

Update `js/api.js` with this URL.

---

## 5. WAF (Rate Limiting)

```bash
aws wafv2 create-web-acl \
  --name music-api-waf \
  --scope REGIONAL \
  --default-action Allow={} \
  --rules '[{
    "Name": "RateLimit",
    "Priority": 1,
    "Statement": {
      "RateBasedStatement": {
        "Limit": 1000,
        "AggregateKeyType": "IP"
      }
    },
    "Action": { "Block": {} },
    "VisibilityConfig": {
      "SampledRequestsEnabled": true,
      "CloudWatchMetricsEnabled": true,
      "MetricName": "RateLimit"
    }
  }]' \
  --visibility-config SampledRequestsEnabled=true,CloudWatchMetricsEnabled=true,MetricName=music-api-waf \
  --region us-east-1
```

Associate with the API Gateway stage:

```bash
aws wafv2 associate-web-acl \
  --web-acl-arn <WAF_ACL_ARN> \
  --resource-arn "arn:aws:apigateway:us-east-1::/restapis/<API_ID>/stages/v1" \
  --region us-east-1
```

---

## 6. Secrets Manager

API keys for ingestion adapters are stored here. The Lambda functions
themselves don't read these — they're used by the local ingestion scripts.

```bash
aws secretsmanager create-secret \
  --name music/jamendo \
  --secret-string '{"client_id":"<your_jamendo_client_id>"}' \
  --region us-east-1

aws secretsmanager create-secret \
  --name music/metabrainz \
  --secret-string '{"user_agent":"<app>/<version> ( <email> )"}' \
  --region us-east-1
```

---

## 7. GitHub Pages

The frontend is a static PWA served from the `master` branch root.

1. Repo: `<username>/music`
2. GitHub Pages → Source: `master` branch, `/ (root)`
3. Site URL: `https://<username>.github.io/music/`
4. All asset paths in `index.html`, `js/`, `service-worker.js` use the
   `/music/` prefix to match the subdirectory.

---

## Key Gotchas

- **DynamoDB GSI keys cannot be `null`** — omit the field entirely if the
  value is absent, or the write will be rejected.
- **DynamoDB requires `Decimal` not `float`** — coerce all numeric values
  from external APIs with `Decimal(str(float(val)))`.
- **`overflow-x: hidden` on `body` kills scroll** — browsers implicitly
  create a new scroll container. Use `overflow-x: clip` instead.
- **`/tracks/search` before `/tracks/{id}`** — API Gateway resource creation
  order matters; literal segments must exist before parameterised ones.
- **Lambda proxy integration uses `POST`** — the `--integration-http-method`
  is always `POST` even for GET routes. This is correct.
