# Comprehensive FastSQS Example

This example demonstrates all the advanced features of FastSQS v0.3.0:

## Features Demonstrated

### 1. Idempotency
- Prevents duplicate message processing
- Uses memory-based storage (can be switched to DynamoDB)
- Configurable TTL for idempotency records

### 2. Error Handling & DLQ Management
- Automatic retry with exponential backoff
- Circuit breaker pattern for failing handlers
- Dead Letter Queue management with configurable timeouts
- Error classification and handling

### 3. Visibility Timeout Management
- Automatic monitoring of processing time vs visibility timeout
- Configurable warning thresholds
- Automatic timeout extension for long-running processes
- Metrics collection for timeout events

### 4. Parallelization
- Concurrent message processing with semaphore-based limiting
- Thread pool for CPU-intensive tasks
- Batch processing support with configurable batch sizes
- Resource pooling and management

## Middleware Stack

The example configures a comprehensive middleware stack:

1. **LoggingMiddleware** - Request/response logging
2. **TimingMiddleware** - Performance timing
3. **IdempotencyMiddleware** - Duplicate prevention
4. **ErrorHandlingMiddleware** - Retry logic
5. **DeadLetterQueueMiddleware** - DLQ management
6. **VisibilityTimeoutMonitor** - Timeout monitoring
7. **ProcessingTimeMiddleware** - Processing metrics
8. **ParallelizationMiddleware** - Concurrency control

## Usage

### Dependencies
```bash
pip install fastsqs[dynamodb]  # For DynamoDB idempotency store
```

### Environment Variables
```bash
# Optional: For DynamoDB idempotency store
AWS_REGION=us-east-1
IDEMPOTENCY_TABLE_NAME=fastsqs-idempotency

# Optional: For DLQ management
DLQ_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/my-dlq
```

### Local Testing
```bash
python lambda_function.py
```

### AWS Lambda Deployment
1. Package the code with dependencies
2. Set appropriate IAM permissions for SQS and DynamoDB
3. Configure SQS trigger with the desired queue

## Configuration Options

### Idempotency Configuration
```python
# Memory-based (for testing/small workloads)
store = MemoryIdempotencyStore(ttl_seconds=3600)

# DynamoDB-based (for production)
store = DynamoDBIdempotencyStore(
    table_name="idempotency",
    ttl_seconds=3600,
    region_name="us-east-1"
)
```

### Retry Configuration
```python
retry_config = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=60.0,
    backoff_multiplier=2.0,
    retry_exceptions=[ValueError, ConnectionError]
)
```

### Parallelization Configuration
```python
config = ParallelizationConfig(
    max_concurrent_messages=10,
    use_thread_pool=True,
    thread_pool_size=5,
    batch_processing=True,
    batch_size=10,
    batch_timeout=5.0
)
```

## Queue Routing

The example demonstrates routing to different queues:

- **order-processing**: Standard order processing with full middleware stack
- **high-volume-queue**: High-throughput processing with parallelization
- **critical-queue**: Critical messages with strict timeout monitoring

## Monitoring & Metrics

All middleware components provide statistics that can be logged or sent to monitoring systems:

```python
stats = {
    "idempotency_stats": middleware.get_stats(),
    "retry_stats": error_middleware.get_stats(),
    "visibility_stats": visibility_monitor.get_stats(),
    "parallelization_stats": parallel_middleware.get_stats()
}
```

## Production Considerations

1. **Idempotency Store**: Use DynamoDB for production workloads
2. **Monitoring**: Integrate with CloudWatch or your monitoring system
3. **Error Handling**: Configure appropriate DLQ and alerting
4. **Concurrency**: Tune parallelization based on your workload
5. **Timeouts**: Configure visibility timeouts based on processing requirements
