# FastSQS

**FastAPI-like, production-ready async SQS message processing for Python.**

[![PyPI version](https://img.shields.io/pypi/v/fastsqs.svg)](https://pypi.org/project/fastsqs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Version 0.4.0 - Enhanced Enterprise Features

> ⚠️ **Pre-1.0 Release Warning**: This library is under active development. Breaking changes may occur until version 1.0.0. Pin your version in production.

### 🚀 New in Version 0.4.0

- **Middleware Presets**: Quick setup with production, development, and minimal presets
- **Enhanced Telemetry**: Advanced logging with Elasticsearch integration support
- **Load Balancing**: Intelligent message distribution across handlers
- **Queue Metrics**: Comprehensive queue performance monitoring
- **Custom Middleware Framework**: Simplified custom middleware creation with examples

### 🏗️ Enterprise Features (0.3.x)

- **Idempotency**: Prevent duplicate message processing with memory or DynamoDB storage
- **Advanced Error Handling**: Exponential backoff, circuit breaker, and DLQ management  
- **Visibility Timeout Management**: Automatic monitoring and extension for long-running processes
- **Parallelization**: Concurrent processing with semaphore-based limiting and thread pools

## Key Features

- 🚀 **FastAPI-like API:** Familiar decorator-based routing with automatic type inference
- 🔒 **Pydantic Validation:** Automatic message validation and serialization using SQSEvent models
- 🔄 **Auto Async/Sync:** Write handlers as sync or async functions - framework handles both automatically
- ⚡ **Middleware Presets:** One-line setup for production, development, or minimal configurations
- 🛡️ **Enterprise Middleware:** Idempotency, error handling, circuit breakers, and DLQ management
- 📊 **Telemetry & Metrics:** Built-in performance monitoring and Elasticsearch logging support
- 🔧 **Load Balancing:** Intelligent message distribution and resource management
- 🦾 **Partial Batch Failure:** Native support for AWS Lambda batch failure responses
- 🔀 **FIFO & Standard Queues:** Full support for both SQS queue types with proper ordering
- 🎯 **Flexible Matching:** Automatic field name normalization (camelCase ↔ snake_case)
- 🏗️ **Nested Routing:** QueueRouter support for complex routing scenarios
- 🐍 **Type Safety:** Full type hints and editor support throughout

---

## Requirements

- Python 3.8+
- [Pydantic](https://docs.pydantic.dev/) (installed automatically)

---

## Installation

```bash
# Basic installation
pip install fastsqs

# With DynamoDB support (for production idempotency)
pip install fastsqs[dynamodb]

# With telemetry support (for advanced logging)
pip install fastsqs[telemetry]

# With all optional features
pip install fastsqs[all]
```

---

## Quick Start

### Basic FastAPI-like Example

```python
from fastsqs import FastSQS, SQSEvent

class UserCreated(SQSEvent):
    user_id: str
    email: str
    name: str

class OrderProcessed(SQSEvent):
    order_id: str
    amount: float

# Create FastSQS app
app = FastSQS(debug=True)

# Route messages using SQSEvent models
@app.route(UserCreated)
async def handle_user_created(msg: UserCreated):
    print(f"User created: {msg.name} ({msg.email})")

@app.route(OrderProcessed)
def handle_order_processed(msg: OrderProcessed):
    print(f"Order {msg.order_id}: ${msg.amount}")

# Default handler for unmatched messages
@app.default()
def handle_unknown(payload, ctx):
    print(f"Unknown message: {payload}")

# AWS Lambda handler
def lambda_handler(event, context):
    return app.handler(event, context)
```

### Example SQS Message Payloads

```json
{
  "type": "user_created",
  "user_id": "123",
  "email": "user@example.com",
  "name": "John Doe"
}
```

```json
{
  "type": "order_processed",
  "order_id": "ord-456",
  "amount": 99.99
}
```

---

## Advanced Features

### Middleware Presets (New in 0.4.0)

```python
# Production-ready setup in one line
app.use_preset("production", 
    dynamodb_table="my-idempotency-table",
    max_concurrent=10,
    retry_attempts=3
)

# Development setup
app.use_preset("development")

# Minimal setup
app.use_preset("minimal")
```

### Manual Middleware Configuration

```python
# FIFO Queue Support
app = FastSQS(queue_type=QueueType.FIFO)

# Individual middleware
from fastsqs.middleware import (
    TimingMsMiddleware, LoggingMiddleware, 
    IdempotencyMiddleware, ErrorHandlingMiddleware,
    ParallelizationMiddleware, QueueMetricsMiddleware
)
app.add_middleware(TimingMsMiddleware())
app.add_middleware(LoggingMiddleware())
app.add_middleware(IdempotencyMiddleware())
app.add_middleware(QueueMetricsMiddleware())

# Field Matching - automatically handles camelCase ↔ snake_case
class UserEvent(SQSEvent):
    user_id: str  # Matches: user_id, userId, USER_ID
    first_name: str  # Matches: first_name, firstName
```

---

## How it Works

1. **Message Parsing:** JSON validated and normalized
2. **Route Matching:** Type-based routing to handlers  
3. **Handler Execution:** Sync/async functions supported
4. **Error Handling:** Failed messages → SQS retry/DLQ

---

## Error Handling & Performance

- **Predictable Errors:** All failures result in batch item failures for SQS retry
- **Parallel Processing:** Concurrent message handling (respects FIFO ordering)
- **Type Safety:** Full Pydantic validation with IDE support
- **Memory Efficient:** Minimal overhead per message

---

## Documentation & Contributing

- **Examples:** See `examples/` directory for complete working examples
- **Contributing:** Issues and PRs welcome!
- **License:** MIT

---

**Ready to build type-safe, FastAPI-like SQS processors? Try FastSQS today!**