# FastSQS

**FastAPI-like, production-ready async SQS message processing for Python.**

[![PyPI version](https://img.shields.io/pypi/v/fastsqs.svg)](https://pypi.org/project/fastsqs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Version 0.3.0 - Production Ready Features

> ⚠️ **Pre-1.0 Release Warning**: This library is under active development. Breaking changes may occur until version 1.0.0. Pin your version in production.

### 🚀 New Enterprise Features

- **Idempotency**: Prevent duplicate message processing with memory or DynamoDB storage
- **Advanced Error Handling**: Exponential backoff, circuit breaker, and DLQ management  
- **Visibility Timeout Management**: Automatic monitoring and extension for long-running processes
- **Parallelization**: Concurrent processing with semaphore-based limiting and thread pools

## Recent Updates

### Version 0.3.2
- **Auto DynamoDB Table Creation**: DynamoDB idempotency store now automatically creates tables with proper schema and TTL configuration
- **Enhanced Table Management**: Improved error handling and race condition protection for table operations

### Version 0.3.1
- **Idempotency Improvements**: Enhanced DynamoDB store reliability and error handling
- **Bug Fixes**: Various stability improvements and edge case handling

## Key Features

- 🚀 **FastAPI-like API:** Familiar decorator-based routing with automatic type inference
- 🔒 **Pydantic Validation:** Automatic message validation and serialization using SQSEvent models
- 🔄 **Auto Async/Sync:** Write handlers as sync or async functions - framework handles both automatically
- �️ **Middleware Support:** Built-in and custom middleware for logging, timing, and more
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
pip install fastsqs
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

```python
# FIFO Queue Support
app = FastSQS(queue_type=QueueType.FIFO)

# Middleware
from fastsqs.middleware import TimingMiddleware, LoggingMiddleware
app.add_middleware(TimingMiddleware())
app.add_middleware(LoggingMiddleware())

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