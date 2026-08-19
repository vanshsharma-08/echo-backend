from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import logging

from app.models import ValidationRequest, ValidationResponse, AlertResponse
# from app.mock_ml import get_mock_alerts as get_alerts_source
from app.ml_source import get_alerts_source
from app.storage import init_db, save_validation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echo-hub")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("E.C.H.O. Hub started, DB initialized.")
    yield
    logger.info("E.C.H.O. Hub shutting down.")


app = FastAPI(title="E.C.H.O. Hub API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/health")
def health_check():
    return {"status": "operational", "service": "E.C.H.O. Hub"}


@app.get("/alerts", response_model=List[AlertResponse])
def get_alerts():
    """
    Sub-2KB compressed JSON payload for low-bandwidth edge delivery.
    response_model=List[AlertResponse] does double duty:
      1. Validates outgoing data against the contract (catches ML bugs before they ship)
      2. Strips any extra fields the ML/mock layer accidentally included
    """
    try:
        alerts = get_alerts_source()
        if not alerts:
            logger.warning("get_alerts_source() returned an empty list.")
        return alerts
    except Exception as e:
        logger.error(f"Failed to fetch alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A.U.R.A. engine unavailable — showing no alerts.",
        )


@app.post("/validate", response_model=ValidationResponse)
def validate_alert(payload: ValidationRequest):
    """
    Human-in-the-loop endpoint. Pydantic already rejects malformed payloads
    (missing fields, wrong types) with a 422 before this function body even runs.
    """
    success = save_validation(
        alert_id=payload.alert_id,
        is_valid=payload.is_valid,
        feedback=payload.user_feedback,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save validation — database error.",
        )

    return ValidationResponse(
        status="success",
        message=f"Validation recorded for {payload.alert_id}",
    )