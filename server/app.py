from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from pydantic import BaseModel, conlist
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import joblib
import os
import numpy as np
import pandas as pd
import traceback
import datetime
from dateutil import parser as dtparser
from ultralytics import YOLO
import cv2

try:
    from .grid_index import (lookup_grid_id, is_available as grid_index_available,  # type: ignore
                             lookup_ward_id, is_ward_available, get_grids_in_ward, get_ward_info, get_ward_gdf)  # type: ignore
except Exception:
    # Fallback when running as script
    try:
        from grid_index import (lookup_grid_id, is_available as grid_index_available,  # type: ignore
                               lookup_ward_id, is_ward_available, get_grids_in_ward, get_ward_info, get_ward_gdf)  # type: ignore
    except Exception:
        lookup_grid_id = None  # type: ignore
        grid_index_available = lambda: False  # type: ignore
        lookup_ward_id = None  # type: ignore
        is_ward_available = lambda: False  # type: ignore
        get_grids_in_ward = None  # type: ignore
        get_ward_info = None  # type: ignore
        get_ward_gdf = None  # type: ignore

try:
    from .ward_aggregation import WardAggregator, create_ward_prediction_summary  # type: ignore
except Exception:
    try:
        from ward_aggregation import WardAggregator, create_ward_prediction_summary  # type: ignore
    except Exception:
        WardAggregator = None  # type: ignore
        create_ward_prediction_summary = None  # type: ignore


BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, 'model', 'flood_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'scaler', 'scaler.pkl')
ENCODER_PATH = os.path.join(BASE_DIR, 'encoder', 'label_encoder.pkl')
DATA_PATH = os.path.join(BASE_DIR, 'dataset', 'delhi_flood_dataset_demo.parquet')
_DATA_DF = None


app = FastAPI(title="DelhiFlow - Prediction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=False,  # avoid wildcard + credentials conflict
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount potholes router
try:
    from .potholes import router as potholes_router  # when running as package
except Exception:
    try:
        from potholes import router as potholes_router  # when running as module
    except Exception:
        potholes_router = None

if potholes_router:
    app.include_router(potholes_router, prefix="/potholes", tags=["potholes"])
    print("[ROUTER] Mounted potholes router at /potholes")
else:
    print("[ROUTER] Potholes router NOT mounted")
# ---------------------------------------------------


class GridInput(BaseModel):
    Elevation: float
    Road_Density: float
    Rain_mm: float
    Rain_Past3h: float
    Drain_Water_Level: float
    Soil_Moisture: float
    hour_of_day: int
    month: int
    day_of_week: int


class MultiGridRequest(BaseModel):
    grids: List[GridInput]


class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    hour_of_day: Optional[int] = None
    month: Optional[int] = None
    day_of_week: Optional[int] = None


class LocationTimeRequest(BaseModel):
    # Either provide (latitude, longitude) or a grid_id directly
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    grid_id: Optional[int] = None
    # Timestamp or explicit hour/month/dow
    timestamp: Optional[str] = None  # ISO8601 or any dtparser-compatible string
    hour_of_day: Optional[int] = None
    month: Optional[int] = None
    day_of_week: Optional[int] = None


class WardPredictionRequest(BaseModel):
    """Request model for ward-level flood risk prediction."""
    latitude: float
    longitude: float
    timestamp: Optional[str] = None  # ISO8601 or any dtparser-compatible string
    hour_of_day: Optional[int] = None
    month: Optional[int] = None
    day_of_week: Optional[int] = None
    aggregation_method: Optional[str] = "mean"  # mean, max, median, percentile_75, percentile_90


def load_artifacts():
	"""Load model, scaler and label encoder from disk."""
	try:
		model = joblib.load(MODEL_PATH)
	except Exception:
		model = None
	try:
		scaler = joblib.load(SCALER_PATH)
	except Exception:
		scaler = None
	try:
		le = joblib.load(ENCODER_PATH)
	except Exception:
		le = None
	return model, scaler, le


MODEL, SCALER, LE = load_artifacts()


@app.get("/health")
def health():
	return {"status": "ok", "model_loaded": MODEL is not None}


def transform_and_predict(df_array: np.ndarray):
	"""Expect df_array shape (n, 9) in the same column order as GridInput fields.
	This function scales the continuous features using the saved scaler and returns predictions and probs.
	"""
	if SCALER is None or MODEL is None or LE is None:
		raise RuntimeError("Model artifacts not available on server.")

	# continuous columns indices assuming order: Elevation, Road_Density, Rain_mm, Rain_Past3h, Drain_Water_Level, Soil_Moisture
	cont_idx = [0,1,2,3,4,5]

	cont = df_array[:, cont_idx].astype(float)
	cont_scaled = SCALER.transform(cont)

	# time features cyclical encoding
	hour = df_array[:,6].astype(float)
	month = df_array[:,7].astype(float)
	dow = df_array[:,8].astype(float)

	hour_sin = np.sin(2 * np.pi * hour / 24)
	hour_cos = np.cos(2 * np.pi * hour / 24)
	month_sin = np.sin(2 * np.pi * month / 12)
	month_cos = np.cos(2 * np.pi * month / 12)
	dow_sin = np.sin(2 * np.pi * dow / 7)
	dow_cos = np.cos(2 * np.pi * dow / 7)

	time_feats = np.stack([hour_sin, hour_cos, month_sin, month_cos, dow_sin, dow_cos], axis=1)

	X = np.concatenate([cont_scaled, time_feats], axis=1)

	preds = MODEL.predict(X)
	probs = MODEL.predict_proba(X).max(axis=1)
	labels = LE.inverse_transform(preds)

	results = []
	for p, prob, lab in zip(preds.tolist(), probs.tolist(), labels.tolist()):
		results.append({"class": int(p), "label": str(lab), "confidence": float(round(prob*100,2))})
	return results


@app.post("/prect")
def predict_multi(request: MultiGridRequest):
	"""Predict flood risk for one or more grids.

	Request JSON:
	{
	  "grids": [ {GridInput}, {GridInput}, ... ]
	}

	Response:
	{"results": [{class,label,confidence}, ...]}
	"""
	try:
		if not request.grids:
			raise HTTPException(status_code=400, detail="No grids provided")

		# prepare numpy array
		rows = []
		for g in request.grids:
			rows.append([
				g.Elevation, g.Road_Density, g.Rain_mm, g.Rain_Past3h,
				g.Drain_Water_Level, g.Soil_Moisture, g.hour_of_day, g.month, g.day_of_week
			])
		arr = np.array(rows)

		results = transform_and_predict(arr)
		return {"results": results}
	except HTTPException:
		raise
	except Exception as ex:
		tb = traceback.format_exc()
		raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})

