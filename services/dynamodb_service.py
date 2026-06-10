import boto3
import logging

logger = logging.getLogger(__name__)

class DynamoDBService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('dynamodb', region_name=region)
        self.resource = boto3.resource('dynamodb', region_name=region)

    def create_table(self, table_name, partition_key='resume_id'):
        try:
            response = self.client.create_table(
                TableName=table_name,
                AttributeDefinitions=[{'AttributeName': partition_key, 'AttributeType': 'S'}],
                KeySchema=[{'AttributeName': partition_key, 'KeyType': 'HASH'}],
                BillingMode='PAY_PER_REQUEST'
            )
            waiter = self.client.get_waiter('table_exists')
            waiter.wait(TableName=table_name)
            logger.info(f"DynamoDB table created: {table_name}")
            return response['TableDescription']['TableArn']
        except self.client.exceptions.ResourceInUseException:
            table = self.client.describe_table(TableName=table_name)
            return table['Table']['TableArn']
        except Exception as e:
            logger.error(f"Error creating DynamoDB table: {e}")
            raise

    def delete_table(self, table_name):
        try:
            self.client.delete_table(TableName=table_name)
            waiter = self.client.get_waiter('table_not_exists')
            waiter.wait(TableName=table_name)
            logger.info(f"DynamoDB table deleted: {table_name}")
            return True
        except self.client.exceptions.ResourceNotFoundException:
            return True
        except Exception as e:
            logger.error(f"Error deleting table: {e}")
            return False

    def scan_table(self, table_name, limit=50):
        try:
            table = self.resource.Table(table_name)
            response = table.scan(Limit=limit)
            return response.get('Items', [])
        except Exception as e:
            logger.error(f"Error scanning table: {e}")
            return []

    def list_tables(self):
        try:
            tables = []
            paginator = self.client.get_paginator('list_tables')
            for page in paginator.paginate():
                tables.extend(page['TableNames'])
            return tables
        except Exception as e:
            logger.error(f"Error listing tables: {e}")
            return []

    def get_table_arn(self, table_name):
        try:
            response = self.client.describe_table(TableName=table_name)
            return response['Table']['TableArn']
        except:
            return None
