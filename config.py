"""
Serverless Automation Factory — Central Configuration
Reads from environment variables (or .env via python-dotenv).
"""

import os
from dotenv import load_dotenv

# Load .env if present (never required in production)
load_dotenv()


class Config:
    # ── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "serverless-factory-dev-secret-2024")
    DEBUG: bool = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    PORT: int = int(os.environ.get("PORT", 5000))
    HOST: str = os.environ.get("HOST", "0.0.0.0")

    # ── Database ─────────────────────────────────────────────────────────────
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    DB_PATH: str = os.path.join(BASE_DIR, "database", "app.db")

    # ── Lambda source directory ───────────────────────────────────────────────
    LAMBDA_DIR: str = os.path.join(BASE_DIR, "lambda_functions")

    # ── AWS defaults (override per-request from UI) ──────────────────────────
    AWS_REGION: str = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

    # ── Supported regions shown in dropdowns ─────────────────────────────────
    REGIONS: list = [
        ("us-east-1",      "US East (N. Virginia)"),
        ("us-east-2",      "US East (Ohio)"),
        ("us-west-1",      "US West (N. California)"),
        ("us-west-2",      "US West (Oregon)"),
        ("ap-south-1",     "Asia Pacific (Mumbai)"),
        ("ap-southeast-1", "Asia Pacific (Singapore)"),
        ("ap-southeast-2", "Asia Pacific (Sydney)"),
        ("ap-northeast-1", "Asia Pacific (Tokyo)"),
        ("eu-west-1",      "Europe (Ireland)"),
        ("eu-central-1",   "Europe (Frankfurt)"),
        ("eu-west-2",      "Europe (London)"),
        ("ca-central-1",   "Canada (Central)"),
    ]

    # ── IAM Role name defaults (overridable in deploy forms) ─────────────────
    DEFAULT_RESUME_ROLE_NAME:    str = os.environ.get("DEFAULT_RESUME_ROLE_NAME",    "ServerlessFactory-ResumeRole")
    DEFAULT_ORDER_LAMBDA_ROLE:   str = os.environ.get("DEFAULT_ORDER_LAMBDA_ROLE_NAME", "ServerlessFactory-OrderLambdaRole")
    DEFAULT_ORDER_SF_ROLE:       str = os.environ.get("DEFAULT_ORDER_SF_ROLE_NAME",  "ServerlessFactory-OrderSFRole")
    DEFAULT_ORDER_EB_ROLE:       str = os.environ.get("DEFAULT_ORDER_EB_ROLE_NAME",  "ServerlessFactory-OrderEBRole")