def load_dataset():
    global _DATA_DF
    if _DATA_DF is None:
        if os.path.exists(DATA_PATH):
            try:
                _DATA_DF = pd.read_parquet(DATA_PATH)
            except Exception:
                _DATA_DF = None
        else:
            _DATA_DF = None
    return _DATA_DF


def derive_features_from_location(lat: float, lng: float):
    """Derive environmental features from latitude/longitude.
    
    For now, this uses simplified heuristics based on Delhi's geography.
    In a production system, you'd query actual GIS databases, elevation APIs, etc.
    """
    # Delhi bounds roughly: lat 28.4-28.9, lng 76.8-77.3
    
    # Elevation estimation (Delhi ranges ~200-250m, higher in south/west)
    # Simple linear interpolation based on position
    elevation_base = 200
    if lat < 28.6:  # Southern Delhi tends to be higher
        elevation_base += 20
    if lng < 77.1:  # Western areas slightly higher
        elevation_base += 10
    # Add some variation based on exact coordinates
    elevation = elevation_base + (lat - 28.6) * 50 + (lng - 77.1) * 30
    elevation = max(180, min(250, elevation))  # Clamp to realistic range
    
    # Road density estimation (higher in central/commercial areas)
    # Central Delhi (around 28.6-28.7 lat, 77.1-77.3 lng) has higher road density
    road_density = 0.3  # Base density
    if 28.6 <= lat <= 28.7 and 77.1 <= lng <= 77.3:
        road_density = 0.8  # High density in central areas
    elif 28.55 <= lat <= 28.75 and 77.05 <= lng <= 77.35:
        road_density = 0.6  # Medium density in urban areas
    
    # Rainfall - use seasonal defaults (can be enhanced with weather APIs)
    # Monsoon season (July-September) typically has higher rainfall
    current_month = datetime.datetime.now().month
    if 7 <= current_month <= 9:  # Monsoon
        rain_mm = 15.0
        rain_past3h = 8.0
    elif current_month in [6, 10]:  # Pre/post monsoon
        rain_mm = 8.0
        rain_past3h = 4.0
    else:  # Dry season
        rain_mm = 2.0
        rain_past3h = 1.0
    
    # Drain water level (higher in low-lying areas, during monsoon)
    drain_level = 0.5  # Base level
    if elevation < 210:  # Lower areas tend to have higher drain levels
        drain_level = 1.2
    if 7 <= current_month <= 9:  # Higher during monsoon
        drain_level *= 1.5
    
    # Soil moisture (higher during monsoon, varies with elevation)
    soil_moisture = 0.3  # Base moisture
    if 7 <= current_month <= 9:  # Higher during monsoon
        soil_moisture = 0.7
    elif current_month in [6, 10]:
        soil_moisture = 0.5
    # Lower areas retain more moisture
    if elevation < 210:
        soil_moisture = min(1.0, soil_moisture + 0.2)
    
    return {
        "Elevation": float(elevation),
        "Road_Density": float(road_density),
        "Rain_mm": float(rain_mm),
        "Rain_Past3h": float(rain_past3h),
        "Drain_Water_Level": float(drain_level),
        "Soil_Moisture": float(soil_moisture)
    }


