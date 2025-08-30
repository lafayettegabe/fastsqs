from fastsqs import QueueApp, QueueRouter, LoggingMiddleware, TimingMsMiddleware
import json


user_router = QueueRouter(key="action")

app = QueueApp(
    title="Middleware Example App",
    description="Example showing built-in middleware usage",
    version="1.0.0",
    debug=True,
)

app.add_middleware(LoggingMiddleware(mask_fields=["password", "ssn"]))
app.add_middleware(TimingMsMiddleware())

app.include_router(user_router)

@user_router.route("login")
async def handle_user_login(payload, record, context, ctx):
    print(f"User logged in: {payload.get('userId')}")
    await asyncio.sleep(0.1)
    return {"status": "success", "userId": payload.get("userId")}


@user_router.route("logout")
async def handle_user_logout(payload, record, context, ctx):
    print(f"User logged out: {payload.get('userId')}")
    await asyncio.sleep(0.05)
    return {"status": "success", "userId": payload.get("userId")}


@user_router.route("profile_update")
async def handle_profile_update(payload, record, context, ctx):
    print(f"Profile updated for user: {payload.get('userId')}")
    await asyncio.sleep(0.2)
    return {"status": "success", "userId": payload.get("userId")}

def lambda_handler(event, context):
    return app.handler(event, context)


# -----------------------------------------------------------------------
# -------------------------------- TESTS --------------------------------

async def test_middleware():
    print("=== Testing Middleware ===")

    test_events = [
        {
            "Records": [
                {
                    "messageId": "msg-001",
                    "body": json.dumps(
                        {
                            "action": "login",
                            "userId": "user123",
                            "password": "secret123",
                            "timestamp": "2024-01-01T10:00:00Z",
                        }
                    ),
                    "attributes": {},
                }
            ]
        },
        {
            "Records": [
                {
                    "messageId": "msg-002",
                    "body": json.dumps(
                        {
                            "action": "profile_update",
                            "userId": "user123",
                            "ssn": "123-45-6789",
                            "email": "user@example.com",
                        }
                    ),
                    "attributes": {},
                }
            ]
        },
        {
            "Records": [
                {
                    "messageId": "msg-003",
                    "body": json.dumps(
                        {
                            "action": "logout",
                            "userId": "user123",
                            "sessionId": "sess-456",
                        }
                    ),
                    "attributes": {},
                }
            ]
        },
    ]

    for i, event in enumerate(test_events, 1):
        print(f"\n--- Test Event {i} ---")
        result = lambda_handler(event, None)
        print(f"Result: {result}")


if __name__ == "__main__":
    test_middleware()