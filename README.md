# FastSQS

**FastAPI-like, production-ready async SQS message processing for Python.**

[![PyPI version](https://img.shields.io/pypi/v/fastsqs.svg)](https://pypi.org/project/fastsqs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Version 0.3.0 - Production Ready Features

### 🚀 New Enterprise Features

- **Idempotency**: Prevent duplicate message processing with memory or DynamoDB storage
- **Advanced Error Handling**: Exponential backoff, circuit breaker, and DLQ management  
- **Visibility Timeout Management**: Automatic monitoring and extension for long-running processes
- **Parallelization**: Concurrent processing with semaphore-based limiting and thread pools

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

### FIFO Queue Support

```python
from fastsqs import FastSQS, QueueType

app = FastSQS(
    queue_type=QueueType.FIFO,
    debug=True
)

# Messages in the same messageGroupId are processed sequentially
# Different groups are processed in parallel
```

### Flexible Field Matching

FastSQS automatically handles field name variations:

```python
class UserEvent(SQSEvent):
    user_id: str  # Will match: user_id, userId, USER_ID, etc.
    first_name: str  # Will match: first_name, firstName, etc.

@app.route(UserEvent)
def handle_user(msg: UserEvent):
    print(f"User: {msg.user_id}, Name: {msg.first_name}")
```

SQS messages with different field formats work automatically:
```json
{"type": "user_event", "userId": "123", "firstName": "John"}
```

### Middleware

```python
from fastsqs.middleware import TimingMiddleware, LoggingMiddleware

# Built-in middleware
app.add_middleware(TimingMiddleware())
app.add_middleware(LoggingMiddleware())

# Custom middleware
from fastsqs.middleware import Middleware

class AuthMiddleware(Middleware):
    async def before(self, payload, record, context, ctx):
        if not payload.get("auth_token"):
            raise ValueError("Missing auth token")
    
    async def after(self, payload, record, context, ctx, error):
        if error:
            print(f"Handler failed: {error}")

app.add_middleware(AuthMiddleware())
```

### Complex Routing with QueueRouter

For complex nested routing scenarios, you can still use QueueRouter:

```python
from fastsqs import FastSQS, QueueRouter

# Main FastSQS app
app = FastSQS()

# Complex router for nested routing
user_router = QueueRouter(key="action")

@user_router.route("create")
def create_user(msg, ctx):
    print(f"Creating user: {msg}")

@user_router.route("delete") 
def delete_user(msg, ctx):
    print(f"Deleting user: {msg}")

# Include the router for complex scenarios
app.include_router(user_router)
```

Example payload for nested routing:
```json
{
  "service": "users",
  "action": "create",
  "user_data": {...}
}
```

---

## Package Structure

The library is organized into clean, modular components:

```
fastsqs/
├── __init__.py          # Main exports (FastSQS, QueueRouter, etc.)
├── app.py               # Main FastSQS class  
├── events.py            # SQSEvent base class with field normalization
├── types.py             # Type definitions
├── exceptions.py        # Custom exceptions
├── utils.py             # Utility functions
├── middleware/          # Middleware components
│   ├── __init__.py
│   ├── base.py         # Base middleware class
│   ├── timing.py       # Timing middleware
│   └── logging.py      # Logging middleware
└── routing/            # QueueRouter for complex routing
    ├── __init__.py
    ├── entry.py        # Route entry
    └── router.py       # Router implementation
```

---

## How it Works

### Message Processing Flow

1. **Message Parsing:** JSON message body is parsed and validated
2. **Route Matching:** Message type is extracted and matched to registered routes
3. **Model Validation:** SQSEvent model validates and normalizes the message data
4. **Handler Execution:** Your handler function is called with the validated model
5. **Error Handling:** Any errors result in batch item failures for SQS retry

### Key Concepts

- **FastAPI-like Decorators:** Use `@app.route(SQSEventModel)` to register handlers
- **Automatic Type Inference:** Handler signature determines what parameters to pass
- **Field Normalization:** camelCase ↔ snake_case conversion happens automatically
- **Flexible Matching:** Multiple field name variants are supported out of the box
- **Standard Error Handling:** All errors result in message failure and SQS retry/DLQ

---

## Error Handling

FastSQS uses a simple, predictable error handling strategy:

| Error Type | Behavior | SQS Result |
|------------|----------|------------|
| **Invalid JSON** | `InvalidMessage` exception | Message fails → retry/DLQ |
| **Validation Error** | `InvalidMessage` exception | Message fails → retry/DLQ |
| **No Route Found** | `RouteNotFound` exception | Message fails → retry/DLQ |
| **Handler Exception** | Exception propagates | Message fails → retry/DLQ |

All failures are added to `batchItemFailures` in the Lambda response, allowing SQS to handle retries and dead letter queues according to your queue configuration.

---

## Performance Features

- **FastAPI-like Efficiency:** Minimal overhead with fast dictionary-based routing
- **Parallel Processing:** Standard SQS messages are processed concurrently
- **FIFO Ordering:** FIFO messages maintain order within message groups
- **Partial Batch Failures:** Only failed messages are retried, not entire batches
- **Type Safety:** Full type checking and validation with Pydantic
- **Memory Efficient:** Minimal overhead per message with automatic cleanup

---

## Documentation

- **Examples:** See the `examples/` directory for complete working examples
- **Type Safety:** Full type hints throughout for excellent IDE support
- **API Reference:** All classes and methods include comprehensive docstrings

---

## Contributing

Contributions, issues, and feature requests are welcome!
Please open an issue or submit a pull request.

---

## License

This project is licensed under the terms of the MIT license.

---

**Ready to build type-safe, FastAPI-like SQS processors? Try FastSQS today!**