@app.post("/predict_location")
def predict_location(request: LocationRequest):
    """Predict flood risk based on latitude/longitude coordinates.
    
    This endpoint automatically derives environmental features from the coordinates
    and predicts flood risk using the current time or provided time information.
    
    Request JSON:
    {
      "latitude": 28.6139,
      "longitude": 77.2090,
      "hour_of_day": 14,    // optional, defaults to current hour
      "month": 8,           // optional, defaults to current month  
      "day_of_week": 2      // optional, defaults to current day of week
    }
    
    Response:
    {
      "location": {"latitude": 28.6139, "longitude": 77.2090},
      "derived_features": {...},
      "prediction": {"class": 0, "label": "High", "confidence": 85.2}
    }
    """
    try:
        # Validate coordinates (use wider bounds to avoid false negatives near edges of Delhi)
        if not (28.0 <= request.latitude <= 29.5 and 76.0 <= request.longitude <= 78.0):
            # Still allow processing but indicate unusual coordinates
            pass
        
        # Derive environmental features from location
        features = derive_features_from_location(request.latitude, request.longitude)
        
        # Use current time if not provided
        now = datetime.datetime.now()
        hour = request.hour_of_day if request.hour_of_day is not None else now.hour
        month = request.month if request.month is not None else now.month
        day_of_week = request.day_of_week if request.day_of_week is not None else now.weekday()
        
        # Create prediction input
        grid_input = GridInput(
            Elevation=features["Elevation"],
            Road_Density=features["Road_Density"], 
            Rain_mm=features["Rain_mm"],
            Rain_Past3h=features["Rain_Past3h"],
            Drain_Water_Level=features["Drain_Water_Level"],
            Soil_Moisture=features["Soil_Moisture"],
            hour_of_day=hour,
            month=month,
            day_of_week=day_of_week
        )
        
        # Make prediction
        rows = [[
            grid_input.Elevation, grid_input.Road_Density, grid_input.Rain_mm, 
            grid_input.Rain_Past3h, grid_input.Drain_Water_Level, grid_input.Soil_Moisture,
            grid_input.hour_of_day, grid_input.month, grid_input.day_of_week
        ]]
        arr = np.array(rows)
        results = transform_and_predict(arr)
        
        return {
            "location": {
                "latitude": request.latitude,
                "longitude": request.longitude
            },
            "derived_features": features,
            "time_used": {
                "hour_of_day": hour,
                "month": month, 
                "day_of_week": day_of_week
            },
            "prediction": results[0] if results else None
        }
        
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.post("/predict_location_time")
def predict_location_time(payload: LocationTimeRequest):
    """Dataset-driven prediction using location + time to select the correct grid row.

    Flow:
    - If grid_id not provided: use spatial lookup (requires grid_index file) to map (lat,lon)->Grid_ID
    - Parse timestamp or derive hour/month/dow
    - Find dataset row(s) for Grid_ID and the matching hour
    - Build model input from the dataset row and time features
    - Run model and return prediction plus the source row used

    Request JSON examples:
    {"latitude": 28.6139, "longitude": 77.2090, "timestamp": "2025-07-01T14:30:00+05:30"}
    {"grid_id": 123, "hour_of_day": 14, "month": 7, "day_of_week": 2}
    """
    try:
        df = load_dataset()
        if df is None:
            raise HTTPException(status_code=500, detail="Dataset not available on server")

        # Determine grid id
        grid_id = payload.grid_id
        lat = payload.latitude
        lon = payload.longitude

        if grid_id is None:
            if lat is None or lon is None:
                raise HTTPException(status_code=400, detail="Provide either grid_id or latitude+longitude")
            if not (28.0 <= float(lat) <= 29.5 and 76.0 <= float(lon) <= 78.0):
                # Wider bounds than /predict_location to allow lookup near edges
                raise HTTPException(status_code=400, detail="Coordinates out of expected region for Delhi grid")
            if not grid_index_available():
                raise HTTPException(status_code=400, detail="Grid geometry index not available on server for spatial lookup. Provide grid_id directly or add dataset/grid_index.geojson")
            gid = lookup_grid_id(float(lat), float(lon))  # type: ignore
            if gid is None:
                raise HTTPException(status_code=404, detail="No grid cell found for provided coordinates")
            grid_id = gid

        # Parse time info
        hour = payload.hour_of_day
        month = payload.month
        dow = payload.day_of_week
        if payload.timestamp:
            try:
                dt = dtparser.parse(payload.timestamp)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid timestamp format")
            hour = dt.hour
            month = dt.month
            dow = dt.weekday()
        else:
            # fill blanks from now
            now = datetime.datetime.now()
            hour = hour if hour is not None else now.hour
            month = month if month is not None else now.month
            dow = dow if dow is not None else now.weekday()

        # Dataset has an 'Hour' timestamp column per grid; choose the same month and hour
        # We'll match month and hour-of-day; if multiple days exist, take the first for that month.
        df_grid = df[df["Grid_ID"] == int(grid_id)]
        if df_grid.empty:
            raise HTTPException(status_code=404, detail=f"No dataset rows for Grid_ID={grid_id}")

        # Ensure Hour is datetime
        if not np.issubdtype(df_grid["Hour"].dtype, np.datetime64):
            try:
                df_grid = df_grid.assign(Hour=pd.to_datetime(df_grid["Hour"]))
            except Exception:
                pass

        # Filter by month and hour
        df_sel = df_grid[(df_grid["Hour"].dt.month == int(month)) & (df_grid["Hour"].dt.hour == int(hour))]
        if df_sel.empty:
            # Fallback: just first row of this grid
            df_sel = df_grid.head(1)

        row = df_sel.iloc[0]

        # Build input features: prefer dataset values when present; otherwise fallback to simple heuristics
        def val_or_default(name, default):
            v = row.get(name)
            try:
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    return default
                return float(v)
            except Exception:
                return default

        # If lat/lon were provided, use heuristic derivation for elevation/road density when dataset has NaN
        if lat is not None and lon is not None:
            feats_loc = derive_features_from_location(float(lat), float(lon))
        else:
            feats_loc = None

        Elevation = val_or_default("Elevation", feats_loc["Elevation"] if feats_loc else 210.0)
        Road_Density = val_or_default("Road_Density", feats_loc["Road_Density"] if feats_loc else 0.5)
        Rain_mm = val_or_default("Rain_mm", feats_loc["Rain_mm"] if feats_loc else 5.0)
        Rain_Past3h = val_or_default("Rain_Past3h", feats_loc["Rain_Past3h"] if feats_loc else Rain_mm)
        Drain_Water_Level = val_or_default("Drain_Water_Level", feats_loc["Drain_Water_Level"] if feats_loc else 0.8)
        Soil_Moisture = val_or_default("Soil_Moisture", feats_loc["Soil_Moisture"] if feats_loc else 0.4)

        # Build model array and predict
        arr = np.array([[
            Elevation, Road_Density, Rain_mm, Rain_Past3h, Drain_Water_Level, Soil_Moisture,
            int(hour), int(month), int(dow)
        ]])
        results = transform_and_predict(arr)

        return {
            "grid_id": int(grid_id),
            "used_row": {
                "Hour": row["Hour"].isoformat() if hasattr(row["Hour"], "isoformat") else str(row["Hour"]),
                "Elevation": Elevation,
                "Road_Density": Road_Density,
                "Rain_mm": Rain_mm,
                "Rain_Past3h": Rain_Past3h,
                "Drain_Water_Level": Drain_Water_Level,
                "Soil_Moisture": Soil_Moisture,
            },
            "time_used": {"hour_of_day": int(hour), "month": int(month), "day_of_week": int(dow)},
            "prediction": results[0] if results else None,
        }
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})

