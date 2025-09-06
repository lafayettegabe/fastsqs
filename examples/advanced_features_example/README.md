# Advanced Features Example

This example demonstrates all the advanced features introduced in FastSQS v0.3.0:

## New Features Demonstrated

### 1. **Idempotency**
- Message deduplication using various strategies
- In-memory and DynamoDB storage backends
- Automatic handling of duplicate messages
- Configurable TTL for idempotency records

### 2. **Enhanced Error Handling & Retry Logic**
- Configurable retry strategies with exponential backoff
- Circuit breaker pattern for preventing cascading failures
- Dead letter queue integration
- Error classification (permanent vs. temporary)

### 3. **Visibility Timeout Monitoring**
- Real-time monitoring of message processing time
- Warnings when approaching visibility timeout
- Processing time metrics and statistics
- Queue-level performance metrics

### 4. **Advanced Parallelization**
- Configurable concurrency limits
- Resource pooling for shared resources (DB connections, etc.)
- Thread pool support for CPU-intensive tasks
- Load balancing across multiple handlers
- Batch processing capabilities

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run the example
python lambda_function.py
```

## What It Demonstrates

### Idempotency
- Messages with the same `order_id` and `customer_id` are deduplicated
- Cached results are returned for duplicate messages
- Memory-based storage (can be switched to DynamoDB)

### Error Handling
- Automatic retries with exponential backoff
- Different handling for permanent vs. temporary errors
- Circuit breaker prevents cascading failures

### Visibility Timeout Monitoring
- Tracks processing time for each message
- Warns when approaching SQS visibility timeout
- Provides detailed performance metrics

### Parallelization
- Configurable concurrency limits (max 5 concurrent messages)
- Thread pool for blocking operations
- Resource pools for database connections
- Proper async/await handling

## Configuration Options

### FastSQS App Configuration
```python
app = FastSQS(
    max_concurrent_messages=5,      # Control parallelization
    enable_partial_batch_failure=True,  # Only retry failed messages
    queue_type=QueueType.STANDARD   # or QueueType.FIFO
)
```

### Idempotency Configuration
```python
IdempotencyMiddleware(
    store=MemoryIdempotencyStore(),  # or DynamoDBIdempotencyStore()
    ttl_seconds=3600,               # 1 hour cache
    payload_hash_fields=["order_id", "customer_id"]
)
```

### Retry Configuration
```python
RetryConfig(
    max_retries=3,
    base_delay=1.0,
    exponential_backoff=True,
    jitter=True
)
```

### Parallelization Configuration
```python
ParallelizationConfig(
    max_concurrent_messages=5,
    use_thread_pool=True,
    thread_pool_size=4,
    batch_processing=False
)
```

## Expected Output

The example will demonstrate:
1. Normal message processing with timing metrics
2. Idempotency in action (duplicate detection)
3. Error handling and retry logic
4. Parallel processing of multiple messages
5. Mixed message types with different handlers

## Production Considerations

### Idempotency
- Use DynamoDB for persistent idempotency in production
- Configure appropriate TTL based on business requirements
- Consider message content for idempotency key generation

### Error Handling
- Configure dead letter queues at the SQS level
- Implement proper logging and monitoring
- Set appropriate retry limits and delays

### Visibility Timeout
- Set SQS visibility timeout longer than max processing time
- Monitor processing time metrics
- Use queue-level metrics for optimization

### Parallelization
- Tune concurrency based on downstream service limits
- Use resource pools for expensive resources
- Monitor memory and CPU usage

## Integration with AWS Services

### DynamoDB Idempotency
```python
from fastsqs.middleware import DynamoDBIdempotencyStore

store = DynamoDBIdempotencyStore(
    table_name="fastsqs-idempotency",
    region_name="us-east-1"
)
```

### CloudWatch Metrics
```python
def cloudwatch_metrics_callback(metrics):
    # Send metrics to CloudWatch
    cloudwatch.put_metric_data(
        Namespace='FastSQS',
        MetricData=[
            {
                'MetricName': 'ProcessingTime',
                'Value': metrics['avg_processing_time'],
                'Unit': 'Seconds'
            }
        ]
    )
```

This example provides a comprehensive foundation for building production-ready SQS message processors with FastSQS v0.3.0.
