#  Serverless Automation Factory

A professional Flask-based web application for deploying and demonstrating AWS Serverless architectures — built for classroom training environments.

---

## Overview

The **Serverless Automation Factory** is a complete cloud management dashboard that allows instructors and learners to:

- Deploy full AWS serverless environments via a web UI (no console needed)
- Demonstrate two end-to-end pipelines live in the classroom
- Destroy all created resources cleanly, avoiding AWS cost leakage

---

## Supported Workflows

### 1. Resume Processing Pipeline
```
S3 Upload → Lambda → DynamoDB → SNS Notification
```
HR scenario: Automatically processes uploaded resumes, stores records in DynamoDB, and sends notifications via SNS.

### 2. Order Processing Pipeline
```
EventBridge → Step Functions → ValidateOrder → ProcessPayment → SendNotification
                                                     │                  │
                                               (on failure)        SES Email
                                                     │            SNS Fan-out
                                          NotifyFailure Lambda          │
                                               │         │         SQS OrdersQueue
                                           SES Email   SNS
                                                     │
                                                SQS DLQ (raw error stored)
```

E-commerce scenario: Full order lifecycle with:
- **SES** for reliable transactional email (success & failure)
- **SNS fan-out** broadcasting order events to all subscribers simultaneously
- **SQS OrdersQueue** receiving all order events from SNS
- **SQS DLQ** capturing raw payment failure errors for investigation
- Retry logic (3 attempts with exponential backoff) on payment failures

---

##  Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5, Bootstrap 5, Font Awesome, JavaScript/AJAX |
| Backend | Python 3.12, Flask, Boto3 |
| Database | SQLite (local deployment metadata) |
| AWS | S3, Lambda, DynamoDB, SNS, SES, SQS, Step Functions, EventBridge, IAM, CloudWatch |

---

##  Setup Instructions

### Prerequisites

- Python 3.12+
- AWS account with programmatic access
- IAM user with the following permissions:
  - `AmazonS3FullAccess`
  - `AWSLambda_FullAccess`
  - `AmazonDynamoDBFullAccess`
  - `AmazonSNSFullAccess`
  - `AmazonSESFullAccess`
  - `AWSStepFunctionsFullAccess`
  - `AmazonEventBridgeFullAccess`
  - `AmazonSQSFullAccess`
  - `IAMFullAccess`
  - `CloudWatchLogsFullAccess`

### Step 1: Clone / Extract

```bash
cd serverless_factory
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure AWS Credentials

**Option A — Environment Variables (Recommended for demos):**
```bash
# Linux/Mac
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1

