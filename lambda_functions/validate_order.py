import json

def lambda_handler(event, context):
    order_id = event.get('order_id', '')
    customer_name = event.get('customer_name', '')
    amount = float(event.get('amount', 0))

    if not order_id or not customer_name:
        raise Exception("Invalid order: missing order_id or customer_name")
    if amount <= 0:
        raise Exception("Invalid order: amount must be greater than 0")

    return {
        **event,
        'validation_status': 'VALIDATED',
        'validation_message': 'Order validated successfully'
    }
