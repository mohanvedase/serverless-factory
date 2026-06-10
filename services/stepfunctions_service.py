import boto3
import json
import logging

logger = logging.getLogger(__name__)

class StepFunctionsService:
    def __init__(self, region='us-east-1'):
        self.client = boto3.client('stepfunctions', region_name=region)
        self.region = region

    def build_order_state_machine(self, validate_arn, payment_arn, notification_arn, failure_notification_arn, dlq_url):
        definition = {
            "Comment": "Order Processing Workflow",
            "StartAt": "ValidateOrder",
            "States": {
                "ValidateOrder": {
                    "Type": "Task",
                    "Resource": validate_arn,
                    "Next": "ProcessPayment",
                    "Catch": [{
                        "ErrorEquals": ["States.ALL"],
                        "Next": "NotifyOrderFailed",
                        "ResultPath": "$.error"
                    }]
                },
                "ProcessPayment": {
                    "Type": "Task",
                    "Resource": payment_arn,
                    "Next": "SendNotification",
                    "Retry": [{
                        "ErrorEquals": ["States.ALL"],
                        "IntervalSeconds": 2,
                        "MaxAttempts": 3,
                        "BackoffRate": 2.0
                    }],
                    "Catch": [{
                        "ErrorEquals": ["States.ALL"],
                        "Next": "NotifyPaymentFailed",
                        "ResultPath": "$.error"
                    }]
                },
                "SendNotification": {
                    "Type": "Task",
                    "Resource": notification_arn,
                    "Next": "OrderCompleted",
                    "Catch": [{
                        "ErrorEquals": ["States.ALL"],
                        "Next": "OrderCompleted"
                    }]
                },
                "NotifyOrderFailed": {
                    "Type": "Task",
                    "Resource": failure_notification_arn,
                    "Parameters": {
                        "order_id.$": "$.order_id",
                        "customer_name.$": "$.customer_name",
                        "amount.$": "$.amount",
                        "error.$": "$.error",
                        "failure_stage": "Order Validation"
                    },
                    "ResultPath": "$.notifyResult",
                    "Next": "OrderFailed",
                    "Catch": [{
                        "ErrorEquals": ["States.ALL"],
                        "ResultPath": "$.notifyError",
                        "Next": "OrderFailed"
                    }]
                },
                "NotifyPaymentFailed": {
                    "Type": "Task",
                    "Resource": failure_notification_arn,
                    "Parameters": {
                        "order_id.$": "$.order_id",
                        "customer_name.$": "$.customer_name",
                        "amount.$": "$.amount",
                        "error.$": "$.error",
                        "failure_stage": "Payment Processing"
                    },
                    "ResultPath": "$.notifyResult",
                    "Next": "SendToDLQ",
                    "Catch": [{
                        "ErrorEquals": ["States.ALL"],
                        "ResultPath": "$.notifyError",
                        "Next": "PaymentFailed"
                    }]
                },
                "SendToDLQ": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::sqs:sendMessage",
                    "Parameters": {
                        "QueueUrl": dlq_url or "",
                        "MessageBody.$": "States.JsonToString($.error)"
                    },
                    "Next": "PaymentFailed",
                    "Catch": [{
                        "ErrorEquals": ["States.ALL"],
                        "Next": "PaymentFailed"
                    }]
                },
                "OrderCompleted": {
                    "Type": "Succeed"
                },
                "PaymentFailed": {
                    "Type": "Fail",
                    "Error": "PaymentFailed",
                    "Cause": "Payment processing failed after retries"
                },
                "OrderFailed": {
                    "Type": "Fail",
                    "Error": "OrderFailed",
                    "Cause": "Order processing failed"
                }
            }
        }
        return json.dumps(definition)

    def create_state_machine(self, name, definition, role_arn):
        try:
            response = self.client.create_state_machine(
                name=name,
                definition=definition,
                roleArn=role_arn,
                type='STANDARD',
                loggingConfiguration={
                    'level': 'OFF'
                }
            )
            logger.info(f"State machine created: {response['stateMachineArn']}")
            return response['stateMachineArn']
        except self.client.exceptions.StateMachineAlreadyExists:
            machines = self.client.list_state_machines()
            for sm in machines.get('stateMachines', []):
                if sm['name'] == name:
                    return sm['stateMachineArn']
        except Exception as e:
            logger.error(f"Error creating state machine: {e}")
            raise

    def start_execution(self, state_machine_arn, execution_name, input_data):
        try:
            response = self.client.start_execution(
                stateMachineArn=state_machine_arn,
                name=execution_name,
                input=json.dumps(input_data)
            )
            return response['executionArn']
        except Exception as e:
            logger.error(f"Error starting execution: {e}")
            raise

    def describe_execution(self, execution_arn):
        try:
            return self.client.describe_execution(executionArn=execution_arn)
        except Exception as e:
            logger.error(f"Error describing execution: {e}")
            return None

    def get_execution_history(self, execution_arn):
        try:
            response = self.client.get_execution_history(
                executionArn=execution_arn,
                includeExecutionData=True
            )
            return response.get('events', [])
        except Exception as e:
            logger.error(f"Error getting execution history: {e}")
            return []

    def delete_state_machine(self, state_machine_arn):
        try:
            self.client.delete_state_machine(stateMachineArn=state_machine_arn)
            logger.info(f"State machine deleted: {state_machine_arn}")
            return True
        except Exception as e:
            logger.error(f"Error deleting state machine: {e}")
            return False

    def list_state_machines(self):
        try:
            response = self.client.list_state_machines()
            return response.get('stateMachines', [])
        except Exception as e:
            logger.error(f"Error listing state machines: {e}")
            return []

    def get_state_machine_arn(self, name):
        try:
            machines = self.client.list_state_machines()
            for sm in machines.get('stateMachines', []):
                if sm['name'] == name:
                    return sm['stateMachineArn']
            return None
        except:
            return None
