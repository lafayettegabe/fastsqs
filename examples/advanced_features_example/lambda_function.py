from fastsqs import FastSQS, SQSEvent, QueueType
from fastsqs.middleware import (
    IdempotencyMiddleware, MemoryIdempotencyStore, 
    ErrorHandlingMiddleware, RetryConfig,
    VisibilityTimeoutMonitor, ProcessingTimeMiddleware,
    ParallelizationMiddleware, ParallelizationConfig, ConcurrencyLimiter
)
import json
import asyncio
import time
from typing import Dict, Any


class OrderProcessed(SQSEvent):
    order_id: str
    customer_id: str
    amount: float
    timestamp: str

class PaymentProcessed(SQSEvent):
    payment_id: str
    order_id: str
    amount: float
    method: str


def create_database_connection():
    """Mock database connection factory"""
    return {"connection_id": f"conn_{int(time.time())}", "status": "connected"}


def cleanup_database_connection(conn):
    """Mock database connection cleanup"""
    conn["status"] = "closed"


# Create FastSQS app with enhanced features
app = FastSQS(
    title="Advanced SQS Processor",
    description="Demonstrates advanced FastSQS features",
    version="0.3.0",
    debug=True,
    queue_type=QueueType.STANDARD,
    max_concurrent_messages=5,  # Control parallelization
    enable_partial_batch_failure=True
)

# Configure idempotency with memory store
idempotency_store = MemoryIdempotencyStore()
app.add_middleware(IdempotencyMiddleware(
    store=idempotency_store,
    ttl_seconds=3600,  # 1 hour
    use_message_deduplication_id=True,
    payload_hash_fields=["order_id", "customer_id"]  # Hash specific fields for idempotency
))

# Configure error handling with retry logic
retry_config = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    exponential_backoff=True,
    jitter=True
)
app.add_middleware(ErrorHandlingMiddleware(
    retry_config=retry_config
))

# Add visibility timeout monitoring
app.add_middleware(VisibilityTimeoutMonitor(
    default_visibility_timeout=30.0,
    warning_threshold=0.8  # Warn at 80% of timeout
))

# Add enhanced processing time monitoring
app.add_middleware(ProcessingTimeMiddleware(
    slow_processing_threshold=5.0,
    store_detailed_metrics=True
))

# Configure parallelization with resource pooling
parallelization_config = ParallelizationConfig(
    max_concurrent_messages=5,
    use_thread_pool=True,
    thread_pool_size=4
)

# Note: In a real application, you might use actual database connections
# from fastsqs.middleware.parallelization import ResourcePool
# db_pool = ResourcePool(
#     create_resource=create_database_connection,
#     cleanup_resource=cleanup_database_connection,
#     max_size=5
# )

app.add_middleware(ParallelizationMiddleware(
    config=parallelization_config,
    # resource_pools={"database": db_pool}
))


@app.route(OrderProcessed)
async def handle_order_processed(msg: OrderProcessed, ctx: Dict[str, Any]):
    """Handle order processing with idempotency and error handling"""
    print(f"Processing order: {msg.order_id} for customer: {msg.customer_id}")
    print(f"Amount: ${msg.amount}")
    
    # Simulate processing time
    await asyncio.sleep(2.0)
    
    # Access context information
    message_id = ctx.get("messageId")
    queue_type = ctx.get("queueType")
    
    print(f"Message ID: {message_id}")
    print(f"Queue Type: {queue_type}")
    
    # Check if this was an idempotency hit
    if ctx.get("idempotency_hit"):
        print(f"Idempotency hit - returning cached result")
        return ctx.get("idempotency_result")
    
    # Simulate some business logic
    result = {
        "status": "processed",
        "order_id": msg.order_id,
        "processed_at": time.time(),
        "amount": msg.amount
    }
    
    # Store result for idempotency
    ctx["handler_result"] = result
    
    return result


