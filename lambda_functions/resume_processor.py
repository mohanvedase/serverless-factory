import json
import boto3
import os
import urllib.parse
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

def lambda_handler(event, context):
    table_name = os.environ.get('DYNAMODB_TABLE', 'ResumeProcessing')
    sns_topic_arn = os.environ.get('SNS_TOPIC_ARN', '')

    table = dynamodb.Table(table_name)

    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        size = record['s3']['object'].get('size', 0)

        timestamp = datetime.utcnow().isoformat()
        resume_id = key.replace('/', '_').replace('.', '_') + '_' + str(int(datetime.utcnow().timestamp()))

        item = {
            'resume_id': resume_id,
            'file_name': key,
            'bucket': bucket,
            'file_size': size,
            'upload_time': timestamp,
            'processing_status': 'PROCESSED',
            'notification_status': 'PENDING'
        }

        table.put_item(Item=item)
        print(f"Stored resume record: {resume_id}")

        if sns_topic_arn:
            message = f"""New Resume Received!

File: {key}
Bucket: {bucket}
Size: {size} bytes
Processed At: {timestamp}
Record ID: {resume_id}

Resume has been processed and stored in DynamoDB."""

            sns.publish(
                TopicArn=sns_topic_arn,
                Subject=f'New Resume Processed: {key}',
                Message=message
            )

            table.update_item(
                Key={'resume_id': resume_id},
                UpdateExpression='SET notification_status = :s',
                ExpressionAttributeValues={':s': 'SENT'}
            )
            print(f"SNS notification sent for {key}")

    return {
        'statusCode': 200,
        'body': json.dumps('Resume processing complete')
    }
