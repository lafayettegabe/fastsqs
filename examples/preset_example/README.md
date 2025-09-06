# FastSQS Preset Example

This example demonstrates how to use FastSQS middleware presets for quick setup.

## Available Presets

### Production Preset
```python
app.use_preset("production", 
    dynamodb_table="my-idempotency-table",  # Optional: uses memory store if not provided
    region_name="us-east-1",                # Optional: uses default region
    max_concurrent=10,                      # Optional: default is 10
    retry_attempts=3,                       # Optional: default is 3
    visibility_timeout=30.0,                # Optional: default is 30.0
    circuit_breaker_threshold=5             # Optional: default is 5
)
```

Includes:
- LoggingMiddleware
- TimingMsMiddleware  
- IdempotencyMiddleware (DynamoDB or Memory)
- ErrorHandlingMiddleware (with retry + circuit breaker)
- VisibilityTimeoutMonitor
- ParallelizationMiddleware

### Development Preset
```python
app.use_preset("development", max_concurrent=5)  # Optional: default is 5
```

Includes:
- LoggingMiddleware
- TimingMsMiddleware
- IdempotencyMiddleware (Memory store, 5min TTL)
- ErrorHandlingMiddleware (2 retries, faster backoff)
- VisibilityTimeoutMonitor (relaxed thresholds)
- ParallelizationMiddleware (no thread pool)

### Minimal Preset
```python
app.use_preset("minimal")
```

Includes:
- LoggingMiddleware
- TimingMsMiddleware
- IdempotencyMiddleware (Memory store, 1hr TTL)

## Usage

Instead of manually configuring each middleware:
```python
# Before (verbose)
app.add_middleware(LoggingMiddleware())
app.add_middleware(TimingMsMiddleware())
app.add_middleware(IdempotencyMiddleware(...))
app.add_middleware(ErrorHandlingMiddleware(...))
# ... more middleware
```

Use a preset:
```python
# After (simple)
app.use_preset("production", dynamodb_table="my-table")
```
