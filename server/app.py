from fastapi import FastAPI, HTTPException
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

try:
    from .grid_index import lookup_grid_id, is_available as grid_index_available  # type: ignore
except Exception:
    # Fallback when running as script
    try:
        from grid_index import lookup_grid_id, is_available as grid_index_available  # type: ignore
    except Exception:
        lookup_grid_id = None  # type: ignore
        grid_index_available = lambda: False  # type: ignore


BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, 'model', 'flood_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'scaler', 'scaler.pkl')
ENCODER_PATH = os.path.join(BASE_DIR, 'encoder', 'label_encoder.pkl')
DATA_PATH = os.path.join(BASE_DIR, 'dataset', 'delhi_flood_dataset_demo.parquet')
_DATA_DF = None


app = FastAPI(title="DelhiFlow - Prediction API")

# Allow requests from the frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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