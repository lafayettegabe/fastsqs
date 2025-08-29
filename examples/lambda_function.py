from fastsqs import QueueApp, QueueRouter, LoggingMiddleware, TimingMsMiddleware
import json
import asyncio

## If you have Pydantic models, import them here

## Create app and top-level router based on 'action'
app = QueueApp(
    title="User+Order Processor",
    description="Handles multiple kinds of events via SQS",
    version="2.0.0",
    debug=True,
    strict=True
)

## -------- ROUTERS -------- ##
router = QueueRouter("action")

create_router = QueueRouter("entity")
db_router = QueueRouter("db")

router.subrouter("create", create_router)
router.subrouter("write", db_router)

## -------- MIDDLEWARES -------- ##
app.add_middleware(LoggingMiddleware(mask_fields=["password"]))
app.add_middleware(TimingMsMiddleware())

## Include router in app
app.include_router(router)

## -------- CREATE HANDLERS -------- ##
@create_router.route("user")
def create_user(payload, ctx, **_):
    print(f"[CREATE USER] payload={payload} route={ctx['route_path']}")

@create_router.route("order")
def create_order(payload, ctx, **_):
    print(f"[CREATE ORDER] payload={payload} route={ctx['route_path']}")

## -------- UPDATE HANDLER -------- ##
@router.route("update")
def update_user(payload, ctx, **_):
    print(f"[UPDATE USER] payload={payload} route={ctx['route_path']}")

## -------- DELETE HANDLER -------- ##
@router.route("delete")
def delete_user(payload, ctx, **_):
    print(f"[DELETE USER] payload={payload} route={ctx['route_path']}")

## -------- SEARCH HANDLER -------- ##
@router.route("search")
def search_users(payload, ctx, **_):
    print(f"[SEARCH USERS] payload={payload} route={ctx['route_path']}")

## -------- SPECIAL DB ROUTING -------- ##
@db_router.route("rds")
def write_to_rds(payload, ctx, **_):
    print(f"[WRITE TO RDS] payload={payload} route={ctx['route_path']}")

@db_router.route("cache")
def write_to_cache(payload, ctx, **_):
    print(f"[WRITE TO CACHE] payload={payload} route={ctx['route_path']}")

## -------- FALLBACK HANDLER -------- ##
@router.wildcard()
def unknown_action(payload, ctx, **_):
    print(f"[FALLBACK] Unknown action={payload.get('action')} full_payload={payload}")

## Lambda entry point
def lambda_handler(event, context):
    return app.handler(event, context)