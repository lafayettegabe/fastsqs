from fastsqs import QueueApp, QueueRouter
import asyncio


order_router = QueueRouter(key="type")


@order_router.route("order_created")
async def handle_order_created(payload, record, context, ctx):
    print("Processing order in Standard queue (parallel processing)")
    print(f"Order created: {payload.get('orderId')}")
    print(f"Message ID: {record.get('messageId')}")


@order_router.route("order_updated")
async def handle_order_updated(payload, record, context, ctx):
    print("Processing order update in Standard queue (parallel processing)")
    print(f"Order updated: {payload.get('orderId')}")
    print(f"Message ID: {record.get('messageId')}")


print("=== Standard Queue Example ===")
standard_app = QueueApp(
    title="Standard Queue App",
    description="Example showing Standard SQS queue processing",
    version="1.0.0",
    debug=True,
)
standard_app.include_router(order_router)

def lambda_handler(event, context):
    return standard_app.handler(event, context)


# -----------------------------------------------------------------------
# -------------------------------- TESTS --------------------------------

if __name__ == "__main__":
    event = {
        "Records": [
            {
                "messageId": "msg-001",
                "body": '{"type": "order_created", "orderId": "order-123"}',
                "attributes": {},
            },
            {
                "messageId": "msg-002",
                "body": '{"type": "order_updated", "orderId": "order-123"}',
                "attributes": {},
            },
            {
                "messageId": "msg-003",
                "body": '{"type": "order_created", "orderId": "order-456"}',
                "attributes": {},
            },
        ]
    }

    result = lambda_handler(event, None)
    print(f"Processing complete. Result: {result}")