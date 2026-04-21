"""
api.py - FastAPI backend for the Statistics
"""

import os
import sys
import uuid
import decimal
import datetime
import logging
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))
from database import (
    get_oracle_connection,
    get_data,
    get_locations,
    get_units,
    get_units_for_indicators,
    get_indicators,
    test_connection,
)

app = FastAPI(title="Statistics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAP_TABLE = {
    'Prices and Interest Rates': ['FACT_CPI', 'FACT_INTEREST'],
    'External Sector':            'FACT_BOP',
    'Financial Sector Indicators':'FACT_MONETARY',
    'Government Finance Statistics':'FACT_FISC',
    'National Accounts':          'FACT_GDP',
    'Payment Statistics':         'FACT_PAYMENT',
}


CATEGORIES = [
    {"id": "Prices and Interest Rates",          "label": "Prices and Interest Rates"},
    {"id": "External Sector",                    "label": "External Sector"},
    {"id": "Financial Sector Indicators",        "label": "Financial Sector Indicators"},
    {"id": "Government Finance Statistics",      "label": "Government Finance Statistics"},
    {"id": "National Accounts",                  "label": "National Accounts"},
    {"id": "Payment Statistics",                 "label": "Payment Statistics"}
]

_sessions: dict = {}


# ── Oracle type serialization ──────────────────────────────────────────────────

def _safe(value):
    """Convert Oracle/Python types that are not JSON-serializable to safe equivalents."""
    if value is None:
        return None
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    # numpy scalar types (pandas internal)
    try:
        import numpy as np
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, float) and np.isnan(value):
            return None
    except ImportError:
        pass
    # Python float NaN
    if isinstance(value, float) and value != value:
        return None
    return value


def _df_to_records(df):
    """Convert a DataFrame to a list of JSON-safe dicts."""
    records = []
    for row in df.itertuples(index=False):
        records.append({col: _safe(val) for col, val in zip(df.columns, row)})
    return records


# ── Schemas ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class DataRequest(BaseModel):
    category: str
    start_year: int = 2015
    start_month: Optional[int] = None
    start_day: Optional[int] = None
    end_year: int = 2025
    end_month: Optional[int] = None
    end_day: Optional[int] = None
    location: str = "Tanzania"
    indicator_names: Optional[List[str]] = None
    unit_names: Optional[List[str]] = None
    aggregation: str = "monthly"


# ── Auth helper ────────────────────────────────────────────────────────────────

def _get_session(authorization: str = Header(...)) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    session = _sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(req: LoginRequest):
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "1521"))
    service_name = os.getenv("DB_SERVICE_NAME", "xe")
    try:
        conn = get_oracle_connection(
            req.username, req.password, host, port, service_name
        )
        ok, msg, ts = test_connection(conn)
        if not ok:
            raise HTTPException(status_code=401, detail=msg)
    except HTTPException:
        raise
    except Exception as e:
        log.error("Login failed: %s", e)
        raise HTTPException(status_code=401, detail=str(e))

    token = str(uuid.uuid4())
    _sessions[token] = {"conn": conn}
    log.info("Session created for %s@%s", req.username, host)
    return {"token": token, "timestamp": str(ts)}


@app.post("/api/logout")
def logout(session: dict = Depends(_get_session), authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    _sessions.pop(token, None)
    return {"ok": True}


@app.get("/api/categories")
def categories(_session: dict = Depends(_get_session)):
    return {"categories": CATEGORIES}


@app.get("/api/indicators")
def indicators(category: str, session: dict = Depends(_get_session)):
    fact_tables = MAP_TABLE.get(category)
    if not fact_tables:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
    try:
        if isinstance(fact_tables, list):
            dfs = [get_indicators(session["conn"], fact_table=ft) for ft in fact_tables]
            df = pd.concat(dfs, ignore_index=True).drop_duplicates(subset=['INDICATOR_NAME'])
        else:
            df = get_indicators(session["conn"], fact_table=fact_tables)
        return _df_to_records(df)
    except Exception as e:
        log.error("indicators(%s) failed: %s", category, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/locations")
def locations(session: dict = Depends(_get_session)):
    try:
        return {"locations": get_locations(session["conn"])}
    except Exception as e:
        log.error("locations failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/units")
def units(category: str, session: dict = Depends(_get_session)):
    fact_tables = MAP_TABLE.get(category)
    if not fact_tables:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
    try:
        if isinstance(fact_tables, list):
            all_units: set = set()
            for ft in fact_tables:
                df = get_indicators(session["conn"], fact_table=ft)
                ind_names = tuple(df["INDICATOR_NAME"].tolist()) if not df.empty else ()
                all_units.update(get_units_for_indicators(session["conn"], ind_names, category, ft))
            unit_list = sorted(all_units)
        else:
            df = get_indicators(session["conn"], fact_table=fact_tables)
            ind_names = tuple(df["INDICATOR_NAME"].tolist()) if not df.empty else ()
            unit_list = get_units_for_indicators(session["conn"], ind_names, category)
        return {"units": unit_list}
    except Exception as e:
        log.error("units(%s) failed: %s", category, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data")
def data(req: DataRequest, session: dict = Depends(_get_session)):
    fact_tables = MAP_TABLE.get(req.category)
    if not fact_tables:
        raise HTTPException(status_code=400, detail=f"Unknown category: {req.category}")
    try:
        kwargs = dict(
            connection=session["conn"],
            data_group=req.category,
            start_year=req.start_year,
            start_month=req.start_month,
            start_day=req.start_day,
            end_year=req.end_year,
            end_month=req.end_month,
            end_day=req.end_day,
            location=req.location,
            indicator_names=req.indicator_names,
            unit_names=req.unit_names,
            aggregation=req.aggregation,
            wide_format=False,
        )
        if isinstance(fact_tables, list):
            dfs = [get_data(**kwargs, fact_table=ft) for ft in fact_tables]
            df = pd.concat(dfs, ignore_index=True)
        else:
            df = get_data(**kwargs)
        if df.empty:
            return {"data": [], "columns": []}
        return {"data": _df_to_records(df), "columns": list(df.columns)}
    except Exception as e:
        log.error("data(%s) failed: %s", req.category, e)
        raise HTTPException(status_code=500, detail=str(e))
