# fastsqs

**Fast, modern, async SQS routing and middleware for Python.**

[![PyPI version](https://img.shields.io/pypi/v/fastsqs.svg)](https://pypi.org/project/fastsqs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Key Features

- 🚀 **High Performance:** Async message routing for AWS SQS, designed for speed and scalability
- 🧩 **Declarative Routing:** Organize your SQS message handling with nested routers and decorators
- 🔄 **Auto Async/Sync:** Write handlers as sync or async functions - framework handles both automatically
- 🔒 **Validation:** Per-route payload validation using Pydantic models
- 🛠️ **Middleware:** Add before/after hooks for logging, timing, masking, and more
- 🦾 **Partial Batch Failure:** Native support for AWS Lambda batch failure responses
- 🔀 **FIFO & Standard Queues:** Full support for both SQS queue types with ordered processing for FIFO
- 🎯 **Wildcard & Default Routes:** Flexible routing with wildcard matching and fallback handlers
- 🏗️ **Nested Routing:** Build complex routing hierarchies with subrouters
- 🐍 **Pythonic & Intuitive:** Type hints, editor support, and a familiar API for Python developers

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

### Basic Example

```python
from fastsqs import QueueApp, QueueRouter
from pydantic import BaseModel

class GreetingPayload(BaseModel):
    type: str
    message: str

# Create router
router = QueueRouter(key="type")

# Sync handler - no async needed!
@router.route("greeting", model=GreetingPayload)
def handle_greeting(payload, record, context, ctx, data):
    print(f"Greeting: {data.message}")

# Async handler also works
@router.route("async_task")
async def handle_async_task(payload, ctx):
    # Do async work here
    print(f"Processing async: {payload}")

# Create app
app = QueueApp(title="My SQS App", debug=True)
app.include_router(router)

# Lambda handler
def lambda_handler(event, context):
    return app.handler(event, context)
```

### Example Payloads

```json
{
  "type": "greeting",
  "message": "Hello from SQS!"
}
```

```json
{
  "type": "async_task",
  "data": "Some async processing data"
}
```

---

## Advanced Features

### FIFO Queue Support

```python
from fastsqs import QueueApp, QueueType

app = QueueApp(
    queue_type=QueueType.FIFO,
    debug=True
)

# Messages in the same messageGroupId are processed sequentially
# Different groups are processed in parallel
```

### Wildcard and Default Routes

```python
router = QueueRouter(key="action")

# Handle specific routes
@router.route("process")
def handle_process(payload):
    print("Processing...")

# Wildcard - matches any value
@router.wildcard()
def handle_any_action(payload, ctx):
    action = payload.get("action", "unknown")
    print(f"Handling action: {action}")

# Default - called when key is missing
@router.route()  # No value = default
def handle_no_action(payload):
    print("No action specified")
```

### Nested Routing

```python
# Main router routes by "service"
main_router = QueueRouter(key="service")

# Sub-router routes by "action" within a service
user_router = QueueRouter(key="action")

@user_router.route("create")
def create_user(payload):
    print(f"Creating user: {payload}")

@user_router.route("delete")
def delete_user(payload):
    print(f"Deleting user: {payload}")

# Attach sub-router
main_router.subrouter("users", user_router)

app.include_router(main_router)
```

Example payload for nested routing:
```json
{
  "service": "users",
  "action": "create",
  "user_data": {...}
}
```

### Middleware

```python
from fastsqs import Middleware, TimingMsMiddleware, LoggingMiddleware

# Built-in timing middleware
app.add_middleware(TimingMsMiddleware())

# Built-in logging middleware
app.add_middleware(LoggingMiddleware(
    include_payload=True,
    mask_fields=["password", "secret"]
))

# Custom middleware
class AuthMiddleware(Middleware):
    async def before(self, payload, record, context, ctx):
        # Validate auth token
        if not payload.get("auth_token"):
            raise ValueError("Missing auth token")
        print("Auth validated")
    
    async def after(self, payload, record, context, ctx, error):
        if error:
            print(f"Handler failed: {error}")
        else:
            print("Handler completed successfully")

app.add_middleware(AuthMiddleware())
```

### Payload Scoping

```python
# Control what payload is passed to handlers
router = QueueRouter(
    key="type",
    payload_scope="both"  # "root", "current", or "both"
)

@router.route("nested")
def handle_nested(payload, current_payload, root_payload):
    # payload = root_payload (for "both" scope)
    # current_payload = current level payload
    # root_payload = original payload
    pass
```

### Error Handling

```python
app = QueueApp(
    on_decode_error="skip",      # Skip invalid JSON
    on_validation_error="skip",   # Skip validation failures
    strict=False                 # Don't error on unmatched routes
)

# Custom default handler for unmatched routes
def default_handler(payload, ctx):
    print(f"Unhandled message: {payload}")

app = QueueApp(default_handler=default_handler)
```

---

## Package Structure

The library is organized into clean, modular components:

```
fastsqs/
├── __init__.py          # Main exports
├── types.py             # Type definitions
├── exceptions.py        # Custom exceptions
├── utils.py             # Utility functions
├── app.py              # Main QueueApp class
├── middleware/         # Middleware components
│   ├── __init__.py
│   ├── base.py         # Base middleware
│   ├── timing.py       # Timing middleware
│   └── logging.py      # Logging middleware
└── routing/            # Routing components
    ├── __init__.py
    ├── entry.py        # Route entry
    └── router.py       # Router implementation
```

---

## How it Works

- **Automatic Async/Sync:** Write handlers as regular functions or async functions - the framework automatically detects and handles both
- **Routing:** Use `QueueRouter` to route messages by payload fields. Decorators make it easy to register handlers
- **Validation:** Attach Pydantic models to routes for automatic payload validation
- **Middleware:** Add global or per-route middleware for logging, timing, masking, etc.
- **Batch Failure:** Handles partial failures for SQS-triggered Lambda functions, so only failed messages are retried
- **FIFO Support:** Sequential processing within message groups while maintaining parallelism across groups

---

## Performance Features

- **Parallel Processing:** Standard SQS messages are processed concurrently
- **FIFO Ordering:** FIFO messages maintain order within message groups
- **Partial Batch Failures:** Only failed messages are retried, not entire batches
- **Efficient Routing:** Fast dictionary-based message routing
- **Memory Efficient:** Minimal overhead per message

---

## Documentation

- [API Reference](#) (coming soon)
- [Tutorials](#) (coming soon)
- [Examples](#) (see `examples/`)

---

## Contributing

Contributions, issues, and feature requests are welcome!
Please open an issue or submit a pull request.

---

## License

This project is licensed under the terms of the MIT license.

---

**Ready to build async, robust SQS message processors? Try fastsqs today!**