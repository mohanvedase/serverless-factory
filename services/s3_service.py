import boto3
import logging

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('s3', region_name=region)
        self.region = region

    def create_bucket(self, bucket_name):
        try:
            if self.region == 'us-east-1':
                self.client.create_bucket(Bucket=bucket_name)
            else:
                self.client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )
            self.client.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            logger.info(f"S3 bucket created: {bucket_name}")
            return f"arn:aws:s3:::{bucket_name}"
        except self.client.exceptions.BucketAlreadyOwnedByYou:
            return f"arn:aws:s3:::{bucket_name}"
        except Exception as e:
            logger.error(f"Error creating bucket: {e}")
            raise

    def configure_s3_trigger(self, bucket_name, lambda_arn):
        try:
            self.client.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={
                    'LambdaFunctionConfigurations': [{
                        'LambdaFunctionArn': lambda_arn,
                        'Events': ['s3:ObjectCreated:*']
                    }]
                }
            )
            logger.info(f"S3 trigger configured for {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Error configuring S3 trigger: {e}")
            raise

    def remove_s3_trigger(self, bucket_name):
        try:
            self.client.put_bucket_notification_configuration(
                Bucket=bucket_name,
                NotificationConfiguration={}
            )
            return True
        except Exception as e:
            logger.error(f"Error removing S3 trigger: {e}")
            return False

    def add_lambda_permission_for_s3(self, lambda_client, function_name, bucket_name, account_id):
        try:
            statement_id = f"S3Invoke-{bucket_name.replace('-', '')[:20]}"
            lambda_client.add_permission(
                FunctionName=function_name,
                StatementId=statement_id,
                Action='lambda:InvokeFunction',
                Principal='s3.amazonaws.com',
                SourceArn=f'arn:aws:s3:::{bucket_name}',
                SourceAccount=account_id
            )
            return True
        except lambda_client.exceptions.ResourceConflictException:
            return True
        except Exception as e:
            logger.error(f"Error adding lambda permission: {e}")
            return False

    def upload_file(self, bucket_name, key, file_obj):
        try:
            self.client.upload_fileobj(file_obj, bucket_name, key)
            return True
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise

    def empty_bucket(self, bucket_name):
        try:
            s3 = boto3.resource('s3', region_name=self.region)
            bucket = s3.Bucket(bucket_name)
            bucket.object_versions.delete()
            bucket.objects.all().delete()
            return True
        except Exception as e:
            logger.error(f"Error emptying bucket: {e}")
            return False

    def delete_bucket(self, bucket_name):
        try:
            self.empty_bucket(bucket_name)
            self.client.delete_bucket(Bucket=bucket_name)
            logger.info(f"S3 bucket deleted: {bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting bucket: {e}")
            return False

    def list_buckets(self):
        try:
            response = self.client.list_buckets()
            return response.get('Buckets', [])
        except Exception as e:
            logger.error(f"Error listing buckets: {e}")
            return []
