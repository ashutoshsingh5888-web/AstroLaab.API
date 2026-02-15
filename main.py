from fastapi import FastAPI, Query, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import os
import traceback
import secrets

# Engine imports
from engine.astronomy import calculate_chart
from engine.dasha import calculate_vimshottari_dasha
from engine.panchang import calculate_panchang
from engine.charts import generate_chart_layout

app = FastAPI(
    title="AstroLaab Engine API",
    version="1.0.0",
    description="Indian Vedic Astrology Engine - Lahiri Ayanamsa"
)

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Later restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Load API Key From Environment
# -----------------------------
API_KEY = os.getenv("ASTROLAAB_API_KEY")


def verify_api_key(x_api_key: str = Header(None)):
    if API_KEY is None:
        raise HTTPException(
            status_code=500,
            detail="API key not configured on server"
        )

    if x_api_key is None:
        raise HTTPException(
            status_code=401,
            detail="API key required - include X-Api-Key header"
        )

    if not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )


# -----------------------------
# Health Endpoint (Public)
# -----------------------------
@app.get("/health")
def health():
    return {
        "status": "running",
        "engine": "AstroLaab",
        "ayanamsa": "Lahiri",
        "timezone_input": "IST"
    }


# -----------------------------
# IST → UTC Conversion
# -----------------------------
def ist_to_utc(year, month, day, hour, minute):
    ist_time = datetime(year, month, day, hour, minute)
    utc_time = ist_time - timedelta(hours=5, minutes=30)
    return utc_time


# -----------------------------
# Protected Chart Endpoint
# -----------------------------
@app.get("/chart")
def generate_chart(
    year: int = Query(..., ge=1900, le=2100),
    month: int = Query(..., ge=1, le=12),
    day: int = Query(..., ge=1, le=31),
    hour: int = Query(..., ge=0, le=23),
    minute: int = Query(..., ge=0, le=59),
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    chart_style: str = Query("north", pattern="^(north|south)$"),
    _: None = Depends(verify_api_key)  # Add as dependency
):
    try:
        # Convert IST → UTC
        utc_time = ist_to_utc(year, month, day, hour, minute)

        # Core Chart
        chart_data = calculate_chart(
            utc_time.year,
            utc_time.month,
            utc_time.day,
            utc_time.hour + utc_time.minute / 60,
            latitude,
            longitude
        )

        # Panchang
        panchang_data = calculate_panchang(
            utc_time.year,
            utc_time.month,
            utc_time.day,
            utc_time.hour + utc_time.minute / 60
        )

        # Dasha
        dasha_data = calculate_vimshottari_dasha(
            chart_data["Planets"]["Moon"]["longitude"],
            datetime(year, month, day)
        )

        # Layout
        layout = generate_chart_layout(
            chart_data,
            chart_style
        )

        return {
            "meta": {
                "input_timezone": "IST",
                "calculated_in_utc": True,
                "ayanamsa": "Lahiri"
            },
            "Ascendant": chart_data["Ascendant"],
            "Planets": chart_data["Planets"],
            "Panchang": panchang_data,
            "Mahadasha_Timeline": dasha_data["timeline"],
            "Current_Running_Dasha": dasha_data["current"],
            "Chart_Layout": layout
        }

    except Exception:
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail="Internal calculation error"
        )