import json
import random

def lambda_handler(event, context):
    simulate_failure = event.get('simulate_failure', False)

    if simulate_failure:
        raise Exception("PAYMENT_FAILED: Payment gateway declined the transaction")

    order_id = event.get('order_id', '')
    amount = float(event.get('amount', 0))
    transaction_id = f"TXN-{order_id}-{random.randint(100000, 999999)}"

    return {
        **event,
        'payment_status': 'SUCCESS',
        'transaction_id': transaction_id,
        'payment_message': f'Payment of ${amount} processed successfully'
    }
