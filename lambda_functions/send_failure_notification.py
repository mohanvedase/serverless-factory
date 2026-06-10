import boto3
import json
import os
from datetime import datetime

ses = boto3.client('ses', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

def lambda_handler(event, context):
    notification_email = os.environ.get('NOTIFICATION_EMAIL', '')
    sns_topic_arn      = os.environ.get('SNS_TOPIC_ARN', '')

    order_id      = event.get('order_id', 'N/A')
    customer_name = event.get('customer_name', 'N/A')
    amount        = float(event.get('amount', 0))
    failure_stage = event.get('failure_stage', 'Order Processing')
    timestamp     = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    error_info = event.get('error', {})
    if isinstance(error_info, dict):
        error_type = error_info.get('Error', 'ProcessingError')
        raw_cause  = error_info.get('Cause', 'Unknown error occurred')
        try:
            cause_json = json.loads(raw_cause)
            error_cause = cause_json.get('errorMessage', raw_cause)
        except (json.JSONDecodeError, TypeError):
            error_cause = raw_cause
    else:
        error_type  = 'ProcessingError'
        error_cause = str(error_info)

    subject = f'Order Processing Alert - {order_id}'
    body = (
        "============================================================\n"
        "           ORDER PROCESSING ALERT - ACTION REQUIRED\n"
        "============================================================\n\n"
        "Your order could not be completed. Details below:\n\n"
        "Order Details:\n"
        "--------------\n"
        f"  Order ID      : {order_id}\n"
        f"  Customer      : {customer_name}\n"
        f"  Amount        : ${amount:.2f}\n"
        f"  Status        : FAILED\n"
        f"  Failed At     : {timestamp}\n\n"
        "Failure Information:\n"
        "--------------------\n"
        f"  Stage         : {failure_stage}\n"
        f"  Error Type    : {error_type}\n"
        f"  Reason        : {error_cause}\n\n"
        "Please try placing your order again. If the issue persists,\n"
        "contact support and quote your Order ID.\n\n"
        "============================================================\n"
        "This is an automated notification from the Order Pipeline.\n"
        "============================================================\n"
    )

    # SES — direct transactional email (no subscription required)
    if notification_email:
        ses.send_email(
            Source=notification_email,
            Destination={'ToAddresses': [notification_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body':    {'Text': {'Data': body, 'Charset': 'UTF-8'}}
            }
        )

    # SNS — publish structured failure event for fan-out to SQS and any other subscribers
    if sns_topic_arn:
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=json.dumps({
                'event_type':    'ORDER_FAILED',
                'order_id':      order_id,
                'customer_name': customer_name,
                'amount':        amount,
                'failure_stage': failure_stage,
                'error_type':    error_type,
                'error_message': error_cause,
                'timestamp':     timestamp
            })
        )

    return {
        **event,
        'notification_status': 'SENT',
        'order_status': 'FAILED'
    }
