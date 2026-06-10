import boto3
import json
import logging

logger = logging.getLogger(__name__)

class EventBridgeService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('events', region_name=region)

    def create_rule(self, rule_name, state_machine_arn, role_arn):
        try:
            response = self.client.put_rule(
                Name=rule_name,
                EventPattern=json.dumps({
                    "source": ["serverless.factory"],
                    "detail-type": ["OrderEvent"]
                }),
                State='ENABLED',
                Description='Order processing event rule by Serverless Factory'
            )
            rule_arn = response['RuleArn']

            self.client.put_targets(
                Rule=rule_name,
                Targets=[{
                    'Id': 'StepFunctionsTarget',
                    'Arn': state_machine_arn,
                    'RoleArn': role_arn,
                    'InputTransformer': {
                        'InputPathsMap': {'detail': '$.detail'},
                        'InputTemplate': '<detail>'
                    }
                }]
            )
            logger.info(f"EventBridge rule created: {rule_arn}")
            return rule_arn
        except Exception as e:
            logger.error(f"Error creating EventBridge rule: {e}")
            raise

    def disable_rule(self, rule_name):
        try:
            self.client.disable_rule(Name=rule_name)
            return True
        except Exception as e:
            logger.error(f"Error disabling rule: {e}")
            return False

    def delete_rule(self, rule_name):
        try:
            self.disable_rule(rule_name)
            targets = self.client.list_targets_by_rule(Rule=rule_name)
            target_ids = [t['Id'] for t in targets.get('Targets', [])]
            if target_ids:
                self.client.remove_targets(Rule=rule_name, Ids=target_ids)
            self.client.delete_rule(Name=rule_name)
            logger.info(f"EventBridge rule deleted: {rule_name}")
            return True
        except self.client.exceptions.ResourceNotFoundException:
            return True
        except Exception as e:
            logger.error(f"Error deleting rule: {e}")
            return False

    def list_rules(self):
        try:
            response = self.client.list_rules()
            return response.get('Rules', [])
        except Exception as e:
            logger.error(f"Error listing rules: {e}")
            return []

    def get_rule_arn(self, rule_name):
        try:
            response = self.client.describe_rule(Name=rule_name)
            return response.get('Arn')
        except:
            return None
