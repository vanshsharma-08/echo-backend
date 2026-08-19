"""The one file backend imports. Exposes get_predictions() -> list[dict] matching AlertResponse."""
import uuid
from datetime import datetime, timezone

from data_ingestion.weather import get_weather_features
from data_ingestion.satellite import get_ndwi_ndvi
from data_ingestion.iot_mock import get_mock_iot_reading
from model.classifier import predict_risk

# Default bounding box: ITER campus / Bhubaneswar ward area — swap as needed
DEFAULT_BBOX = [85.815, 20.290, 85.835, 20.305]  # [min_lon, min_lat, max_lon, max_lat]
GRID_SIZE = 3  # 3x3 = 9 sample points; bump up if backend/frontend can handle more


def _grid_points(bbox: list[float], n: int) -> list[tuple[float, float]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    lons = [min_lon + (max_lon - min_lon) * i / (n - 1) for i in range(n)]
    lats = [min_lat + (max_lat - min_lat) * i / (n - 1) for i in range(n)]
    return [(lat, lon) for lat in lats for lon in lons]


def _make_alert(lat: float, lon: float) -> dict:
    weather = get_weather_features(lat, lon)
    sat = get_ndwi_ndvi([lon - 0.005, lat - 0.005, lon + 0.005, lat + 0.005])
    iot = get_mock_iot_reading(lat, lon)

    features = {**weather, **sat, **iot}
    result = predict_risk(features)

    return {
        "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
        "latitude": round(float(lat), 6),
        "longitude": round(float(lon), 6),
        "risk_score": float(result["risk_score"]),
        "risk_level": str(result["risk_level"]),
        "evidence": str(result["evidence"]),
        "status": "UNVERIFIED",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def get_predictions(bbox: list[float] = None, grid_size: int = None) -> list[dict]:
    """
    No required arguments — sensible defaults so backend can call get_predictions() cold.
    Returns a list of alerts, native Python types only, matching the frozen AlertResponse contract.
    """
    bbox = bbox or DEFAULT_BBOX
    grid_size = grid_size or GRID_SIZE

    alerts = []
    for lat, lon in _grid_points(bbox, grid_size):
        try:
            alerts.append(_make_alert(lat, lon))
        except Exception as e:
            # Don't let one bad point (e.g. Sentinel Hub timeout) kill the whole batch
            print(f"[real_ml] skipped point ({lat},{lon}): {e}")
            continue
    return alerts


if __name__ == "__main__":
    import json
    print(json.dumps(get_predictions(), indent=2))