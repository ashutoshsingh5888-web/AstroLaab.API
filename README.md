# AstroLaab API
# AstroLaab API

Vedic Astrology Engine using Lahiri Ayanamsa.

## Setup

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

## Endpoints

/health
/chart


# AstroLaab API

Vedic Astrology Engine (Lahiri Ayanamsa, IST-based input)

## Features

- Sidereal Lahiri calculations
- True Rahu / Ketu
- Whole sign houses
- Vimshottari Mahadasha
- Panchang
- North / South chart layout
- IST → UTC conversion
- Hardened API layer

## Setup

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

## Endpoints

/health
/chart
