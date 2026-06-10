import boto3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CloudWatchService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('logs', region_name=region)

    def get_lambda_logs(self, function_name, hours=1, limit=100):
        log_group = f'/aws/lambda/{function_name}'
        return self._get_logs(log_group, hours, limit)

    def _get_logs(self, log_group, hours=1, limit=100):
        try:
            end_time = int(datetime.utcnow().timestamp() * 1000)
            start_time = int((datetime.utcnow() - timedelta(hours=hours)).timestamp() * 1000)

            streams = self.client.describe_log_streams(
                logGroupName=log_group,
                orderBy='LastEventTime',
                descending=True,
                limit=5
            )

            events = []
            for stream in streams.get('logStreams', []):
                response = self.client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream['logStreamName'],
                    startTime=start_time,
                    endTime=end_time,
                    limit=limit // len(streams.get('logStreams', [1])),
                    startFromHead=False
                )
                for event in response.get('events', []):
                    events.append({
                        'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                        'message': event['message'].strip(),
                        'stream': stream['logStreamName']
                    })

            events.sort(key=lambda x: x['timestamp'], reverse=True)
            return events[:limit]
        except self.client.exceptions.ResourceNotFoundException:
            return []
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return []

    def get_step_function_logs(self, state_machine_name, hours=1):
        log_group = f'/aws/states/{state_machine_name}'
        return self._get_logs(log_group, hours)

    def list_log_groups(self, prefix='/aws/lambda/'):
        try:
            groups = []
            paginator = self.client.get_paginator('describe_log_groups')
            for page in paginator.paginate(logGroupNamePrefix=prefix):
                groups.extend(page['logGroups'])
            return groups
        except Exception as e:
            logger.error(f"Error listing log groups: {e}")
            return []