# --- Pothole detection endpoint ---
# Try to load a dedicated pothole model if available, otherwise reuse YOLO model
POTHOLE_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model', 'potholes.pt')
POTHOLE_MODEL = None
try:
    if os.path.exists(POTHOLE_MODEL_PATH):
        POTHOLE_MODEL = YOLO(POTHOLE_MODEL_PATH)
        print(f"[MODEL] Loaded pothole model from {POTHOLE_MODEL_PATH}")
    else:
        # Fallback to general model if specific pothole model not found
        POTHOLE_MODEL = YOLO(MODEL_PATH)
        print(f"[MODEL] Pothole model not found, falling back to {MODEL_PATH}")
except Exception as e:
    POTHOLE_MODEL = None
    print(f"[MODEL] Failed to load pothole model: {e}")


@app.post('/analyze_issue')
async def analyze_issue(lat: float = Form(None), lon: float = Form(None), file: UploadFile = File(...)):
    """Analyze uploaded image/video for potholes. Returns detection status and provided coordinates.
    - Accepts a multipart/form-data file (image or video)
    - Optional form fields: lat, lon (floats)
    """
    # Validate file type
    content_type = file.content_type
    if not content_type or (not content_type.startswith('image/') and not content_type.startswith('video/')):
        raise HTTPException(status_code=400, detail='Invalid file type. Upload an image or video.')

    if POTHOLE_MODEL is None:
        raise HTTPException(status_code=500, detail='Pothole model not available on server')

    # Read file bytes
    data = await file.read()

    # For images - load using cv2.imdecode
    if content_type.startswith('image/'):
        np_arr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail='Could not decode image')

        # Run inference
        try:
            results = POTHOLE_MODEL(img)
        except Exception as e:
            print(f"[ANALYZE] Model inference failed: {e}")
            raise HTTPException(status_code=500, detail='Model inference failed')

        # Check detections for pothole class
        detections = results[0].boxes
        pothole_detected = False
        pothole_boxes = []
        # Try to detect by name if names are available, otherwise check for class id 0 assumption
        names = results[0].names if hasattr(results[0], 'names') else {}
        for box in detections:
            cls = int(box.cls[0])
            conf = float(box.conf[0]) if hasattr(box, 'conf') else None
            label = names.get(cls, str(cls)) if isinstance(names, dict) else str(cls)
            # Consider 'pothole' label or class id 0 as pothole (fallback)
            if str(label).lower() == 'pothole' or cls == 0:
                pothole_detected = True
                x1, y1, x2, y2 = map(float, box.xyxy[0]) if hasattr(box, 'xyxy') else (0,0,0,0)
                pothole_boxes.append({'bbox': [x1, y1, x2, y2], 'confidence': conf, 'class': cls, 'label': label})

    else:
        # For videos: save temporarily and analyze first frame
        try:
            tmp_path = os.path.join(os.path.dirname(__file__), 'temp_upload')
            os.makedirs(tmp_path, exist_ok=True)
            tmp_file = os.path.join(tmp_path, file.filename)
            with open(tmp_file, 'wb') as f:
                f.write(data)
            cap = cv2.VideoCapture(tmp_file)
            ret, frame = cap.read()
            cap.release()
            os.remove(tmp_file)
            if not ret or frame is None:
                raise HTTPException(status_code=400, detail='Could not read video frame')

            results = POTHOLE_MODEL(frame)
            detections = results[0].boxes
            pothole_detected = False
            pothole_boxes = []
            names = results[0].names if hasattr(results[0], 'names') else {}
            for box in detections:
                cls = int(box.cls[0])
                conf = float(box.conf[0]) if hasattr(box, 'conf') else None
                label = names.get(cls, str(cls)) if isinstance(names, dict) else str(cls)
                if str(label).lower() == 'pothole' or cls == 0:
                    pothole_detected = True
                    x1, y1, x2, y2 = map(float, box.xyxy[0]) if hasattr(box, 'xyxy') else (0,0,0,0)
                    pothole_boxes.append({'bbox': [x1, y1, x2, y2], 'confidence': conf, 'class': cls, 'label': label})

  
        except HTTPException:
            raise
        except Exception as e:
            print(f"[ANALYZE VIDEO] Failed: {e}")
            raise HTTPException(status_code=500, detail='Video analysis failed')


