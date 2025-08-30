from fastsqs import QueueApp, QueueRouter, QueueType


order_router = QueueRouter(key="type")

fifo_app = QueueApp(
    title="FIFO Queue App",
    description="Example showing FIFO SQS queue processing",
    version="1.0.0",
    queue_type=QueueType.FIFO,
    debug=True,
)
fifo_app.include_router(order_router)


@order_router.route("order_created")
async def handle_order_created(payload, record, context, ctx):

    queue_type = ctx.get("queueType")
    fifo_info = ctx.get("fifoInfo", {})

    if queue_type == "fifo":
        message_group = fifo_info.get("messageGroupId")
        dedup_id = fifo_info.get("messageDeduplicationId")
        print(f"Processing order in FIFO queue, group: {message_group}")
        print(f"Deduplication ID: {dedup_id}")
    else:
        print("Processing order in Standard queue")

    print(f"Order created: {payload.get('orderId')}")
    print(f"Message ID: {record.get('messageId')}")


@order_router.route("order_updated")
async def handle_order_updated(payload, record, context, ctx):

    queue_type = ctx.get("queueType")
    fifo_info = ctx.get("fifoInfo", {})

    if queue_type == "fifo":
        message_group = fifo_info.get("messageGroupId")
        dedup_id = fifo_info.get("messageDeduplicationId")
        print(f"Processing order update in FIFO queue, group: {message_group}")
        print(f"Deduplication ID: {dedup_id}")
    else:
        print("Processing order update in Standard queue")

    print(f"Order updated: {payload.get('orderId')}")
    print(f"Message ID: {record.get('messageId')}")


def lambda_handler(event, context):
    return fifo_app.handler(event, context)


# -----------------------------------------------------------------------
# -------------------------------- TESTS --------------------------------

if __name__ == "__main__":
    event = {
        "Records": [
            {
                "messageId": "msg-fifo-001",
                "body": '{"type": "order_created", "orderId": "order-123"}',
                "attributes": {
                    "messageGroupId": "customer-001",
                    "messageDeduplicationId": "dedup-001",
                },
            },
            {
                "messageId": "msg-fifo-002",
                "body": '{"type": "order_updated", "orderId": "order-123"}',
                "attributes": {
                    "messageGroupId": "customer-001",
                    "messageDeduplicationId": "dedup-002",
                },
            },
            {
                "messageId": "msg-fifo-003",
                "body": '{"type": "order_created", "orderId": "order-456"}',
                "attributes": {
                    "messageGroupId": "customer-002",
                    "messageDeduplicationId": "dedup-003",
                },
            },
        ]
    }
    
    result = lambda_handler(event, None)
    print(f"Processing complete. Result: {result}")
