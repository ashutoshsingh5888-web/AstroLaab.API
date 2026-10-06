from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
import traceback
import secrets
import time
import logging

# SlowAPI imports
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

# Engine imports
from engine.astronomy import calculate_chart
from engine.dasha import calculate_vimshottari_dasha
from engine.panchang import calculate_panchang
from engine.charts import generate_chart_layout

# ====================================================
# Environment Detection
# ====================================================
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ====================================================
# Logging Setup
# ====================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ====================================================
# App Initialization
# ====================================================
if ENVIRONMENT == "production":
    app = FastAPI(
        title="AstroLaab Engine API",
        version="1.0.1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None
    )
else:
    app = FastAPI(
        title="AstroLaab Engine API",
        version="1.0.1",
        description="Indian Vedic Astrology Engine - Lahiri Ayanamsa"
    )

# ====================================================
# Rate Limiter (Per API Key)
# ====================================================
def api_key_identifier(request: Request):
    return request.headers.get("x-api-key") or get_remote_address(request)

limiter = Limiter(key_func=api_key_identifier)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# ====================================================
# CORS
# ====================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://astrolaab.com",
        "https://www.astrolaab.com"
    ],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ====================================================
# API Key
# ====================================================
API_KEY = os.getenv("ASTROLAAB_API_KEY")

def verify_api_key(x_api_key: str = Header(None)):
    if API_KEY is None:
        raise HTTPException(status_code=500, detail="API key not configured")
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="API key required")
    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")

# ====================================================
# Request Logging Middleware
# ====================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = round((time.time() - start_time) * 1000, 2)

    logger.info(
        f"{request.method} {request.url.path} | "
        f"Status: {response.status_code} | "
        f"Time: {process_time}ms"
    )
    return response

# ====================================================
# Pydantic Model
# ====================================================
class ChartRequest(BaseModel):
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    chart_style: str = Field("north", pattern="^(north|south)$")

    @model_validator(mode="after")
    def validate_calendar_date(self):
        try:
            datetime(self.year, self.month, self.day, self.hour, self.minute)
        except ValueError as exc:
            raise ValueError("invalid calendar date/time") from exc
        return self

# ====================================================
# Health
# ====================================================
@app.get("/api/v1/health")
def health():
    return {
        "status": "running",
        "engine": "AstroLaab",
        "version": "v1.0.1",
        "ayanamsa": "Lahiri"
    }

# ====================================================
# Chart Endpoint (FIXED)
# ====================================================
@limiter.limit("20/minute")
@app.post("/api/v1/chart")
def generate_chart(
    request: Request,
    payload: ChartRequest,
    _: None = Depends(verify_api_key)
):
    try:
        # Inputs are declared IST. Convert once at the API boundary, then keep
        # all Swiss Ephemeris calculations on UT.
        local_dt = datetime(
            payload.year,
            payload.month,
            payload.day,
            payload.hour,
            payload.minute,
            tzinfo=ZoneInfo("Asia/Kolkata"),
        )
        utc_dt = local_dt.astimezone(timezone.utc)
        utc_decimal_hour = (
            utc_dt.hour
            + utc_dt.minute / 60
            + utc_dt.second / 3600
        )

        chart_data = calculate_chart(
            utc_dt.year,
            utc_dt.month,
            utc_dt.day,
            utc_decimal_hour,
            payload.latitude,
            payload.longitude
        )

        panchang_data = calculate_panchang(
            utc_dt.year,
            utc_dt.month,
            utc_dt.day,
            utc_decimal_hour
        )

        dasha_data = calculate_vimshottari_dasha(
            chart_data["Planets"]["Moon"]["longitude"],
            datetime(payload.year, payload.month, payload.day)
        )

        layout = generate_chart_layout(chart_data, payload.chart_style)

        return {
            "meta": {
                "api_version": "v1.0.1",
                "input_timezone": "Asia/Kolkata (IST)",
                "timezone_conversion": "IST local time converted to UTC before Swiss Ephemeris",
                "ayanamsa": "Lahiri",
                "time_scales": {"planets": "UT input to Swiss Ephemeris", "houses": "UT"},
                "utc": utc_dt.isoformat()
            },
            "Ascendant": chart_data["Ascendant"],
            "Planets": chart_data["Planets"],
            "Panchang": panchang_data,
            "Mahadasha_Timeline": dasha_data["timeline"],
            "Current_Running_Dasha": dasha_data["current"],
            "Chart_Layout": layout
        }

    except Exception:
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal calculation error")