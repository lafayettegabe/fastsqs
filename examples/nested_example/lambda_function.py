from fastsqs import QueueApp, QueueRouter, LoggingMiddleware, TimingMsMiddleware
import json


app = QueueApp(
    title="User+Order Processor",
    description="Handles multiple kinds of events via SQS with nested routing",
    version="2.0.0",
    debug=True,
    strict=True,
)

router = QueueRouter("action")

create_router = QueueRouter("entity")
db_router = QueueRouter("db")

router.subrouter("create", create_router)
router.subrouter("write", db_router)

app.add_middleware(LoggingMiddleware(mask_fields=["password"]))
app.add_middleware(TimingMsMiddleware())

app.include_router(router)


@create_router.route("user")
def create_user(payload, ctx, **_):
    print(f"[CREATE USER] payload={payload} route={ctx['route_path']}")


@create_router.route("order")
def create_order(payload, ctx, **_):
    print(f"[CREATE ORDER] payload={payload} route={ctx['route_path']}")


@router.route("update")
def update_user(payload, ctx, **_):
    print(f"[UPDATE USER] payload={payload} route={ctx['route_path']}")


@router.route("delete")
def delete_user(payload, ctx, **_):
    print(f"[DELETE USER] payload={payload} route={ctx['route_path']}")


@router.route("search")
def search_users(payload, ctx, **_):
    print(f"[SEARCH USERS] payload={payload} route={ctx['route_path']}")


@db_router.route("rds")
def write_to_rds(payload, ctx, **_):
    print(f"[WRITE TO RDS] payload={payload} route={ctx['route_path']}")


@db_router.route("cache")
def write_to_cache(payload, ctx, **_):
    print(f"[WRITE TO CACHE] payload={payload} route={ctx['route_path']}")


@router.wildcard()
def unknown_action(payload, ctx, **_):
    print(
        f"[FALLBACK] Unknown action={payload.get('action')} " f"full_payload={payload}"
    )


def lambda_handler(event, context):
    return app.handler(event, context)


# -----------------------------------------------------------------------
# -------------------------------- TESTS --------------------------------

def test_nested_routing():
    print("=== Testing Nested Routing ===")

    test_cases = [
        {"action": "create", "entity": "user", "name": "John Doe"},
        {"action": "create", "entity": "order", "orderId": "12345"},
        {"action": "update", "userId": "user123", "name": "Jane Doe"},
        {"action": "delete", "userId": "user123"},
        {"action": "search", "query": "John"},
        {"action": "write", "db": "rds", "table": "users"},
        {"action": "write", "db": "cache", "key": "user:123"},
        {"action": "unknown", "data": "test"},
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test_case['action']} ---")
        event = {
            "Records": [
                {
                    "messageId": f"msg-{i}",
                    "body": json.dumps(test_case),
                    "attributes": {},
                }
            ]
        }

        result = lambda_handler(event, None)
        print(f"Result: {result}")


if __name__ == "__main__":
    test_nested_routing()
