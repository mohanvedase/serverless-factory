import boto3
import logging

logger = logging.getLogger(__name__)

class SNSService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('sns', region_name=region)

    def create_topic(self, topic_name):
        try:
            response = self.client.create_topic(Name=topic_name)
            topic_arn = response['TopicArn']
            logger.info(f"SNS topic created: {topic_arn}")
            return topic_arn
        except Exception as e:
            logger.error(f"Error creating SNS topic: {e}")
            raise

    def subscribe_sqs(self, topic_arn, queue_arn):
        """Subscribe an SQS queue to an SNS topic (auto-confirmed, no email needed)."""
        try:
            # Check if already subscribed
            paginator = self.client.get_paginator('list_subscriptions_by_topic')
            for page in paginator.paginate(TopicArn=topic_arn):
                for sub in page.get('Subscriptions', []):
                    if sub.get('Protocol') == 'sqs' and sub.get('Endpoint') == queue_arn:
                        logger.info(f"SQS {queue_arn} already subscribed to topic")
                        return sub['SubscriptionArn']

            response = self.client.subscribe(
                TopicArn=topic_arn,
                Protocol='sqs',
                Endpoint=queue_arn,
                Attributes={'RawMessageDelivery': 'false'}
            )
            logger.info(f"SQS subscribed to SNS topic: {response['SubscriptionArn']}")
            return response['SubscriptionArn']
        except Exception as e:
            logger.error(f"Error subscribing SQS to SNS: {e}")
            raise

    def subscribe_email(self, topic_arn, email):
        try:
            # Check for an existing subscription to avoid duplicates
            paginator = self.client.get_paginator('list_subscriptions_by_topic')
            for page in paginator.paginate(TopicArn=topic_arn):
                for sub in page.get('Subscriptions', []):
                    if sub.get('Endpoint', '').lower() == email.lower():
                        logger.info(f"Email {email} already subscribed (status: {sub['SubscriptionArn']})")
                        return sub['SubscriptionArn']

            response = self.client.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )
            return response['SubscriptionArn']
        except Exception as e:
            logger.error(f"Error subscribing email: {e}")
            raise

    def delete_topic(self, topic_arn):
        try:
            subscriptions = self.client.list_subscriptions_by_topic(TopicArn=topic_arn)
            for sub in subscriptions.get('Subscriptions', []):
                if sub['SubscriptionArn'] != 'PendingConfirmation':
                    try:
                        self.client.unsubscribe(SubscriptionArn=sub['SubscriptionArn'])
                    except:
                        pass
            self.client.delete_topic(TopicArn=topic_arn)
            logger.info(f"SNS topic deleted: {topic_arn}")
            return True
        except Exception as e:
            logger.error(f"Error deleting SNS topic: {e}")
            return False

    def list_topics(self):
        try:
            topics = []
            paginator = self.client.get_paginator('list_topics')
            for page in paginator.paginate():
                topics.extend(page['Topics'])
            return topics
        except Exception as e:
            logger.error(f"Error listing topics: {e}")
            return []

    def publish(self, topic_arn, subject, message):
        try:
            self.client.publish(TopicArn=topic_arn, Subject=subject, Message=message)
            return True
        except Exception as e:
            logger.error(f"Error publishing to SNS: {e}")
            return False