# ========================= WARD-LEVEL FLOOD RISK PREDICTION =======================


@app.post("/predict_ward")
def predict_ward(request: WardPredictionRequest):
    """Predict flood risk at WARD level based on user location.
    
    This endpoint:
    1. Finds the ward containing the user's coordinates
    2. Gets all grids within that ward
    3. Predicts flood risk for each grid
    4. Aggregates predictions to ward-level summary
    
    Request JSON:
    {
      "latitude": 28.6139,
      "longitude": 77.2090,
      "timestamp": "2025-07-01T14:30:00+05:30",  // optional
      "hour_of_day": 14,    // optional
      "month": 8,           // optional
      "day_of_week": 2,     // optional
      "aggregation_method": "mean"  // optional: mean, max, median, percentile_75, percentile_90
    }
    
    Response:
    {
      "Ward_ID": 5,
      "Ward_Name": "Ward_5",
      "Flood_Risk_Score": 0.65,
      "Flood_Risk_Class": "Medium",
      "Flood_Risk_Class_ID": 2,
      "Grid_Count": 12,
      "Risk_Distribution": {"High": 0.25, "Medium": 0.5, "Low": 0.25},
      "location": {"latitude": 28.6139, "longitude": 77.2090},
      "time_used": {"hour_of_day": 14, "month": 7, "day_of_week": 2}
    }
    """
    try:
        # Check if ward features are available
        if not is_ward_available():
            raise HTTPException(
                status_code=400,
                detail="Ward boundaries not available. Run create_ward_boundaries.py first."
            )
        
        # Validate coordinates
        if not (28.0 <= request.latitude <= 29.5 and 76.0 <= request.longitude <= 78.0):
            raise HTTPException(
                status_code=400,
                detail="Coordinates out of expected region for Delhi"
            )
        
        # Find ward containing this location; fallback to nearest ward if outside polygons
        ward_id = lookup_ward_id(request.latitude, request.longitude)  # type: ignore
        lookup_method = "contains"
        if ward_id is None:
            try:
                from .grid_index import lookup_nearest_ward  # type: ignore
            except Exception:
                from grid_index import lookup_nearest_ward  # type: ignore
            ward_id = lookup_nearest_ward(request.latitude, request.longitude)  # type: ignore
            lookup_method = "nearest"
        if ward_id is None:
            raise HTTPException(
                status_code=404,
                detail=f"No ward found for coordinates ({request.latitude}, {request.longitude})"
            )
        
        # Get ward info
        ward_info = get_ward_info(ward_id)  # type: ignore
        ward_name = ward_info.get("Ward_Name") if ward_info else f"Ward_{ward_id}"
        
        # Get all grids in this ward
        grid_ids = get_grids_in_ward(ward_id)  # type: ignore
        
        # Parse time info
        now = datetime.datetime.now()
        if request.timestamp:
            try:
                dt = dtparser.parse(request.timestamp)
                hour = dt.hour
                month = dt.month
                dow = dt.weekday()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid timestamp format")
        else:
            hour = request.hour_of_day if request.hour_of_day is not None else now.hour
            month = request.month if request.month is not None else now.month
            dow = request.day_of_week if request.day_of_week is not None else now.weekday()
        
        # Get predictions for all grids in the ward, or fallback to single-point inference when none are mapped
        df = load_dataset()
        if df is None:
            raise HTTPException(status_code=500, detail="Dataset not available on server")
        
        grid_predictions = {}  # grid_id -> risk_score

        if not grid_ids:
            # Fallback: no grids mapped to this ward, infer risk directly at the given location
            feats_loc = derive_features_from_location(request.latitude, request.longitude)
            arr = np.array([
                [
                    feats_loc["Elevation"],
                    feats_loc["Road_Density"],
                    feats_loc["Rain_mm"],
                    feats_loc["Rain_Past3h"],
                    feats_loc["Drain_Water_Level"],
                    feats_loc["Soil_Moisture"],
                    int(hour),
                    int(month),
                    int(dow),
                ]
            ])
            results = transform_and_predict(arr)
            if results:
                class_id = results[0]["class"]
                score = WardAggregator.class_to_score(class_id)  # type: ignore
                grid_predictions[-1] = score  # synthetic grid id for fallback
        else:
            for grid_id in grid_ids:
                try:
                    # Get dataset rows for this grid
                    df_grid = df[df["Grid_ID"] == int(grid_id)]
                    if df_grid.empty:
                        continue
                    
                    # Ensure Hour is datetime
                    if not np.issubdtype(df_grid["Hour"].dtype, np.datetime64):
                        try:
                            df_grid = df_grid.assign(Hour=pd.to_datetime(df_grid["Hour"]))
                        except Exception:
                            pass
                    
                    # Filter by month and hour
                    df_sel = df_grid[(df_grid["Hour"].dt.month == int(month)) & (df_grid["Hour"].dt.hour == int(hour))]
                    if df_sel.empty:
                        df_sel = df_grid.head(1)
                    
                    row = df_sel.iloc[0]
                    
                    # Extract features
                    def val_or_default(name, default):
                        v = row.get(name)
                        try:
                            if v is None or (isinstance(v, float) and np.isnan(v)):
                                return default
                            return float(v)
                        except Exception:
                            return default
                    
                    # Derive features from location for missing values
                    feats_loc = derive_features_from_location(request.latitude, request.longitude)
                    
                    Elevation = val_or_default("Elevation", feats_loc["Elevation"])
                    Road_Density = val_or_default("Road_Density", feats_loc["Road_Density"])
                    Rain_mm = val_or_default("Rain_mm", feats_loc["Rain_mm"])
                    Rain_Past3h = val_or_default("Rain_Past3h", feats_loc["Rain_Past3h"])
                    Drain_Water_Level = val_or_default("Drain_Water_Level", feats_loc["Drain_Water_Level"])
                    Soil_Moisture = val_or_default("Soil_Moisture", feats_loc["Soil_Moisture"])
                    
                    # Predict
                    arr = np.array([
                        [
                            Elevation,
                            Road_Density,
                            Rain_mm,
                            Rain_Past3h,
                            Drain_Water_Level,
                            Soil_Moisture,
                            int(hour),
                            int(month),
                            int(dow),
                        ]
                    ])
                    
                    results = transform_and_predict(arr)
                    if results:
                        # Convert class prediction to normalized score
                        # class 0=High (0.8), 1=Low (0.2), 2=Medium (0.5)
                        class_id = results[0]["class"]
                        score = WardAggregator.class_to_score(class_id)  # type: ignore
                        grid_predictions[grid_id] = score
                
                except Exception as e:
                    print(f"[PREDICT WARD] Error predicting grid {grid_id}: {e}")
                    continue
        
        # Aggregate predictions
        if not grid_predictions:
            raise HTTPException(
                status_code=500,
                detail="Could not generate predictions for any grid in the ward"
            )
        
        aggregation_method = request.aggregation_method or "mean"
        summary = create_ward_prediction_summary(  # type: ignore
            ward_id=ward_id,
            ward_name=ward_name,
            grid_predictions=grid_predictions,
            aggregation_method=aggregation_method
        )
        
        # Add location and time info
        summary["location"] = {
            "latitude": request.latitude,
            "longitude": request.longitude
        }
        summary["time_used"] = {
            "hour_of_day": int(hour),
            "month": int(month),
            "day_of_week": int(dow)
        }
        summary["aggregation_method"] = aggregation_method
        summary["ward_lookup"] = lookup_method
        if not grid_ids:
            summary["fallback"] = "single_point"
        
        return summary
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"[PREDICT WARD] Error: {tb}")
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.get("/ward_info/{ward_id}")
def get_ward_details(ward_id: int):
    """Get information about a specific ward.
    
    Response:
    {
      "Ward_ID": 5,
      "Ward_Name": "Ward_5",
      "bounds": {
        "min_lon": 77.05,
        "min_lat": 28.6,
        "max_lon": 77.15,
        "max_lat": 28.7
      },
      "grid_count": 12
    }
    """
    try:
        if not is_ward_available():
            raise HTTPException(
                status_code=400,
                detail="Ward boundaries not available"
            )
        
        ward_info = get_ward_info(ward_id)  # type: ignore
        if ward_info is None:
            raise HTTPException(
                status_code=404,
                detail=f"Ward {ward_id} not found"
            )
        
        # Get grid count
        grid_ids = get_grids_in_ward(ward_id)  # type: ignore
        ward_info["grid_count"] = len(grid_ids)
        
        return ward_info
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.post("/predict_ward_batch")
def predict_ward_batch(requests_list: List[WardPredictionRequest]):
    """Predict flood risk for multiple locations at once.
    
    Request JSON:
    [
      {"latitude": 28.6139, "longitude": 77.2090, ...},
      {"latitude": 28.5, "longitude": 77.1, ...}
    ]
    
    Response:
    {
      "results": [
        {"Ward_ID": 5, "Flood_Risk_Class": "Medium", ...},
        {"Ward_ID": 3, "Flood_Risk_Class": "High", ...}
      ],
      "processed": 2,
      "failed": 0
    }
    """
    try:
        results = []
        failed = 0
        
        for req in requests_list:
            try:
                # Reuse single prediction logic
                result = predict_ward(req)
                results.append(result)
            except HTTPException as he:
                failed += 1
                results.append({
                    "error": he.detail,
                    "location": {"latitude": req.latitude, "longitude": req.longitude}
                })
            except Exception as e:
                failed += 1
                results.append({
                    "error": str(e),
                    "location": {"latitude": req.latitude, "longitude": req.longitude}
                })
        
        return {
            "results": results,
            "processed": len(requests_list) - failed,
            "failed": failed,
            "total": len(requests_list)
        }
    
    except Exception as ex:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.get("/wards/geojson")