# Windows (PowerShell)
$env:AWS_ACCESS_KEY_ID="your_access_key"
$env:AWS_SECRET_ACCESS_KEY="your_secret_key"
$env:AWS_DEFAULT_REGION="us-east-1"
```

**Option B — .env file:**
```bash
cp .env.example .env
# Edit .env with your real credentials
```

**Option C — AWS CLI Profile:**
```bash
aws configure
```

### Step 5: Verify Your Email in AWS SES (Required for Order Pipeline)

The Order Pipeline sends emails via **AWS SES** (not SNS subscription). You must verify your email once before deploying:

1. Go to **AWS Console → SES → Verified Identities** (us-east-1)
2. Click **Create Identity → Email Address**
3. Enter the email you will use for notifications
4. Click the verification link AWS sends to that email

> This is a one-time step. After verification, emails are sent reliably with no subscription confirmations or deactivation issues.

### Step 6: Run the Application

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

---

## Dashboard Pages

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Overview, stats, architecture diagrams |
| Resume Pipeline | `/resume-pipeline` | Deploy & test the HR resume pipeline |
| Order Workflow | `/order-pipeline` | Deploy & test the e-commerce order workflow |
| Resource Inventory | `/inventory` | Live view of all AWS resources |
| Deployment History | `/history` | SQLite-backed deployment records |
| CloudWatch Logs | `/logs` | Lambda log viewer |
| Destroy | `/destroy` | Clean teardown of all resources |

---

## Classroom Demo Flow

### Demo 1: Resume Processing Pipeline

1. Go to **Resume Pipeline** → fill in form → click **Deploy Pipeline**
2. Watch the real-time deployment progress (IAM → S3 → DynamoDB → SNS → Lambda → Trigger)
3. Upload a sample PDF resume using the drag-and-drop panel
4. Watch the processing timeline animate
5. Refresh DynamoDB Records to see the stored entry

### Demo 2: Order Processing Pipeline

1. Go to **Order Workflow** → fill in form → click **Deploy Workflow**
2. Deployment creates: IAM Roles → SNS Topic → SQS OrdersQueue (subscribed to SNS) → SQS DLQ → 4 Lambda functions → Step Functions state machine → EventBridge rule
3. Enter order details → click **Start Workflow**
4. Watch Step Functions animate through: ValidateOrder → ProcessPayment → SendNotification
5. Check inbox — **SES sends the Order Confirmed email** directly
6. Open **AWS Console → SQS → OrdersQueue** — see the `ORDER_COMPLETED` JSON event delivered via SNS fan-out

**Demonstrate Failure Path:**

7. Enable **Simulate Payment Failure** → click **Start Workflow**
8. Step Functions retries payment 3 times (watch the retry states)
9. After retries, NotifyPaymentFailed Lambda runs → **SES sends Order Failed alert email**
10. Open **AWS Console → SQS → OrdersQueue** — see the `ORDER_FAILED` event
11. Open **AWS Console → SQS → OrderDLQ** — see the raw error details stored for investigation

**What to highlight in the AWS Console:**

| Console Location | What to Show |
|---|---|
| Step Functions → Executions | Visual workflow with green/red states |
| SNS → Topics → Subscriptions | OrdersQueue subscribed to the topic |
| SQS → OrdersQueue | JSON order events received via SNS fan-out |
| SQS → OrderDLQ | Raw error from failed payment |
| SES → Sending Statistics | Email delivery activity |
| CloudWatch → Log Groups | Lambda execution logs |

### Teardown

1. Go to **Destroy Infrastructure**
2. Select the pipeline(s) to destroy
3. Confirm and watch the destruction sequence

---

## Project Structure

```
serverless_factory/
├── app.py                              # Flask application & all API routes
├── config.py                           # App configuration
├── requirements.txt
├── .env.example
├── README.md
│
├── services/                           # AWS service wrappers (Boto3)
│   ├── __init__.py
│   ├── iam_service.py                  # IAM role creation (includes SES policy)
│   ├── s3_service.py
│   ├── lambda_service.py
│   ├── sns_service.py                  # SNS topic, SQS subscription, fan-out
│   ├── dynamodb_service.py
│   ├── sqs_service.py                  # OrdersQueue, DLQ, SNS allow policy
│   ├── stepfunctions_service.py        # State machine with failure notification states
│   ├── eventbridge_service.py
│   └── cloudwatch_service.py
│
├── templates/                          # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── resume_pipeline.html
│   ├── order_pipeline.html
│   ├── inventory.html
│   ├── history.html
│   ├── logs.html
│   └── destroy.html
│
├── lambda_functions/                   # Lambda source code
│   ├── resume_processor.py             # S3 trigger → DynamoDB + SNS
│   ├── validate_order.py               # Validates order_id, customer_name, amount
│   ├── process_payment.py              # Payment processing (supports failure sim)
│   ├── send_notification.py            # Success: SES email + SNS fan-out publish
│   └── send_failure_notification.py    # Failure: SES email + SNS fan-out publish
│
├── docs/
│   └── architecture_explained.md      # Full architecture explanation (layman + technical)
│
└── database/
    └── app.db                          # SQLite (auto-created on first run)
```

---

## API Reference

### Resume Pipeline
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/deploy/resume` | Deploy full resume pipeline |
| POST | `/api/resume/upload` | Upload a resume file |
| GET | `/api/resume/records` | List DynamoDB records |

### Order Pipeline
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/deploy/order` | Deploy order workflow (SNS + SQS + SES + Step Functions) |
| POST | `/api/order/execute` | Start a Step Functions execution |
| POST | `/api/order/status` | Poll execution status and event history |

### Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/inventory?region=us-east-1` | List all AWS resources |
| GET | `/api/logs?function=NAME&hours=1` | Fetch CloudWatch logs |
| GET | `/api/health` | Health check |

### Destruction
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/destroy/resume` | Destroy resume pipeline |
| POST | `/api/destroy/order` | Destroy order pipeline (includes OrdersQueue + DLQ) |

---

## Important Notes

1. **SES email verification is required** before deploying the Order Pipeline. Verify your email in AWS SES Console (us-east-1) → Verified Identities.
2. **IAM Role Creation requires `iam:CreateRole` permission** — ensure your AWS user has this.
3. **S3 bucket names must be globally unique** — use a suffix like your name or date.
4. **Lambda cold start** — first invocation after deployment may take a few seconds.
5. **SNS → SQS subscription is auto-confirmed** — no email confirmation needed for the OrdersQueue.
6. **Step Functions retries payment 3 times** before routing to the failure notification path.
7. **Always destroy after demo** — avoid unnecessary AWS charges.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `NoCredentialsError` | Check AWS env vars or run `aws configure` |
| `BucketAlreadyExists` | Use a unique bucket name |
| `AccessDenied` | Add missing IAM permissions to your AWS user |
| `MessageRejected` from SES | Email not verified in SES — complete Step 5 of setup |
| Lambda not triggering | Wait 10s after deploy; check S3 event notification config |
| No email received | Check SES Verified Identities; check spam folder |
| SQS OrdersQueue empty | Confirm SNS → SQS subscription is confirmed in SNS console |
| DLQ empty after failure | Ensure simulate_failure flag is set; check Step Functions execution logs |

---

## License

MIT — Free to use for educational purposes.
