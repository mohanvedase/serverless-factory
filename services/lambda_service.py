import boto3
import zipfile
import io
import os
import logging

logger = logging.getLogger(__name__)

class LambdaService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('lambda', region_name=region)
        self.region = region

    def _zip_lambda(self, source_file):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(source_file, os.path.basename(source_file))
        zip_buffer.seek(0)
        return zip_buffer.read()

    def create_function(self, function_name, handler, role_arn, source_file, env_vars=None, runtime='python3.12'):
        try:
            zip_bytes = self._zip_lambda(source_file)
            kwargs = dict(
                FunctionName=function_name,
                Runtime=runtime,
                Role=role_arn,
                Handler=handler,
                Code={'ZipFile': zip_bytes},
                Timeout=60,
                MemorySize=256
            )
            if env_vars:
                kwargs['Environment'] = {'Variables': env_vars}
            response = self.client.create_function(**kwargs)
            waiter = self.client.get_waiter('function_active')
            waiter.wait(FunctionName=function_name)
            logger.info(f"Lambda function created: {function_name}")
            return response['FunctionArn']
        except self.client.exceptions.ResourceConflictException:
            response = self.client.get_function(FunctionName=function_name)
            return response['Configuration']['FunctionArn']
        except Exception as e:
            logger.error(f"Error creating Lambda: {e}")
            raise

    def delete_function(self, function_name):
        try:
            self.client.delete_function(FunctionName=function_name)
            logger.info(f"Lambda function deleted: {function_name}")
            return True
        except self.client.exceptions.ResourceNotFoundException:
            return True
        except Exception as e:
            logger.error(f"Error deleting Lambda: {e}")
            return False

    def list_functions(self):
        try:
            functions = []
            paginator = self.client.get_paginator('list_functions')
            for page in paginator.paginate():
                functions.extend(page['Functions'])
            return functions
        except Exception as e:
            logger.error(f"Error listing functions: {e}")
            return []

    def get_function_arn(self, function_name):
        try:
            response = self.client.get_function(FunctionName=function_name)
            return response['Configuration']['FunctionArn']
        except:
            return None

    def invoke_function(self, function_name, payload):
        import json
        try:
            response = self.client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            result = json.loads(response['Payload'].read())
            return result
        except Exception as e:
            logger.error(f"Error invoking Lambda: {e}")
            raise