@app.route(PaymentProcessed)
async def handle_payment_processed(msg: PaymentProcessed, ctx: Dict[str, Any]):
    """Handle payment processing"""
    print(f"Processing payment: {msg.payment_id} for order: {msg.order_id}")
    print(f"Amount: ${msg.amount}, Method: {msg.method}")
    
    # Simulate processing
    await asyncio.sleep(1.5)
    
    # Simulate occasional errors for testing retry logic
    if msg.payment_id.endswith("error"):
        raise ValueError(f"Simulated error for payment {msg.payment_id}")
    
    result = {
        "status": "completed",
        "payment_id": msg.payment_id,
        "order_id": msg.order_id,
        "processed_at": time.time()
    }
    
    ctx["handler_result"] = result
    return result


@app.default()
def handle_unknown_message(payload: dict, ctx: Dict[str, Any]):
    """Handle unknown message types"""
    print(f"Unknown message type received: {payload}")
    return {"status": "unknown", "payload": payload}


def lambda_handler(event, context):
    """AWS Lambda handler"""
    return app.handler(event, context)


def test_advanced_features():
    """Test all the advanced features"""
    print("=== Testing Advanced FastSQS v0.3.0 Features ===\n")
    
    # Test case 1: Normal processing
    print("--- Test 1: Normal Processing ---")
    event1 = {
        "Records": [
            {
                "messageId": "msg-001",
                "body": json.dumps({
                    "type": "order_processed",
                    "order_id": "ORD-001",
                    "customer_id": "CUST-001",
                    "amount": 99.99,
                    "timestamp": "2024-01-01T10:00:00Z"
                }),
                "attributes": {}
            }
        ]
    }
    
    result1 = lambda_handler(event1, None)
    print(f"Result: {result1}\n")
    
    # Test case 2: Idempotency (same message again)
    print("--- Test 2: Idempotency Test ---")
    result2 = lambda_handler(event1, None)  # Same event
    print(f"Result: {result2}\n")
    
    # Test case 3: Error handling and retry
    print("--- Test 3: Error Handling ---")
    event3 = {
        "Records": [
            {
                "messageId": "msg-error",
                "body": json.dumps({
                    "type": "payment_processed",
                    "payment_id": "PAY-error",  # This will trigger an error
                    "order_id": "ORD-002",
                    "amount": 50.00,
                    "method": "credit_card"
                }),
                "attributes": {}
            }
        ]
    }
    
    result3 = lambda_handler(event3, None)
    print(f"Result: {result3}\n")
    
    # Test case 4: Parallel processing
    print("--- Test 4: Parallel Processing ---")
    event4 = {
        "Records": [
            {
                "messageId": f"msg-{i:03d}",
                "body": json.dumps({
                    "type": "order_processed",
                    "order_id": f"ORD-{i:03d}",
                    "customer_id": f"CUST-{i:03d}",
                    "amount": 10.00 + i,
                    "timestamp": "2024-01-01T10:00:00Z"
                }),
                "attributes": {}
            }
            for i in range(1, 6)  # 5 messages for parallel processing
        ]
    }
    
    start_time = time.time()
    result4 = lambda_handler(event4, None)
    end_time = time.time()
    
    print(f"Processed {len(event4['Records'])} messages in {end_time - start_time:.2f} seconds")
    print(f"Result: {result4}\n")
    
    # Test case 5: Mixed message types
    print("--- Test 5: Mixed Message Types ---")
    event5 = {
        "Records": [
            {
                "messageId": "msg-order-001",
                "body": json.dumps({
                    "type": "order_processed",
                    "order_id": "ORD-MIX-001",
                    "customer_id": "CUST-MIX-001",
                    "amount": 75.50,
                    "timestamp": "2024-01-01T10:00:00Z"
                }),
                "attributes": {}
            },
            {
                "messageId": "msg-payment-001",
                "body": json.dumps({
                    "type": "payment_processed",
                    "payment_id": "PAY-MIX-001",
                    "order_id": "ORD-MIX-001",
                    "amount": 75.50,
                    "method": "debit_card"
                }),
                "attributes": {}
            },
            {
                "messageId": "msg-unknown-001",
                "body": json.dumps({
                    "type": "unknown_type",
                    "data": "test data"
                }),
                "attributes": {}
            }
        ]
    }
    
    result5 = lambda_handler(event5, None)
    print(f"Result: {result5}\n")


if __name__ == "__main__":
    test_advanced_features()
