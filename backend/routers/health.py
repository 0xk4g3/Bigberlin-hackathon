from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    supabase = getattr(request.app.state, "supabase", None)
    sb_status = "not_initialized"
    if supabase:
        ok = await supabase.ping()
        sb_status = "connected" if ok else "error"

    status_code = 200 if sb_status == "connected" else 503
    return JSONResponse(
        content={
            "status": "ok" if status_code == 200 else "degraded",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "supabase": sb_status,
        },
        status_code=status_code,
    )
