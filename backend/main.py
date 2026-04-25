"""
ClaimCall — FastAPI application entry point.

Service instances are created once at startup and stored in app.state.
All routers access shared services via request.app.state (no module globals).
"""

import base64
import json
import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import get_settings
from routers import calls, claims, health, twilio, webhooks
from services.supabase_client import SupabaseService
from services.twilio_client import TwilioClient

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def _check_supabase_key(key: str) -> None:
    """Warn loudly if the Supabase key is not a service_role JWT."""
    try:
        # JWT payload is the second segment
        payload_b64 = key.split(".")[1]
        # Add padding
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(padded))
        role = payload.get("role", "unknown")
        if role != "service_role":
            logger.critical(
                "⚠️  SUPABASE_SERVICE_KEY has role='%s' — must be 'service_role'. "
                "RLS-protected writes WILL fail. "
                "Get the correct key from: Supabase Dashboard → Settings → API → service_role",
                role,
            )
    except Exception:
        logger.warning("Could not decode SUPABASE_SERVICE_KEY JWT to verify role")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ClaimCall starting up (env=%s)", settings.environment)

    # Validate Supabase key role
    _check_supabase_key(settings.supabase_service_key)

    # Initialize Supabase
    app.state.supabase = await SupabaseService.create(settings)
    if not await app.state.supabase.ping():
        logger.error("Supabase connection failed — check SUPABASE_URL and SUPABASE_SERVICE_KEY")
    else:
        logger.info("Supabase connected")

    # Initialize Twilio
    app.state.twilio = TwilioClient(settings)
    logger.info("Twilio client ready (from=%s)", settings.twilio_phone_number)

    # Initialize AI-Coustics processor (optional — degrades gracefully if missing)
    app.state.aic_processor = None
    if settings.aicoustics_enabled and settings.aicoustics_api_key:
        try:
            import aic_sdk as aic
            model_path = aic.Model.download("quail-vf-2.1-l-16khz", "/tmp/aic_models")
            model = aic.Model.from_file(model_path)
            config = aic.ProcessorConfig.optimal(model, num_channels=1)
            app.state.aic_processor = aic.Processor(model, settings.aic_sdk_license, config)
            logger.info("AI-Coustics processor initialized (model=quail-vf-2.1-l-16khz)")
        except Exception as exc:
            logger.warning("AI-Coustics init failed, audio enhancement disabled: %s", exc)

    yield

    logger.info("ClaimCall shutting down")


app = FastAPI(
    title="ClaimCall",
    description="AI Voice Agent for Insurance FNOL Intake",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [settings.app_host],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(twilio.router)
app.include_router(webhooks.router)
app.include_router(calls.router, prefix="/api")
app.include_router(claims.router, prefix="/api")

# Dashboard — served last so it doesn't shadow API routes
app.mount("/", StaticFiles(directory="static", html=True), name="static")