def get_wards_geojson():
    """Get all ward boundaries as GeoJSON for map visualization.
    
    Returns:
        GeoJSON FeatureCollection with all wards including their properties.
    """
    try:
        if not is_ward_available():
            raise HTTPException(
                status_code=404,
                detail="Ward boundaries not available"
            )
        
        # Import geopandas here to avoid dependency if not needed
        try:
            import geopandas as gpd
            import json
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="geopandas is required for GeoJSON export"
            )
        
        # Get ward GeoDataFrame
        ward_gdf = get_ward_gdf()  # type: ignore
        
        # Convert to GeoJSON
        geojson_str = ward_gdf.to_json()
        geojson_dict = json.loads(geojson_str)
        
        # Ensure properties include Ward_ID and Ward_Name (with correct ward names, not district names)
        # Always use dynamic extraction to get correct ward names from GeoJSON properties
        for feature in geojson_dict.get("features", []):
            props = feature.get("properties", {})
            # Ensure Ward_ID exists
            if "Ward_ID" not in props:
                # Try to find it in alternative field names
                for alt_id in ["Ward_No", "ward_no", "WNo_SEC"]:
                    if alt_id in props:
                        props["Ward_ID"] = props[alt_id]
                        break
            
            # Always use dynamic extraction to get correct ward name (avoid district-prefixed names)
            ward_id = props.get("Ward_ID")
            if ward_id:
                try:
                    ward_info = get_ward_info(int(ward_id))  # type: ignore
                    if ward_info and ward_info.get("Ward_Name"):
                        # Use the dynamically extracted name (which avoids district prefixes)
                        props["Ward_Name"] = ward_info["Ward_Name"]
                    elif "Ward_Name" not in props or not props.get("Ward_Name"):
                        # Fallback: ensure we have at least "Ward {ID}" format
                        props["Ward_Name"] = f"Ward {ward_id}"
                except Exception as e:
                    # Fallback if extraction fails
                    if "Ward_Name" not in props or not props.get("Ward_Name"):
                        props["Ward_Name"] = f"Ward {ward_id}" if ward_id else "Unknown Ward"
            elif "Ward_Name" not in props or not props.get("Ward_Name"):
                # No ward ID available, use unknown
                props["Ward_Name"] = "Unknown Ward"
        
        return geojson_dict
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"[ERROR] Failed to get wards GeoJSON: {tb}")
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.get("/heatmap/ward_risk")
def get_ward_risk_heatmap(
    timestamp: Optional[str] = None,
    hour_of_day: Optional[int] = None,
    month: Optional[int] = None,
    day_of_week: Optional[int] = None,
    aggregation_method: str = "mean"
):
    """Generate flood risk heatmap data for all wards.
    
    Processes all wards from GeoJSON, computes centroids, runs predictions,
    and returns heatmap data points in [latitude, longitude, risk_intensity] format.
    
    Query Parameters:
        timestamp: ISO8601 timestamp (optional)
        hour_of_day: Hour (0-23, optional)
        month: Month (1-12, optional)
        day_of_week: Day of week (0-6, optional)
        aggregation_method: Aggregation method for ward-level predictions (default: "mean")
    
    Returns:
        {
            "heatmap_data": [[lat, lng, intensity], ...],
            "total_wards": int,
            "processed_wards": int,
            "time_used": {...},
            "metadata": {...}
        }
    """
    try:
        if not is_ward_available():
            raise HTTPException(
                status_code=404,
                detail="Ward boundaries not available"
            )
        
        # Parse time info
        now = datetime.datetime.now()
        if timestamp:
            try:
                dt = dtparser.parse(timestamp)
                hour = dt.hour
                month_val = dt.month
                dow = dt.weekday()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid timestamp format")
        else:
            hour = hour_of_day if hour_of_day is not None else now.hour
            month_val = month if month is not None else now.month
            dow = day_of_week if day_of_week is not None else now.weekday()
        
        # Get all wards
        ward_gdf = get_ward_gdf()  # type: ignore
        df = load_dataset()
        if df is None:
            raise HTTPException(status_code=500, detail="Dataset not available on server")
        
        heatmap_data = []
        processed_count = 0
        error_count = 0
        
        # Process each ward
        for idx, row in ward_gdf.iterrows():
            try:
                ward_id = int(row.get('Ward_ID') or row.get('Ward_No', 0))
                if ward_id == 0:
                    continue
                
                # Compute centroid of the ward polygon
                geometry = row.geometry
                centroid = geometry.centroid
                lat = float(centroid.y)
                lon = float(centroid.x)
                
                # Get all grids in this ward
                grid_ids = get_grids_in_ward(ward_id)  # type: ignore
                grid_predictions = {}
                
                if not grid_ids:
                    # Fallback: predict directly at centroid
                    feats_loc = derive_features_from_location(lat, lon)
                    arr = np.array([[
                        feats_loc["Elevation"],
                        feats_loc["Road_Density"],
                        feats_loc["Rain_mm"],
                        feats_loc["Rain_Past3h"],
                        feats_loc["Drain_Water_Level"],
                        feats_loc["Soil_Moisture"],
                        int(hour),
                        int(month_val),
                        int(dow),
                    ]])
                    results = transform_and_predict(arr)
                    if results:
                        class_id = results[0]["class"]
                        score = WardAggregator.class_to_score(class_id)  # type: ignore
                        grid_predictions[-1] = score
                else:
                    # Predict for all grids in ward
                    for grid_id in grid_ids:
                        try:
                            df_grid = df[df["Grid_ID"] == int(grid_id)]
                            if df_grid.empty:
                                continue
                            
                            # Ensure Hour is datetime
                            if not np.issubdtype(df_grid["Hour"].dtype, np.datetime64):
                                try:
                                    df_grid = df_grid.assign(Hour=pd.to_datetime(df_grid["Hour"]))
                                except Exception:
                                    pass
                            
                            # Filter by month and hour
                            df_sel = df_grid[(df_grid["Hour"].dt.month == int(month_val)) & (df_grid["Hour"].dt.hour == int(hour))]
                            if df_sel.empty:
                                df_sel = df_grid.head(1)
                            
                            grid_row = df_sel.iloc[0]
                            
                            def val_or_default(name, default):
                                v = grid_row.get(name)
                                try:
                                    if v is None or (isinstance(v, float) and np.isnan(v)):
                                        return default
                                    return float(v)
                                except Exception:
                                    return default
                            
                            feats_loc = derive_features_from_location(lat, lon)
                            
                            Elevation = val_or_default("Elevation", feats_loc["Elevation"])
                            Road_Density = val_or_default("Road_Density", feats_loc["Road_Density"])
                            Rain_mm = val_or_default("Rain_mm", feats_loc["Rain_mm"])
                            Rain_Past3h = val_or_default("Rain_Past3h", feats_loc["Rain_Past3h"])
                            Drain_Water_Level = val_or_default("Drain_Water_Level", feats_loc["Drain_Water_Level"])
                            Soil_Moisture = val_or_default("Soil_Moisture", feats_loc["Soil_Moisture"])
                            
                            arr = np.array([[
                                Elevation,
                                Road_Density,
                                Rain_mm,
                                Rain_Past3h,
                                Drain_Water_Level,
                                Soil_Moisture,
                                int(hour),
                                int(month_val),
                                int(dow),
                            ]])
                            
                            results = transform_and_predict(arr)
                            if results:
                                class_id = results[0]["class"]
                                score = WardAggregator.class_to_score(class_id)  # type: ignore
                                grid_predictions[grid_id] = score
                        
                        except Exception as e:
                            print(f"[HEATMAP] Error predicting grid {grid_id} in ward {ward_id}: {e}")
                            continue
                
                # Aggregate to ward-level risk score
                if grid_predictions:
                    aggregator = WardAggregator()
                    risk_score = aggregator.aggregate_predictions(
                        grid_predictions,
                        method=aggregation_method
                    )
                    # Add to heatmap data: [latitude, longitude, intensity]
                    # Intensity is normalized 0-1, where 1 = highest risk
                    heatmap_data.append([lat, lon, float(risk_score)])
                    processed_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                print(f"[HEATMAP] Error processing ward {idx}: {e}")
                error_count += 1
                continue
        
        if not heatmap_data:
            raise HTTPException(
                status_code=500,
                detail="Could not generate heatmap data for any ward"
            )
        
        return {
            "heatmap_data": heatmap_data,
            "total_wards": len(ward_gdf),
            "processed_wards": processed_count,
            "error_count": error_count,
            "time_used": {
                "hour_of_day": int(hour),
                "month": int(month_val),
                "day_of_week": int(dow)
            },
            "aggregation_method": aggregation_method,
            "metadata": {
                "intensity_range": {
                    "min": float(min(point[2] for point in heatmap_data)),
                    "max": float(max(point[2] for point in heatmap_data)),
                    "mean": float(np.mean([point[2] for point in heatmap_data]))
                }
            }
        }
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"[HEATMAP] Error: {tb}")
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.get("/wards/{ward_id}/geojson")
def get_ward_geojson(ward_id: int):
    """Get a specific ward's geometry as GeoJSON.
    
    Args:
        ward_id: The Ward_ID to retrieve
        
    Returns:
        GeoJSON Feature for the specific ward.
    """
    try:
        if not is_ward_available():
            raise HTTPException(
                status_code=404,
                detail="Ward boundaries not available"
            )
        
        try:
            import geopandas as gpd
            import json
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="geopandas is required for GeoJSON export"
            )
        
        ward_gdf = get_ward_gdf()  # type: ignore
        ward_rows = ward_gdf[ward_gdf['Ward_ID'] == ward_id]
        
        if ward_rows.empty:
            raise HTTPException(
                status_code=404,
                detail=f"Ward {ward_id} not found"
            )
        
        # Convert single ward to GeoJSON
        geojson_str = ward_rows.to_json()
        geojson_dict = json.loads(geojson_str)
        
        # Ensure properties are set correctly (with correct ward names, not district names)
        for feature in geojson_dict.get("features", []):
            props = feature.get("properties", {})
            # Always use dynamic extraction to get correct ward name (avoid district-prefixed names)
            ward_info = get_ward_info(ward_id)  # type: ignore
            if ward_info and ward_info.get("Ward_Name"):
                # Use the dynamically extracted name (which avoids district prefixes)
                props["Ward_Name"] = ward_info["Ward_Name"]
            elif "Ward_Name" not in props or not props.get("Ward_Name"):
                # Fallback: ensure we have at least "Ward {ID}" format
                props["Ward_Name"] = f"Ward {ward_id}"
        
        return geojson_dict
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})
