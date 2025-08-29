# fastsqs

**Fast, modern, async SQS routing and middleware for Python.**

[![PyPI version](https://img.shields.io/pypi/v/fastsqs.svg)](https://pypi.org/project/fastsqs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Key Features

- 🚀 **High Performance:** Async message routing for AWS SQS, designed for speed and scalability.
- 🧩 **Declarative Routing:** Organize your SQS message handling with nested routers and decorators.
- 🔒 **Validation:** Per-route payload validation using Pydantic models.
- 🛠️ **Middleware:** Add before/after hooks for logging, timing, masking, and more.
- 🦾 **Partial Batch Failure:** Native support for AWS Lambda batch failure responses.
- 🐍 **Pythonic & Intuitive:** Type hints, editor support, and a familiar API for Python developers.

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

## Example

### Create your app

```python
from fastsqs import QueueApp, QueueRouter, Middleware
from pydantic import BaseModel

class GreetingPayload(BaseModel):
    type: str
    message: str

router = QueueRouter(key="type")

@router.route("greeting", model=GreetingPayload)
async def handle_greeting(payload, record, context, ctx, data):
    print(f"Greeting: {data.message}")

app = QueueApp(title="Greeting SQS App", debug=True)
app.include_router(router)


def lambda_handler(event, context):
    return app.handler(event, context)
```

### Example Payload

```json
{
  "type": "greeting",
  "message": "Hello from SQS!"
}
```

### Add Middleware

```python
class PrintMiddleware(Middleware):
    async def before(self, payload, record, context, ctx):
        print("Before:", payload)
    async def after(self, payload, record, context, ctx, error):
        print("After:", payload, "Error:", error)

app.add_middleware(PrintMiddleware())
```

---

## How it Works

- **Routing:** Use `QueueRouter` to route messages by payload fields. Decorators make it easy to register handlers.
- **Validation:** Attach Pydantic models to routes for automatic payload validation.
- **Middleware:** Add global or per-route middleware for logging, timing, masking, etc.
- **Batch Failure:** Handles partial failures for SQS-triggered Lambda functions, so only failed messages are retried.

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
