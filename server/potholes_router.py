from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
from pothole_service import report_from_citizen, report_from_iot, get_all_for_map

router = APIRouter()


@router.post("/potholes/report")
async def pothole_report(file: UploadFile = File(...), lat: Optional[float] = Form(None), lon: Optional[float] = Form(None)):
    """Citizen upload endpoint.
    Expects multipart/form-data with `file` (image) and `lat`, `lon` (browser GPS).
    Returns 400 with a clear message if lat/lon are missing instead of a 422 validation error.
    """
    # Validate lat/lon presence and type
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Latitude/longitude missing. Please enable location and retry.")
    try:
        browser_lat = float(lat)
        browser_lon = float(lon)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lat/lon provided")

    # Read file bytes
    data = await file.read()

    result = report_from_citizen(data, browser_lat, browser_lon)
    return result


@router.post("/potholes/iot")
async def pothole_iot_report(lat: float = Form(...), lon: float = Form(...), intensity: float = Form(0.5), vehicleId: str = Form("unknown")):
    """IoT device endpoint for reporting potholes without image validation.
    Used as fallback when EXIF validation fails on citizen uploads.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        intensity_f = float(intensity) if intensity else 0.5
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid lat/lon/intensity provided")
    
    result = report_from_iot(lat_f, lon_f, intensity_f, vehicleId)
    return result


@router.get("/potholes/map")
async def potholes_map():
    """Return all grid records for map display."""
    return get_all_for_map()