import boto3
import json
import logging

logger = logging.getLogger(__name__)

class SQSService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('sqs', region_name=region)

    def create_queue(self, queue_name):
        """Create a standard SQS queue for receiving SNS fan-out messages."""
        try:
            response = self.client.create_queue(
                QueueName=queue_name,
                Attributes={
                    'MessageRetentionPeriod': '86400',  # 1 day
                    'VisibilityTimeout': '30'
                }
            )
            url = response['QueueUrl']
            arn = self.client.get_queue_attributes(
                QueueUrl=url, AttributeNames=['QueueArn']
            )['Attributes']['QueueArn']
            logger.info(f"SQS queue created: {arn}")
            return url, arn
        except self.client.exceptions.QueueAlreadyExists:
            url = self.client.get_queue_url(QueueName=queue_name)['QueueUrl']
            arn = self.client.get_queue_attributes(
                QueueUrl=url, AttributeNames=['QueueArn']
            )['Attributes']['QueueArn']
            return url, arn
        except Exception as e:
            logger.error(f"Error creating SQS queue: {e}")
            raise

    def allow_sns_to_send(self, queue_url, queue_arn, topic_arn):
        """Set queue policy so SNS can publish messages to this queue."""
        try:
            policy = {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "sns.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {"ArnEquals": {"aws:SourceArn": topic_arn}}
                }]
            }
            self.client.set_queue_attributes(
                QueueUrl=queue_url,
                Attributes={'Policy': json.dumps(policy)}
            )
            logger.info(f"SNS → SQS policy set for {queue_arn}")
            return True
        except Exception as e:
            logger.error(f"Error setting queue policy: {e}")
            raise

    def create_dlq(self, queue_name):
        try:
            response = self.client.create_queue(
                QueueName=queue_name,
                Attributes={
                    'MessageRetentionPeriod': '1209600',  # 14 days
                    'VisibilityTimeout': '30'
                }
            )
            url = response['QueueUrl']
            arn_response = self.client.get_queue_attributes(
                QueueUrl=url, AttributeNames=['QueueArn']
            )
            arn = arn_response['Attributes']['QueueArn']
            logger.info(f"SQS DLQ created: {arn}")
            return url, arn
        except Exception as e:
            logger.error(f"Error creating SQS queue: {e}")
            raise

    def delete_queue(self, queue_url):
        try:
            self.client.delete_queue(QueueUrl=queue_url)
            logger.info(f"SQS queue deleted: {queue_url}")
            return True
        except Exception as e:
            logger.error(f"Error deleting SQS queue: {e}")
            return False

    def get_queue_url(self, queue_name):
        try:
            response = self.client.get_queue_url(QueueName=queue_name)
            return response['QueueUrl']
        except:
            return None

    def get_queue_arn(self, queue_url):
        try:
            response = self.client.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=['QueueArn']
            )
            return response['Attributes']['QueueArn']
        except:
            return None

    def list_queues(self):
        try:
            response = self.client.list_queues()
            return response.get('QueueUrls', [])
        except Exception as e:
            logger.error(f"Error listing queues: {e}")
            return []

    def receive_messages(self, queue_url, max_messages=10):
        try:
            response = self.client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=5
            )
            return response.get('Messages', [])
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
            return []
