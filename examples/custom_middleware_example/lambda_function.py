
from fastsqs import QueueApp, QueueRouter
import json
from middleware.custom_logging import CustomLoggingMiddleware
from middleware.error_handling import ErrorHandlingMiddleware
from middleware.metrics import MetricsMiddleware


user_router = QueueRouter(key="action")

app = QueueApp(
    title="Custom Middleware Example App",
    description="Example showing custom middleware usage",
    version="1.0.0",
    debug=True,
)

app.add_middleware(CustomLoggingMiddleware())
app.add_middleware(ErrorHandlingMiddleware())
app.add_middleware(MetricsMiddleware())

app.include_router(user_router)


@user_router.route("login")
async def handle_user_login(payload, record, context, ctx):
    """Handle user login messages."""
    print(f"User logged in: {payload.get('userId')}")
    return {"status": "success", "userId": payload.get("userId")}


@user_router.route("logout")
async def handle_user_logout(payload, record, context, ctx):
    """Handle user logout messages."""
    print(f"User logged out: {payload.get('userId')}")
    return {"status": "success", "userId": payload.get("userId")}


@user_router.route("invalid")
async def handle_invalid_message(payload, record, context, ctx):
    """Handle invalid messages (will trigger error middleware)."""
    raise ValueError("This is a test error")

def lambda_handler(event, context):
    return app.handler(event, context)


# -----------------------------------------------------------------------
# -------------------------------- TESTS --------------------------------

def test_custom_middleware():
    """Test the custom middleware functionality."""
    print("=== Testing Custom Middleware ===")

    test_events = [
        {
            "Records": [
                {
                    "messageId": "msg-001",
                    "body": json.dumps({"action": "login", "userId": "user123"}),
                    "attributes": {},
                }
            ]
        },
        {
            "Records": [
                {
                    "messageId": "msg-002",
                    "body": json.dumps({"action": "logout", "userId": "user123"}),
                    "attributes": {},
                }
            ]
        },
        {
            "Records": [
                {
                    "messageId": "msg-003",
                    "body": json.dumps({"action": "invalid"}),
                    "attributes": {},
                }
            ]
        },
    ]

    for i, event in enumerate(test_events, 1):
        print(f"\n--- Test Event {i} ---")
        try:
            result = lambda_handler(event, None)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Exception: {e}")


if __name__ == "__main__":
    test_custom_middleware()