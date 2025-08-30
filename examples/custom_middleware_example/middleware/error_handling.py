from fastsqs import Middleware

class ErrorHandlingMiddleware(Middleware):
    async def before(self, payload, record, context, ctx):
        if not payload.get("action"):
            raise ValueError("Missing required field: action")
        ctx["error_count"] = ctx.get("error_count", 0)

    async def after(self, payload, record, context, ctx, result):
        print(f"[SUCCESS] Message {record.get('messageId')} completed")

    async def error(self, payload, record, context, ctx, error):
        error_count = ctx.get("error_count", 0) + 1
        ctx["error_count"] = error_count
        print(f"[ERROR] Message {record.get('messageId')} failed")
        print(f"[ERROR] Error: {type(error).__name__}: {error}")
        print(f"[ERROR] Total errors: {error_count}")
        return {"status": "error", "error": str(error)}
