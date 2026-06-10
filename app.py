import os
import json
import logging
import boto3
import sqlite3
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from services.iam_service import IAMService
from services.s3_service import S3Service
from services.lambda_service import LambdaService
from services.sns_service import SNSService
from services.dynamodb_service import DynamoDBService
from services.sqs_service import SQSService
from services.stepfunctions_service import StepFunctionsService
from services.eventbridge_service import EventBridgeService
from services.cloudwatch_service import CloudWatchService
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# ── Database helpers ──────────────────────────────────────────────────────────

def init_db():
    os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS deployments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            type             TEXT    NOT NULL,
            region           TEXT    NOT NULL,
            status           TEXT    NOT NULL,
            config           TEXT,
            resources        TEXT,
            resources_count  INTEGER DEFAULT 0,
            created_at       TEXT    NOT NULL,
            updated_at       TEXT    NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _db():
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_deployment(name, dtype, region, status, config, resources=None):
    conn = _db()
    now = datetime.utcnow().isoformat()
    rcount = len(resources) if resources else 0
    conn.execute(
        """INSERT INTO deployments
           (name, type, region, status, config, resources, resources_count, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (name, dtype, region, status,
         json.dumps(config),
         json.dumps(resources or {}),
         rcount, now, now)
    )
    conn.commit()
    conn.close()


def update_deployment(name, status, resources=None):
    conn = _db()
    now = datetime.utcnow().isoformat()
    if resources:
        conn.execute(
            "UPDATE deployments SET status=?, resources=?, resources_count=?, updated_at=? WHERE name=?",
            (status, json.dumps(resources), len(resources), now, name)
        )
    else:
        conn.execute(
            "UPDATE deployments SET status=?, updated_at=? WHERE name=?",
            (status, now, name)
        )
    conn.commit()
    conn.close()


def get_deployment(name):
    conn = _db()
    row = conn.execute(
        "SELECT * FROM deployments WHERE name=? ORDER BY id DESC LIMIT 1", (name,)
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["config"]    = json.loads(d["config"]    or "{}")
        d["resources"] = json.loads(d["resources"] or "{}")
        return d
    return None


def get_all_deployments():
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM deployments ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["config"]    = json.loads(d["config"]    or "{}")
        d["resources"] = json.loads(d["resources"] or "{}")
        result.append(d)
    return result


def aws_account_id(region):
    try:
        return boto3.client("sts", region_name=region).get_caller_identity()["Account"]
    except Exception:
        return None


# ── Page routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    deployments = get_all_deployments()
    stats = {
        "total":     len(deployments),
        "active":    sum(1 for d in deployments if d["status"] == "ACTIVE"),
        "failed":    sum(1 for d in deployments if d["status"] == "FAILED"),
        "destroyed": sum(1 for d in deployments if d["status"] == "DESTROYED"),
    }
    return render_template(
        "dashboard.html",
        deployments=deployments[:5],
        stats=stats,
        regions=Config.REGIONS
    )


@app.route("/resume-pipeline")
def resume_pipeline():
    dep = get_deployment("resume_pipeline_active")
    return render_template("resume_pipeline.html",
        deployment=dep,
        regions=Config.REGIONS,
        default_role_name=Config.DEFAULT_RESUME_ROLE_NAME,
    )


@app.route("/order-pipeline")
def order_pipeline():
    dep = get_deployment("order_pipeline_active")
    return render_template("order_pipeline.html",
        deployment=dep,
        regions=Config.REGIONS,
        default_lambda_role=Config.DEFAULT_ORDER_LAMBDA_ROLE,
        default_sf_role=Config.DEFAULT_ORDER_SF_ROLE,
        default_eb_role=Config.DEFAULT_ORDER_EB_ROLE,
    )


@app.route("/history")
def history():
    return render_template("history.html", deployments=get_all_deployments())


@app.route("/inventory")
def inventory():
    return render_template("inventory.html", regions=Config.REGIONS)


@app.route("/destroy")
def destroy():
    return render_template(
        "destroy.html",
        resume_dep=get_deployment("resume_pipeline_active"),
        order_dep=get_deployment("order_pipeline_active")
    )


@app.route("/logs")
def logs():
    return render_template("logs.html", regions=Config.REGIONS)


# ── Resume pipeline API ───────────────────────────────────────────────────────

@app.route("/api/deploy/resume", methods=["POST"])
def api_deploy_resume():
    data         = request.get_json() or {}
    region       = data.get("region", "us-east-1")
    project_name = data.get("project_name", "ResumeFactory")
    bucket_name  = data.get("bucket_name", "").strip()
    table_name   = data.get("table_name", "ResumeProcessing").strip()
    sns_name     = data.get("sns_topic_name", "ResumeNotifications").strip()
    lambda_name  = data.get("lambda_name", "ResumeProcessor").strip()
    email        = data.get("email", "").strip()

    if not bucket_name or not email:
        return jsonify(success=False, error="bucket_name and email are required"), 400

    steps = []

    def step(msg, status="ok", error=None):
        s = {"message": msg, "status": status}
        if error:
            s["error"] = str(error)
        steps.append(s)

    resources = {}

    try:
        iam    = IAMService(region)
        s3     = S3Service(region)
        dynamo = DynamoDBService(region)
        sns    = SNSService(region)
        lmb    = LambdaService(region)

        role_name = data.get("role_name", "").strip() or f"{project_name}-LambdaRole"
        role_arn  = iam.create_lambda_role(role_name)
        resources["iam_role"] = {"name": role_name, "arn": role_arn, "type": "IAM Role"}
        step("IAM Role Created")

        bucket_arn = s3.create_bucket(bucket_name)
        resources["s3_bucket"] = {"name": bucket_name, "arn": bucket_arn, "type": "S3 Bucket"}
        step("S3 Bucket Created")

        table_arn = dynamo.create_table(table_name)
        resources["dynamodb_table"] = {"name": table_name, "arn": table_arn, "type": "DynamoDB Table"}
        step("DynamoDB Table Created")

        topic_arn = sns.create_topic(sns_name)
        resources["sns_topic"] = {"name": sns_name, "arn": topic_arn, "type": "SNS Topic"}
        step("SNS Topic Created")

        sns.subscribe_email(topic_arn, email)
        step("Email Subscription Added (confirm via inbox)")

        lambda_src = os.path.join(Config.LAMBDA_DIR, "resume_processor.py")
        lambda_arn = lmb.create_function(
            function_name=lambda_name,
            handler="resume_processor.lambda_handler",
            role_arn=role_arn,
            source_file=lambda_src,
            env_vars={"DYNAMODB_TABLE": table_name, "SNS_TOPIC_ARN": topic_arn}
        )
        resources["lambda_function"] = {"name": lambda_name, "arn": lambda_arn, "type": "Lambda Function"}
        step("Lambda Function Created & Deployed")

        acct = aws_account_id(region)
        if acct:
            lmb_client = boto3.client("lambda", region_name=region)
            s3.add_lambda_permission_for_s3(lmb_client, lambda_name, bucket_name, acct)

        s3.configure_s3_trigger(bucket_name, lambda_arn)
        step("S3 Event Trigger Configured")

        cfg = {
            "region": region, "bucket_name": bucket_name,
            "table_name": table_name, "sns_topic_name": sns_name,
            "sns_topic_arn": topic_arn, "lambda_name": lambda_name,
            "email": email, "role_name": role_name,
        }
        save_deployment("resume_pipeline_active", "Resume Pipeline", region, "ACTIVE", cfg, resources)
        step("Pipeline Ready ✓")

        return jsonify(success=True, steps=steps, resources=resources)

    except Exception as exc:
        step(f"Deployment failed: {exc}", "error", exc)
        logger.exception("Resume deploy error")
        return jsonify(success=False, steps=steps, error=str(exc)), 500


@app.route("/api/resume/upload", methods=["POST"])
def api_resume_upload():
    dep = get_deployment("resume_pipeline_active")
    if not dep or dep["status"] != "ACTIVE":
        return jsonify(success=False, error="No active Resume Pipeline found"), 400

    file = request.files.get("resume")
    if not file:
        return jsonify(success=False, error="No file provided"), 400

    region      = dep["config"]["region"]
    bucket_name = dep["config"]["bucket_name"]
    table_name  = dep["config"]["table_name"]

    s3     = S3Service(region)
    dynamo = DynamoDBService(region)

    try:
        s3.upload_file(bucket_name, file.filename, file)
        time.sleep(4)   # allow Lambda to process
        records  = dynamo.scan_table(table_name)
        matching = [r for r in records if file.filename in r.get("file_name", "")]
        return jsonify(success=True, records=matching[:5], file_name=file.filename)
    except Exception as exc:
        logger.exception("Upload error")
        return jsonify(success=False, error=str(exc)), 500


@app.route("/api/resume/records")
def api_resume_records():
    dep = get_deployment("resume_pipeline_active")
    if not dep or dep["status"] != "ACTIVE":
        return jsonify(records=[])
    dynamo  = DynamoDBService(dep["config"]["region"])
    records = dynamo.scan_table(dep["config"]["table_name"])
    return jsonify(records=records)


# ── Order pipeline API ────────────────────────────────────────────────────────

@app.route("/api/deploy/order", methods=["POST"])
def api_deploy_order():
    data             = request.get_json() or {}
    region           = data.get("region", "us-east-1")
    project_name     = data.get("project_name", "OrderFactory")
    state_machine    = data.get("state_machine_name", "OrderProcessing")
    eb_rule_name     = data.get("eb_rule_name", "OrderEventRule")
    dlq_name         = data.get("dlq_name", "OrderDLQ")
    email            = data.get("email", "").strip()

    if not email:
        return jsonify(success=False, error="email is required"), 400

    steps = []
    def step(msg, status="ok", error=None):
        s = {"message": msg, "status": status}
        if error:
            s["error"] = str(error)
        steps.append(s)

    resources = {}

    try:
        iam = IAMService(region)
        sns = SNSService(region)
        sqs = SQSService(region)
        lmb = LambdaService(region)
        sf  = StepFunctionsService(region)
        eb  = EventBridgeService(region)

        # IAM Roles
        lambda_role_name = data.get("lambda_role_name", "").strip() or f"{project_name}-LambdaRole"
        lambda_role_arn  = iam.create_lambda_role(lambda_role_name,
            additional_policies=["arn:aws:iam::aws:policy/AmazonSQSFullAccess"])
        resources["lambda_role"] = {"name": lambda_role_name, "arn": lambda_role_arn, "type": "IAM Role"}
        step("Lambda IAM Role Created")

        sf_role_name = data.get("sf_role_name", "").strip() or f"{project_name}-StepFnRole"
        sf_role_arn  = iam.create_stepfunctions_role(sf_role_name)
        resources["sf_role"] = {"name": sf_role_name, "arn": sf_role_arn, "type": "IAM Role"}
        step("Step Functions IAM Role Created")

        eb_role_name = data.get("eb_role_name_input", "").strip() or f"{project_name}-EventBridgeRole"
        eb_role_arn  = iam.create_eventbridge_role(eb_role_name)
        resources["eb_role"] = {"name": eb_role_name, "arn": eb_role_arn, "type": "IAM Role"}
        step("EventBridge IAM Role Created")

        # SNS topic — fan-out hub; lambdas publish events here, SQS queue subscribes
        topic_name = f"{project_name}-Notifications"
        topic_arn  = sns.create_topic(topic_name)
        resources["sns_topic"] = {"name": topic_name, "arn": topic_arn, "type": "SNS Topic"}
        step("SNS Topic Created")

        # SQS OrdersQueue — subscribes to SNS, receives every order event (success + failure)
        orders_queue_name = f"{project_name}-OrdersQueue"
        orders_queue_url, orders_queue_arn = sqs.create_queue(orders_queue_name)
        sqs.allow_sns_to_send(orders_queue_url, orders_queue_arn, topic_arn)
        sns.subscribe_sqs(topic_arn, orders_queue_arn)
        resources["sqs_orders_queue"] = {"name": orders_queue_name, "arn": orders_queue_arn, "url": orders_queue_url, "type": "SQS Queue"}
        step("SQS Orders Queue Created & Subscribed to SNS")

        # SQS DLQ — receives raw failed payment errors from Step Functions
        dlq_url, dlq_arn = sqs.create_dlq(dlq_name)
        resources["sqs_dlq"] = {"name": dlq_name, "arn": dlq_arn, "url": dlq_url, "type": "SQS Queue"}
        step("SQS Dead Letter Queue Created")

        # Lambda functions
        validate_name = f"{project_name}-ValidateOrder"
        validate_arn  = lmb.create_function(
            validate_name, "validate_order.lambda_handler", lambda_role_arn,
            os.path.join(Config.LAMBDA_DIR, "validate_order.py")
        )
        resources["validate_lambda"] = {"name": validate_name, "arn": validate_arn, "type": "Lambda Function"}
        step("ValidateOrder Lambda Created")

        payment_name = f"{project_name}-ProcessPayment"
        payment_arn  = lmb.create_function(
            payment_name, "process_payment.lambda_handler", lambda_role_arn,
            os.path.join(Config.LAMBDA_DIR, "process_payment.py")
        )
        resources["payment_lambda"] = {"name": payment_name, "arn": payment_arn, "type": "Lambda Function"}
        step("ProcessPayment Lambda Created")

        notify_name = f"{project_name}-SendNotification"
        notify_arn  = lmb.create_function(
            notify_name, "send_notification.lambda_handler", lambda_role_arn,
            os.path.join(Config.LAMBDA_DIR, "send_notification.py"),
            env_vars={"NOTIFICATION_EMAIL": email, "SNS_TOPIC_ARN": topic_arn}
        )
        resources["notify_lambda"] = {"name": notify_name, "arn": notify_arn, "type": "Lambda Function"}
        step("SendNotification Lambda Created")

        fail_notify_name = f"{project_name}-SendFailureNotification"
        fail_notify_arn  = lmb.create_function(
            fail_notify_name, "send_failure_notification.lambda_handler", lambda_role_arn,
            os.path.join(Config.LAMBDA_DIR, "send_failure_notification.py"),
            env_vars={"NOTIFICATION_EMAIL": email, "SNS_TOPIC_ARN": topic_arn}
        )
        resources["fail_notify_lambda"] = {"name": fail_notify_name, "arn": fail_notify_arn, "type": "Lambda Function"}
        step("SendFailureNotification Lambda Created")

        # Step Functions
        definition = sf.build_order_state_machine(validate_arn, payment_arn, notify_arn, fail_notify_arn, dlq_url)
        sm_arn     = sf.create_state_machine(state_machine, definition, sf_role_arn)
        resources["state_machine"] = {"name": state_machine, "arn": sm_arn, "type": "Step Function"}
        step("Step Functions State Machine Created")

        # EventBridge
        eb_arn = eb.create_rule(eb_rule_name, sm_arn, eb_role_arn)
        resources["eb_rule"] = {"name": eb_rule_name, "arn": eb_arn, "type": "EventBridge Rule"}
        step("EventBridge Rule Created")

        cfg = {
            "region": region, "project_name": project_name,
            "state_machine_name": state_machine, "state_machine_arn": sm_arn,
            "eb_rule_name": eb_rule_name, "dlq_name": dlq_name,
            "dlq_arn": dlq_arn, "dlq_url": dlq_url,
            "orders_queue_name": orders_queue_name, "orders_queue_url": orders_queue_url,
            "email": email, "sns_topic_arn": topic_arn,
            "lambda_role_name": lambda_role_name, "sf_role_name": sf_role_name,
            "eb_role_name": eb_role_name,
            "validate_lambda": validate_name,
            "payment_lambda": payment_name,
            "notify_lambda": notify_name,
            "fail_notify_lambda": fail_notify_name,
        }
        save_deployment("order_pipeline_active", "Order Pipeline", region, "ACTIVE", cfg, resources)
        step("Order Workflow Ready ✓")

        return jsonify(success=True, steps=steps, resources=resources)

    except Exception as exc:
        step(f"Deployment failed: {exc}", "error", exc)
        logger.exception("Order deploy error")
        return jsonify(success=False, steps=steps, error=str(exc)), 500


@app.route("/api/order/execute", methods=["POST"])
def api_order_execute():
    dep = get_deployment("order_pipeline_active")
    if not dep or dep["status"] != "ACTIVE":
        return jsonify(success=False, error="No active Order Pipeline found"), 400

    data             = request.get_json() or {}
    region           = dep["config"]["region"]
    sm_arn           = dep["config"]["state_machine_arn"]
    simulate_failure = data.get("simulate_failure", False)

    sf       = StepFunctionsService(region)
    order_id = f"ORD-{int(time.time())}"

    input_data = {
        "order_id":        order_id,
        "customer_name":   data.get("customer_name", "Customer"),
        "amount":          float(data.get("amount", 100)),
        "simulate_failure": simulate_failure,
    }

    try:
        exec_arn = sf.start_execution(sm_arn, f"exec-{order_id}", input_data)
        return jsonify(success=True, execution_arn=exec_arn, order_id=order_id)
    except Exception as exc:
        return jsonify(success=False, error=str(exc)), 500


@app.route("/api/order/status", methods=["POST"])
def api_order_status():
    dep  = get_deployment("order_pipeline_active")
    data = request.get_json() or {}
    exec_arn = data.get("execution_arn")

    if not dep or not exec_arn:
        return jsonify(success=False, error="Missing execution_arn or no pipeline"), 400

    sf = StepFunctionsService(dep["config"]["region"])

    try:
        execution = sf.describe_execution(exec_arn)
        history   = sf.get_execution_history(exec_arn)

        events = []
        for e in history:
            evt = {"type": e.get("type", "")}
            ts  = e.get("timestamp")
            evt["timestamp"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            if "stateEnteredEventDetails" in e:
                evt["state"] = e["stateEnteredEventDetails"].get("name", "")
            events.append(evt)

        return jsonify(
            success=True,
            status=execution.get("status", "UNKNOWN"),
            events=events[-20:]
        )
    except Exception as exc:
        return jsonify(success=False, error=str(exc)), 500


# ── Inventory API ─────────────────────────────────────────────────────────────

@app.route("/api/inventory")
def api_inventory():
    region = request.args.get("region", Config.AWS_REGION)

    try:
        s3     = S3Service(region)
        lmb    = LambdaService(region)
        sns    = SNSService(region)
        dynamo = DynamoDBService(region)
        sqs    = SQSService(region)
        sf     = StepFunctionsService(region)
        eb     = EventBridgeService(region)

        resources = []

        for b in s3.list_buckets():
            resources.append({
                "name": b["Name"], "type": "S3 Bucket",
                "arn": f"arn:aws:s3:::{b['Name']}",
                "status": "Active",
                "created": str(b.get("CreationDate", ""))
            })

        for f in lmb.list_functions():
            resources.append({
                "name": f["FunctionName"], "type": "Lambda Function",
                "arn": f["FunctionArn"], "status": "Active",
                "created": f.get("LastModified", "")
            })

        for t in sns.list_topics():
            arn = t["TopicArn"]
            resources.append({
                "name": arn.split(":")[-1], "type": "SNS Topic",
                "arn": arn, "status": "Active", "created": ""
            })

        for t in dynamo.list_tables():
            resources.append({
                "name": t, "type": "DynamoDB Table",
                "arn": dynamo.get_table_arn(t) or "",
                "status": "Active", "created": ""
            })

        for sm in sf.list_state_machines():
            resources.append({
                "name": sm["name"], "type": "State Machine",
                "arn": sm["stateMachineArn"], "status": "Active",
                "created": str(sm.get("creationDate", ""))
            })

        for rule in eb.list_rules():
            resources.append({
                "name": rule["Name"], "type": "EventBridge Rule",
                "arn": rule.get("Arn", ""),
                "status": rule.get("State", "ENABLED"), "created": ""
            })

        for url in sqs.list_queues():
            name = url.split("/")[-1]
            resources.append({
                "name": name, "type": "SQS Queue",
                "arn": sqs.get_queue_arn(url) or "",
                "status": "Active", "created": ""
            })

        return jsonify(success=True, resources=resources)

    except Exception as exc:
        logger.exception("Inventory error")
        return jsonify(success=False, error=str(exc), resources=[])


# ── CloudWatch Logs API ───────────────────────────────────────────────────────

@app.route("/api/logs")
def api_logs():
    region   = request.args.get("region", Config.AWS_REGION)
    fn_name  = request.args.get("function", "")
    hours    = int(request.args.get("hours", 1))

    try:
        cw = CloudWatchService(region)
        logs   = cw.get_lambda_logs(fn_name, hours) if fn_name else []
        groups = [g["logGroupName"] for g in cw.list_log_groups()]
        return jsonify(success=True, logs=logs, log_groups=groups)
    except Exception as exc:
        return jsonify(success=False, error=str(exc), logs=[], log_groups=[])


# ── Destroy APIs ──────────────────────────────────────────────────────────────

@app.route("/api/destroy/resume", methods=["POST"])
def api_destroy_resume():
    dep = get_deployment("resume_pipeline_active")
    if not dep or dep["status"] != "ACTIVE":
        return jsonify(success=False, error="No active Resume Pipeline to destroy"), 400

    cfg    = dep["config"]
    region = cfg["region"]
    steps  = []

    def step(msg, status="ok"):
        steps.append({"message": msg, "status": status})

    try:
        s3     = S3Service(region)
        lmb    = LambdaService(region)
        sns    = SNSService(region)
        dynamo = DynamoDBService(region)
        iam    = IAMService(region)

        s3.remove_s3_trigger(cfg.get("bucket_name", ""))
        step("S3 Trigger Removed")

        lmb.delete_function(cfg.get("lambda_name", ""))
        step("Lambda Function Deleted")

        if cfg.get("sns_topic_arn"):
            sns.delete_topic(cfg["sns_topic_arn"])
        step("SNS Subscriptions & Topic Deleted")

        dynamo.delete_table(cfg.get("table_name", ""))
        step("DynamoDB Table Deleted")

        s3.delete_bucket(cfg.get("bucket_name", ""))
        step("S3 Bucket Emptied & Deleted")

        iam.delete_role(cfg.get("role_name", ""))
        step("IAM Role Deleted")

        update_deployment("resume_pipeline_active", "DESTROYED")
        step("Resume Pipeline Destroyed ✓")

        return jsonify(success=True, steps=steps)

    except Exception as exc:
        step(f"Error: {exc}", "error")
        logger.exception("Destroy resume error")
        return jsonify(success=False, steps=steps, error=str(exc)), 500


@app.route("/api/destroy/order", methods=["POST"])
def api_destroy_order():
    dep = get_deployment("order_pipeline_active")
    if not dep or dep["status"] != "ACTIVE":
        return jsonify(success=False, error="No active Order Pipeline to destroy"), 400

    cfg    = dep["config"]
    region = cfg["region"]
    steps  = []

    def step(msg, status="ok"):
        steps.append({"message": msg, "status": status})

    try:
        eb  = EventBridgeService(region)
        sf  = StepFunctionsService(region)
        lmb = LambdaService(region)
        sns = SNSService(region)
        sqs = SQSService(region)
        iam = IAMService(region)

        eb.disable_rule(cfg.get("eb_rule_name", ""))
        eb.delete_rule(cfg.get("eb_rule_name", ""))
        step("EventBridge Rule Disabled & Deleted")

        sm_arn = sf.get_state_machine_arn(cfg.get("state_machine_name", ""))
        if sm_arn:
            sf.delete_state_machine(sm_arn)
        step("Step Functions State Machine Deleted")

        for key in ["validate_lambda", "payment_lambda", "notify_lambda", "fail_notify_lambda"]:
            if cfg.get(key):
                lmb.delete_function(cfg[key])
        step("All Lambda Functions Deleted")

        if cfg.get("sns_topic_arn"):
            sns.delete_topic(cfg["sns_topic_arn"])
        step("SNS Topic Deleted")

        if cfg.get("orders_queue_url"):
            sqs.delete_queue(cfg["orders_queue_url"])
        if cfg.get("dlq_url"):
            sqs.delete_queue(cfg["dlq_url"])
        step("SQS Queues Deleted")

        for role_key in ["lambda_role_name", "sf_role_name", "eb_role_name"]:
            if cfg.get(role_key):
                iam.delete_role(cfg[role_key])
        step("IAM Roles Deleted")

        update_deployment("order_pipeline_active", "DESTROYED")
        step("Order Pipeline Destroyed ✓")

        return jsonify(success=True, steps=steps)

    except Exception as exc:
        step(f"Error: {exc}", "error")
        logger.exception("Destroy order error")
        return jsonify(success=False, steps=steps, error=str(exc)), 500




@app.route("/api/check-credentials")
def api_check_credentials():
    """Verify AWS credentials and check IAM permissions."""
    region = request.args.get("region", Config.AWS_REGION)
    result = {
        "credentials_valid": False,
        "account_id": None,
        "user_arn": None,
        "region": region,
        "iam_permissions": {},
        "warnings": [],
        "errors": [],
    }
    try:
        sts      = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        result["credentials_valid"] = True
        result["account_id"] = identity["Account"]
        result["user_arn"]   = identity["Arn"]

        iam_client = boto3.client("iam", region_name=region)
        actions_to_check = [
            "iam:CreateRole", "iam:AttachRolePolicy", "iam:DeleteRole",
            "s3:CreateBucket", "s3:PutObject", "s3:DeleteBucket",
            "lambda:CreateFunction", "lambda:InvokeFunction", "lambda:DeleteFunction",
            "dynamodb:CreateTable", "dynamodb:PutItem", "dynamodb:DeleteTable",
            "sns:CreateTopic", "sns:Subscribe", "sns:Publish",
            "sqs:CreateQueue", "sqs:SendMessage", "sqs:DeleteQueue",
            "states:CreateStateMachine", "states:StartExecution",
            "events:PutRule", "events:PutTargets",
        ]
        try:
            sim = iam_client.simulate_principal_policy(
                PolicySourceArn=identity["Arn"],
                ActionNames=actions_to_check,
            )
            for r in sim.get("EvaluationResults", []):
                allowed = r["EvalDecision"] == "allowed"
                result["iam_permissions"][r["EvalActionName"]] = allowed
                if not allowed:
                    result["warnings"].append(f"Permission denied: {r['EvalActionName']}")
        except Exception as e:
            result["warnings"].append(f"Could not simulate permissions (may still work): {str(e)[:120]}")

        critical = ["iam:CreateRole", "lambda:CreateFunction", "s3:CreateBucket"]
        missing  = [a for a in critical if result["iam_permissions"].get(a) is False]
        if missing:
            result["errors"].append(f"Missing critical permissions: {', '.join(missing)}")

    except Exception as exc:
        result["errors"].append(str(exc))

    return jsonify(result)

# ── Health check ──────────────────────────────────────────────────────────────

@app.route("/api/health")
def api_health():
    return jsonify(status="ok", app="Serverless Automation Factory", version="1.0.0")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
