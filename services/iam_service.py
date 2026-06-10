import boto3
import json
import logging

logger = logging.getLogger(__name__)

class IAMService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('iam', region_name=region)

    def _safe_attach_policy(self, role_name, policy_arn):
        try:
            self.client.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
        except Exception:
            pass  # already attached

    def create_lambda_role(self, role_name, additional_policies=None):
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        try:
            response = self.client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Lambda execution role created by Serverless Factory'
            )
            role_arn = response['Role']['Arn']
        except self.client.exceptions.EntityAlreadyExistsException:
            role = self.client.get_role(RoleName=role_name)
            role_arn = role['Role']['Arn']

        # Always ensure all required policies are attached (idempotent)
        for policy_arn in [
            'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
            'arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess',
            'arn:aws:iam::aws:policy/AmazonSNSFullAccess',
            'arn:aws:iam::aws:policy/AmazonSESFullAccess',
            'arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess',
        ]:
            self._safe_attach_policy(role_name, policy_arn)

        if additional_policies:
            for policy_arn in additional_policies:
                self._safe_attach_policy(role_name, policy_arn)

        import time
        time.sleep(10)
        logger.info(f"IAM Role ready: {role_arn}")
        return role_arn

    def create_stepfunctions_role(self, role_name):
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "states.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        try:
            response = self.client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='Step Functions execution role created by Serverless Factory'
            )
            role_arn = response['Role']['Arn']
            self.client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AWSLambda_FullAccess'
            )
            self.client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AmazonSNSFullAccess'
            )
            self.client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/CloudWatchLogsFullAccess'
            )
            import time
            time.sleep(10)
            return role_arn
        except self.client.exceptions.EntityAlreadyExistsException:
            role = self.client.get_role(RoleName=role_name)
            return role['Role']['Arn']

    def create_eventbridge_role(self, role_name):
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        try:
            response = self.client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='EventBridge execution role created by Serverless Factory'
            )
            role_arn = response['Role']['Arn']
            self.client.attach_role_policy(
                RoleName=role_name,
                PolicyArn='arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess'
            )
            import time
            time.sleep(5)
            return role_arn
        except self.client.exceptions.EntityAlreadyExistsException:
            role = self.client.get_role(RoleName=role_name)
            return role['Role']['Arn']

    def delete_role(self, role_name):
        try:
            attached = self.client.list_attached_role_policies(RoleName=role_name)
            for policy in attached.get('AttachedPolicies', []):
                self.client.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
            inline = self.client.list_role_policies(RoleName=role_name)
            for policy_name in inline.get('PolicyNames', []):
                self.client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
            self.client.delete_role(RoleName=role_name)
            logger.info(f"IAM Role deleted: {role_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting role {role_name}: {e}")
            return False

    def get_role_arn(self, role_name):
        try:
            response = self.client.get_role(RoleName=role_name)
            return response['Role']['Arn']
        except:
            return None
