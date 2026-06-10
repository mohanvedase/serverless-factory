import boto3
import json
import os
from datetime import datetime

ses = boto3.client('ses', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

def lambda_handler(event, context):
    notification_email = os.environ.get('NOTIFICATION_EMAIL', '')
    sns_topic_arn      = os.environ.get('SNS_TOPIC_ARN', '')

    order_id       = event.get('order_id', 'N/A')
    customer_name  = event.get('customer_name', 'N/A')
    amount         = float(event.get('amount', 0))
    transaction_id = event.get('transaction_id', 'N/A')
    timestamp      = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    subject = f'Order Confirmed: {order_id}'
    body = (
        "============================================================\n"
        "           ORDER CONFIRMATION - SUCCESS\n"
        "============================================================\n\n"
        "Order Details:\n"
        "--------------\n"
        f"  Order ID      : {order_id}\n"
        f"  Customer      : {customer_name}\n"
        f"  Amount        : ${amount:.2f}\n"
        f"  Transaction ID: {transaction_id}\n"
        f"  Status        : COMPLETED\n"
        f"  Processed At  : {timestamp}\n\n"
        "Your payment has been processed successfully and your\n"
        "order is confirmed. Thank you for your order!\n\n"
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

    # SNS — publish structured event for fan-out to SQS and any other subscribers
    if sns_topic_arn:
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=subject,
            Message=json.dumps({
                'event_type':     'ORDER_COMPLETED',
                'order_id':       order_id,
                'customer_name':  customer_name,
                'amount':         amount,
                'transaction_id': transaction_id,
                'timestamp':      timestamp
            })
        )

    return {
        **event,
        'notification_status': 'SENT',
        'order_status': 'COMPLETED'
    }
