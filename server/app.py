from fastapi import FastAPI, HTTPException, Form, File, UploadFile
from pydantic import BaseModel, conlist
from typing import List, Optional, Dict
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
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from .grid_index import (lookup_grid_id, is_available as grid_index_available,  # type: ignore
                             lookup_ward_id, is_ward_available, get_grids_in_ward, get_ward_info, get_ward_gdf, search_ward_by_name)  # type: ignore
except Exception:
    # Fallback when running as script
    try:
        from grid_index import (lookup_grid_id, is_available as grid_index_available,  # type: ignore
                               lookup_ward_id, is_ward_available, get_grids_in_ward, get_ward_info, get_ward_gdf, search_ward_by_name)  # type: ignore
    except Exception:
        lookup_grid_id = None  # type: ignore
        grid_index_available = lambda: False  # type: ignore
        lookup_ward_id = None  # type: ignore
        is_ward_available = lambda: False  # type: ignore
        get_grids_in_ward = None  # type: ignore
        get_ward_info = None  # type: ignore
        get_ward_gdf = None  # type: ignore
        search_ward_by_name = None  # type: ignore

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
	Matches the training pipeline exactly: uses DataFrame with feature names to avoid sklearn warnings.
	"""
	if SCALER is None or MODEL is None or LE is None:
		raise RuntimeError("Model artifacts not available on server.")

	# Create DataFrame with input feature names matching the original data structure
	input_feature_names = [
		'Elevation', 'Road_Density', 'Rain_mm', 'Rain_Past3h',
		'Drain_Water_Level', 'Soil_Moisture', 'hour_of_day', 'month', 'day_of_week'
	]
	df = pd.DataFrame(df_array, columns=input_feature_names)

	# Scale continuous features - use DataFrame to maintain feature names
	continuous_features = [
		'Elevation', 'Road_Density', 'Rain_mm', 'Rain_Past3h',
		'Drain_Water_Level', 'Soil_Moisture'
	]
	df_scaled = pd.DataFrame(
		SCALER.transform(df[continuous_features]),
		columns=continuous_features
	)

	# Create cyclical time features - matching training pipeline exactly
	df_scaled['hour_sin'] = np.sin(2 * np.pi * df['hour_of_day'] / 24)
	df_scaled['hour_cos'] = np.cos(2 * np.pi * df['hour_of_day'] / 24)
	df_scaled['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
	df_scaled['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
	df_scaled['dow_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
	df_scaled['dow_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

	# Create final feature DataFrame matching training: scaled continuous + cyclical time
	# Order: Elevation, Road_Density, Rain_mm, Rain_Past3h, Drain_Water_Level, Soil_Moisture,
	#        hour_sin, hour_cos, month_sin, month_cos, dow_sin, dow_cos
	X_final = df_scaled[continuous_features + ['hour_sin', 'hour_cos', 'month_sin', 'month_cos', 'dow_sin', 'dow_cos']]

	# Predict using DataFrame (has feature names) - this eliminates sklearn warnings
	preds = MODEL.predict(X_final)
	proba_matrix = MODEL.predict_proba(X_final)
	labels = LE.inverse_transform(preds)

	results = []
	for i, (pred_class, label) in enumerate(zip(preds.tolist(), labels.tolist())):
		# Get probability of the PREDICTED class (more accurate than using max)
		# This ensures confidence reflects the actual predicted class probability
		class_prob = proba_matrix[i, pred_class]
		results.append({
			"class": int(pred_class),
			"label": str(label),
			"confidence": float(round(class_prob * 100, 2))
		})
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
    
    Uses dataset statistics when available to generate more realistic feature values
    that match the training data distribution. Falls back to Delhi-specific heuristics
    if dataset is not loaded.
    """
    # Try to load dataset statistics for better defaults
    df = load_dataset()
    
    # Delhi bounds roughly: lat 28.4-28.9, lng 76.8-77.3
    # Elevation estimation - use dataset statistics if available
    if df is not None and not df.empty and 'Elevation' in df.columns:
        elevation_mean = float(df['Elevation'].mean())
        elevation_std = float(df['Elevation'].std())
        elevation_min = float(df['Elevation'].min())
        elevation_max = float(df['Elevation'].max())
    else:
        # Fallback to Delhi-specific defaults
        elevation_mean = 210.0
        elevation_std = 15.0
        elevation_min = 180.0
        elevation_max = 250.0
    
    # Spatial variation: Delhi - higher in south/west
    elevation_base = elevation_mean
    if lat < 28.6:  # Southern Delhi tends to be higher
        elevation_base += 10
    if lng < 77.1:  # Western areas slightly higher
        elevation_base += 5
    # Add variation based on exact coordinates (within realistic range)
    elevation_variation = (lat - 28.6) * 30 + (lng - 77.1) * 20
    elevation = elevation_base + elevation_variation
    elevation = max(elevation_min, min(elevation_max, elevation))
    
    # Road density - use dataset statistics if available
    if df is not None and not df.empty and 'Road_Density' in df.columns:
        road_density_mean = float(df['Road_Density'].mean())
        road_density_std = float(df['Road_Density'].std())
        road_density_base = road_density_mean
    else:
        road_density_base = 0.5
        road_density_std = 0.2
    
    # Spatial variation: Central Delhi has higher road density
    road_density = road_density_base
    if 28.6 <= lat <= 28.7 and 77.1 <= lng <= 77.3:
        road_density = min(1.0, road_density_base + 0.3)  # High density in central areas
    elif 28.55 <= lat <= 28.75 and 77.05 <= lng <= 77.35:
        road_density = min(1.0, road_density_base + 0.15)  # Medium density in urban areas
    else:
        road_density = max(0.1, road_density_base - 0.1)  # Lower in outskirts
    road_density = max(0.1, min(1.0, road_density))
    
    # Rainfall - use dataset statistics if available, otherwise seasonal defaults
    current_month = datetime.datetime.now().month
    if df is not None and not df.empty and 'Rain_mm' in df.columns and 'Hour' in df.columns:
        try:
            # Ensure Hour column is datetime type
            df_hour = df.copy()
            if not pd.api.types.is_datetime64_any_dtype(df_hour['Hour']):
                df_hour['Hour'] = pd.to_datetime(df_hour['Hour'], errors='coerce')
            # Use monthly average from dataset if available
            monthly_rain = df_hour[df_hour['Hour'].dt.month == current_month]['Rain_mm']
            if not monthly_rain.empty and monthly_rain.notna().any():
                rain_mm = float(monthly_rain.mean())
                rain_past3h = float(monthly_rain.mean() * 0.5) if rain_mm > 0 else 0.0
            else:
                raise ValueError("No monthly rain data")
        except (ValueError, AttributeError, KeyError):
            # Fallback to seasonal defaults
            if 7 <= current_month <= 9:  # Monsoon
                rain_mm = 15.0
                rain_past3h = 8.0
            elif current_month in [6, 10]:  # Pre/post monsoon
                rain_mm = 8.0
                rain_past3h = 4.0
            else:  # Dry season
                rain_mm = 2.0
                rain_past3h = 1.0
    else:
        # Seasonal defaults for Delhi
        if 7 <= current_month <= 9:  # Monsoon (July-September)
            rain_mm = 15.0
            rain_past3h = 8.0
        elif current_month in [6, 10]:  # Pre/post monsoon
            rain_mm = 8.0
            rain_past3h = 4.0
        else:  # Dry season
            rain_mm = 2.0
            rain_past3h = 1.0
    
    # Drain water level - use dataset statistics if available
    if df is not None and not df.empty and 'Drain_Water_Level' in df.columns:
        drain_level_mean = float(df['Drain_Water_Level'].mean())
        drain_level_base = drain_level_mean
    else:
        drain_level_base = 0.5
    
    drain_level = drain_level_base
    if elevation < elevation_mean:  # Lower areas tend to have higher drain levels
        drain_level = min(2.5, drain_level_base * 1.5)
    if 7 <= current_month <= 9:  # Higher during monsoon
        drain_level = min(2.5, drain_level * 1.5)
    drain_level = max(0.0, drain_level)
    
    # Soil moisture - use dataset statistics if available
    if df is not None and not df.empty and 'Soil_Moisture' in df.columns:
        soil_moisture_mean = float(df['Soil_Moisture'].mean())
        soil_moisture_base = soil_moisture_mean
    else:
        soil_moisture_base = 0.3
    
    soil_moisture = soil_moisture_base
    if 7 <= current_month <= 9:  # Higher during monsoon
        soil_moisture = min(1.0, soil_moisture_base + 0.3)
    elif current_month in [6, 10]:
        soil_moisture = min(1.0, soil_moisture_base + 0.15)
    # Lower areas retain more moisture
    if elevation < elevation_mean:
        soil_moisture = min(1.0, soil_moisture + 0.15)
    soil_moisture = max(0.0, min(1.0, soil_moisture))
    
    return {
        "Elevation": float(elevation),
        "Road_Density": float(road_density),
        "Rain_mm": float(max(0.0, rain_mm)),
        "Rain_Past3h": float(max(0.0, rain_past3h)),
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


@app.post("/api/location/risk")
def location_risk(request: LocationRequest):
    """Get flood risk score for a specific location.
    
    This endpoint uses the trained model to predict flood risk at a given coordinate.
    It derives environmental features from the location and returns an authentic risk score.
    
    Request JSON:
    {
      "latitude": 28.6139,
      "longitude": 77.2090
    }
    
    Response:
    {
      "latitude": 28.6139,
      "longitude": 77.2090,
      "flood_risk": 0.75,           // Risk score 0-1
      "flood_risk_class": "High",   // "Low", "Medium", or "High"
      "confidence": 82.5
    }
    """
    try:
        # Derive environmental features from location
        features = derive_features_from_location(request.latitude, request.longitude)
        
        # Use current time
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
        arr = np.array([[
            grid_input.Elevation, grid_input.Road_Density, grid_input.Rain_mm, 
            grid_input.Rain_Past3h, grid_input.Drain_Water_Level, grid_input.Soil_Moisture,
            grid_input.hour_of_day, grid_input.month, grid_input.day_of_week
        ]])
        results = transform_and_predict(arr)
        pred = results[0] if results else None
        
        if not pred:
            raise HTTPException(status_code=500, detail="Prediction failed")
        
        # Convert prediction class to risk score and class name
        # Model classes: 0=High, 1=Medium, 2=Low (based on typical flood model)
        # But let's use the confidence as our risk score
        risk_class_map = {0: "High", 1: "Medium", 2: "Low"}
        class_id = pred["class"]
        risk_score = pred["confidence"] / 100.0  # Convert percentage to 0-1 scale
        
        # For High risk: score is high (0.7-1.0)
        # For Medium risk: score is medium (0.3-0.7)
        # For Low risk: score is low (0.0-0.3)
        if class_id == 0:  # High
            risk_score = 0.7 + (risk_score * 0.3)  # 0.7-1.0
        elif class_id == 1:  # Medium
            risk_score = 0.3 + (risk_score * 0.4)  # 0.3-0.7
        else:  # Low
            risk_score = risk_score * 0.3  # 0.0-0.3
        
        return {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "flood_risk": round(risk_score, 3),
            "flood_risk_class": risk_class_map.get(class_id, "Unknown"),
            "confidence": pred["confidence"]
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
    import logging
    logger = logging.getLogger("uvicorn")
    
    try:
        logger.info(f"[BATCH] Received batch prediction request with {len(requests_list)} locations")
        results = []
        failed = 0
        
        for idx, req in enumerate(requests_list):
            try:
                # Reuse single prediction logic
                result = predict_ward(req)
                results.append(result)
                if (idx + 1) % 10 == 0 or idx == 0:
                    logger.info(f"[BATCH] Processed {idx + 1}/{len(requests_list)} predictions")
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
                        if WardAggregator is not None:
                            score = WardAggregator.class_to_score(class_id)  # type: ignore
                        else:
                            # Fallback: convert class to score manually (0=High=0.8, 1=Low=0.2, 2=Medium=0.5)
                            score = 0.8 if class_id == 0 else (0.2 if class_id == 1 else 0.5)
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
                                if WardAggregator is not None:
                                    score = WardAggregator.class_to_score(class_id)  # type: ignore
                                else:
                                    # Fallback: convert class to score manually
                                    score = 0.8 if class_id == 0 else (0.2 if class_id == 1 else 0.5)
                                grid_predictions[grid_id] = score
                        
                        except Exception as e:
                            print(f"[HEATMAP] Error predicting grid {grid_id} in ward {ward_id}: {e}")
                            continue
                
                # Aggregate to ward-level risk score
                if grid_predictions:
                    if WardAggregator is not None:
                        aggregator = WardAggregator()
                        risk_score = aggregator.aggregate_predictions(
                            grid_predictions,
                            method=aggregation_method
                        )
                    else:
                        # Fallback: use mean of scores
                        scores = list(grid_predictions.values())
                        risk_score = float(np.mean(scores)) if scores else 0.5
                    # Add to heatmap data: [latitude, longitude, intensity]
                    # Intensity is normalized 0-1, where 1 = highest risk
                    heatmap_data.append([lat, lon, float(risk_score)])
                    processed_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                print(f"[HEATMAP] Error processing ward {idx}: {e}")
                traceback.print_exc()
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


# ========================= CHATBOT ENDPOINT WITH GROK API =======================

class ChatRequest(BaseModel):
    """Request model for chatbot queries."""
    message: str
    ward_name: Optional[str] = None


def get_ward_centroid(ward_id: int):
    """Get the centroid coordinates of a ward."""
    try:
        ward_gdf = get_ward_gdf()  # type: ignore
        ward_rows = ward_gdf[ward_gdf['Ward_ID'] == ward_id]
        if ward_rows.empty:
            return None
        row = ward_rows.iloc[0]
        centroid = row.geometry.centroid
        return {
            'latitude': float(centroid.y),
            'longitude': float(centroid.x)
        }
    except Exception as e:
        print(f"[ERROR] Failed to get ward centroid for {ward_id}: {e}")
        return None


def _predict_ward_internal(latitude: float, longitude: float, aggregation_method: str = "mean"):
    """Internal helper function to predict ward flood risk without HTTP endpoint overhead.
    
    This is a refactored version of predict_ward endpoint logic, used by the chat endpoint.
    """
    try:
        if not is_ward_available():
            return None
        
        # Find ward containing this location
        ward_id = lookup_ward_id(latitude, longitude)  # type: ignore
        if ward_id is None:
            try:
                from .grid_index import lookup_nearest_ward  # type: ignore
            except Exception:
                from grid_index import lookup_nearest_ward  # type: ignore
            ward_id = lookup_nearest_ward(latitude, longitude)  # type: ignore
        if ward_id is None:
            return None
        
        # Get ward info
        ward_info = get_ward_info(ward_id)  # type: ignore
        ward_name = ward_info.get("Ward_Name") if ward_info else f"Ward_{ward_id}"
        
        # Get all grids in this ward
        grid_ids = get_grids_in_ward(ward_id)  # type: ignore
        
        # Use current time
        now = datetime.datetime.now()
        hour = now.hour
        month = now.month
        dow = now.weekday()
        
        # Get predictions for all grids in the ward
        df = load_dataset()
        if df is None:
            return None
        
        grid_predictions = {}
        
        if not grid_ids:
            # Fallback: no grids mapped, infer risk directly at the given location
            feats_loc = derive_features_from_location(latitude, longitude)
            arr = np.array([[
                feats_loc["Elevation"],
                feats_loc["Road_Density"],
                feats_loc["Rain_mm"],
                feats_loc["Rain_Past3h"],
                feats_loc["Drain_Water_Level"],
                feats_loc["Soil_Moisture"],
                int(hour),
                int(month),
                int(dow),
            ]])
            results = transform_and_predict(arr)
            if results:
                class_id = results[0]["class"]
                if WardAggregator is not None:
                    score = WardAggregator.class_to_score(class_id)  # type: ignore
                else:
                    # Fallback: convert class to score manually (0=High=0.8, 1=Low=0.2, 2=Medium=0.5)
                    score = 0.8 if class_id == 0 else (0.2 if class_id == 1 else 0.5)
                grid_predictions[-1] = score
        else:
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
                    df_sel = df_grid[(df_grid["Hour"].dt.month == int(month)) & (df_grid["Hour"].dt.hour == int(hour))]
                    if df_sel.empty:
                        df_sel = df_grid.head(1)
                    
                    row = df_sel.iloc[0]
                    
                    def val_or_default(name, default):
                        v = row.get(name)
                        try:
                            if v is None or (isinstance(v, float) and np.isnan(v)):
                                return default
                            return float(v)
                        except Exception:
                            return default
                    
                    feats_loc = derive_features_from_location(latitude, longitude)
                    
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
                        int(month),
                        int(dow),
                    ]])
                    
                    results = transform_and_predict(arr)
                    if results:
                        class_id = results[0]["class"]
                        if WardAggregator is not None:
                            score = WardAggregator.class_to_score(class_id)  # type: ignore
                        else:
                            # Fallback: convert class to score manually (0=High=0.8, 1=Low=0.2, 2=Medium=0.5)
                            score = 0.8 if class_id == 0 else (0.2 if class_id == 1 else 0.5)
                        grid_predictions[grid_id] = score
                
                except Exception as e:
                    print(f"[CHAT] Error predicting grid {grid_id}: {e}")
                    traceback.print_exc()
                    continue
        
        # If no grid predictions, use fallback single-point prediction at centroid
        if not grid_predictions:
            print(f"[CHAT] No grid predictions found, using fallback single-point prediction at centroid")
            feats_loc = derive_features_from_location(latitude, longitude)
            arr = np.array([[
                feats_loc["Elevation"],
                feats_loc["Road_Density"],
                feats_loc["Rain_mm"],
                feats_loc["Rain_Past3h"],
                feats_loc["Drain_Water_Level"],
                feats_loc["Soil_Moisture"],
                int(hour),
                int(month),
                int(dow),
            ]])
            results = transform_and_predict(arr)
            if results:
                class_id = results[0]["class"]
                if WardAggregator is not None:
                    score = WardAggregator.class_to_score(class_id)  # type: ignore
                else:
                    score = 0.8 if class_id == 0 else (0.2 if class_id == 1 else 0.5)
                grid_predictions[-1] = score
            else:
                # Last resort: use default medium risk
                grid_predictions[-1] = 0.5
        
        # Aggregate predictions
        if create_ward_prediction_summary is not None:
            summary = create_ward_prediction_summary(  # type: ignore
                ward_id=ward_id,
                ward_name=ward_name,
                grid_predictions=grid_predictions,
                aggregation_method=aggregation_method
            )
        else:
            # Fallback: create basic summary manually
            scores = list(grid_predictions.values())
            aggregated_score = float(np.mean(scores)) if scores else 0.5
            risk_class_id, risk_class_name = (0, "High") if aggregated_score >= 0.66 else ((1, "Low") if aggregated_score < 0.33 else (2, "Medium"))
            summary = {
                "Ward_ID": ward_id,
                "Ward_Name": ward_name or f"Ward_{ward_id}",
                "Flood_Risk_Score": round(aggregated_score, 4),
                "Flood_Risk_Class": risk_class_name,
                "Flood_Risk_Class_ID": risk_class_id,
                "Grid_Count": len(grid_predictions),
                "Risk_Distribution": {"High": 0.33, "Medium": 0.34, "Low": 0.33}  # Simplified
            }
        
        return summary
    except Exception as e:
        print(f"[CHAT] Error in _predict_ward_internal: {e}")
        traceback.print_exc()
        return None


def get_ward_flood_data(ward_name_query: str):
    """Get comprehensive flood risk data for a ward by name."""
    try:
        # Search for ward by name
        if search_ward_by_name is None:
            return None
        
        ward_info = search_ward_by_name(ward_name_query)  # type: ignore
        if not ward_info:
            return None
        
        ward_id = ward_info['Ward_ID']
        ward_name = ward_info.get('Ward_Name', f"Ward {ward_id}")
        
        # Get ward centroid for prediction
        centroid = get_ward_centroid(ward_id)
        if not centroid:
            return None
        
        # Get flood prediction for this ward using internal helper function
        try:
            prediction_result = _predict_ward_internal(
                centroid['latitude'],
                centroid['longitude'],
                aggregation_method="mean"
            )
        except Exception as e:
            print(f"[CHAT] Failed to get prediction for ward {ward_id}: {e}")
            prediction_result = None
        
        # Get environmental features
        features = derive_features_from_location(centroid['latitude'], centroid['longitude'])
        
        # Combine all data
        ward_data = {
            'ward_id': ward_id,
            'ward_name': ward_name,
            'location': centroid,
            'flood_prediction': prediction_result,
            'environmental_features': {
                'elevation': features.get('Elevation'),
                'road_density': features.get('Road_Density'),
                'current_rainfall_mm': features.get('Rain_mm'),
                'rainfall_past_3h_mm': features.get('Rain_Past3h'),
                'drain_water_level': features.get('Drain_Water_Level'),
                'soil_moisture': features.get('Soil_Moisture')
            }
        }
        
        return ward_data
    except Exception as e:
        print(f"[ERROR] Failed to get ward flood data: {e}")
        traceback.print_exc()
        return None


@app.post("/chat")
async def chat(request: ChatRequest):
    """Chatbot endpoint that uses Grok API to answer questions about ward flood risks.
    
    This endpoint:
    1. Extracts ward name from user message
    2. Fetches real ward data (elevation, flood risk, environmental features)
    3. Uses Grok API to generate intelligent response based on actual data
    4. Returns natural language response with flood risk assessment and prevention measures
    
    Request JSON:
    {
      "message": "What is the flood risk in FATEH NAGAR?",
      "ward_name": "FATEH NAGAR"  // optional, will be extracted from message if not provided
    }
    
    Response:
    {
      "response": "Based on the current data...",
      "ward_data": {...}  // if ward was found
    }
    """
    try:
        # Get Gemini API key from environment (optional - will use fallback if not set)
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        use_gemini = bool(gemini_api_key)
        
        if not use_gemini:
            print("[CHAT] Warning: GEMINI_API_KEY not found. Will use fallback response.")
        
        # Extract ward name from message if not provided
        ward_name_query = request.ward_name
        if not ward_name_query:
            # Try to extract ward name from message (look for "ward", "Ward", ward number, or common patterns)
            import re
            # Look for patterns like "Ward 5", "ward 5", "5", or ward names
            ward_match = re.search(r'(?:ward|Ward|WARD)\s*(\d+)', request.message, re.IGNORECASE)
            if ward_match:
                ward_name_query = ward_match.group(1)
            else:
                # Try to find ward name patterns (uppercase words, capitalized words)
                words = request.message.split()
                # Look for potential ward names (uppercase words, or words after "in", "at", "for")
                for i, word in enumerate(words):
                    if word.lower() in ['in', 'at', 'for', 'of'] and i + 1 < len(words):
                        potential_ward = words[i + 1]
                        # If it's uppercase or starts with capital, might be a ward name
                        if potential_ward.isupper() or potential_ward[0].isupper():
                            ward_name_query = potential_ward
                            break
                # If still no ward found, try to use the whole message or ask user
                if not ward_name_query:
                    # Default: try the entire message as ward name query
                    ward_name_query = request.message.strip()
        
        # Get ward data
        ward_data = None
        if ward_name_query and search_ward_by_name:
            try:
                print(f"[CHAT] Searching for ward: {ward_name_query}")
                ward_data = get_ward_flood_data(ward_name_query)
                if ward_data:
                    print(f"[CHAT] Found ward data for: {ward_data.get('ward_name')}")
                else:
                    print(f"[CHAT] No ward data found for: {ward_name_query}")
            except Exception as e:
                print(f"[CHAT] Error getting ward data: {e}")
                traceback.print_exc()
                ward_data = None
        
        # Prepare context for Gemini API
        system_prompt = """You are a helpful assistant for DelhiFlow, a flood prediction system for Delhi, India. 
You help citizens, MCD employees, and officers understand flood risks in different wards of Delhi.

When provided with ward data, analyze it and provide:
1. Current flood risk level (High/Medium/Low) and what it means
2. Specific reasons why the risk is high/medium/low based on the actual data provided (elevation, rainfall, drain water level, soil moisture, etc.)
3. Concrete prevention measures and recommendations to reduce waterlogging in that specific area
4. Be factual, helpful, and use the actual data values provided

If no ward data is provided, politely ask the user to specify a ward name or number."""

        user_message = request.message
        
        # If we have ward data, include it in the context
        if ward_data:
            flood_risk = ward_data.get('flood_prediction') or {}
            env_features = ward_data.get('environmental_features') or {}
            
            context_data = f"""
Ward Information:
- Ward ID: {ward_data.get('ward_id', 'N/A')}
- Ward Name: {ward_data.get('ward_name', 'N/A')}
- Location: {ward_data.get('location', {}).get('latitude', 'N/A') if ward_data.get('location') else 'N/A'}, {ward_data.get('location', {}).get('longitude', 'N/A') if ward_data.get('location') else 'N/A'}

Flood Risk Prediction:
- Risk Level: {flood_risk.get('Flood_Risk_Class', 'N/A') if flood_risk else 'N/A'}
- Risk Score: {flood_risk.get('Flood_Risk_Score', 'N/A') if flood_risk else 'N/A'}
- Risk Distribution: {flood_risk.get('Risk_Distribution', 'N/A') if flood_risk else 'N/A'}
- Grid Count: {flood_risk.get('Grid_Count', 'N/A') if flood_risk else 'N/A'}

Environmental Features (from actual APIs/data):
- Elevation: {env_features.get('elevation', 'N/A') if env_features else 'N/A'} meters
- Road Density: {env_features.get('road_density', 'N/A') if env_features else 'N/A'}
- Current Rainfall: {env_features.get('current_rainfall_mm', 'N/A') if env_features else 'N/A'} mm
- Rainfall (Past 3 hours): {env_features.get('rainfall_past_3h_mm', 'N/A') if env_features else 'N/A'} mm
- Drain Water Level: {env_features.get('drain_water_level', 'N/A') if env_features else 'N/A'}
- Soil Moisture: {env_features.get('soil_moisture', 'N/A') if env_features else 'N/A'}

User Question: {user_message}

Please analyze this data and provide a comprehensive answer about the flood risk, why it's at this level, and specific prevention measures."""
        else:
            context_data = f"""User Question: {user_message}

The system could not find ward data for the query. Please help the user understand this and ask them to provide a specific ward name or number."""
        
        # Call Gemini API if key is available, otherwise use fallback
        response_text = None
        if use_gemini:
            # Call Google Gemini API
            # Gemini API endpoint format: https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
            gemini_model = os.getenv("GEMINI_MODEL", "gemini-pro")
            gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Gemini API uses a different format - combine system prompt and user message
            full_prompt = f"{system_prompt}\n\n{context_data}"
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": full_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 1000,
                }
            }
            
            # Gemini API uses query parameter for API key
            params = {
                "key": gemini_api_key
            }
            
            try:
                response = requests.post(gemini_api_url, json=payload, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                gemini_response = response.json()
                
                # Extract the response text from Gemini API
                # Gemini API response format: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
                if 'candidates' in gemini_response and len(gemini_response['candidates']) > 0:
                    candidate = gemini_response['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content']:
                        parts = candidate['content']['parts']
                        if len(parts) > 0 and 'text' in parts[0]:
                            response_text = parts[0]['text']
                        else:
                            response_text = str(parts)
                    else:
                        response_text = str(candidate)
                else:
                    response_text = str(gemini_response)
                    
            except requests.exceptions.HTTPError as e:
                # Get error details from response
                error_details = "Unknown error"
                try:
                    if e.response:
                        error_response = e.response.json() if e.response.content else {}
                        error_details = error_response.get('error', {}).get('message', str(e)) if isinstance(error_response.get('error'), dict) else str(error_response)
                        print(f"[CHAT] Gemini API HTTP error: {e.response.status_code} - {error_details}")
                        # Print full error response for debugging
                        print(f"[CHAT] Full error response: {error_response}")
                    else:
                        print(f"[CHAT] Gemini API HTTP error: {e}")
                except Exception as parse_error:
                    print(f"[CHAT] Gemini API HTTP error: {e}")
                    print(f"[CHAT] Could not parse error response: {parse_error}")
                print(f"[CHAT] Using fallback response instead")
                response_text = None  # Will use fallback
            except requests.exceptions.RequestException as e:
                print(f"[CHAT] Gemini API request failed: {e}")
                print(f"[CHAT] Error details: {str(e)}")
                traceback.print_exc()
                response_text = None  # Will use fallback
        
        # Use fallback response if Gemini API is not available or failed
        if not response_text:
            if ward_data:
                flood_risk = ward_data.get('flood_prediction') or {}
                env_features = ward_data.get('environmental_features') or {}
                
                risk_level = flood_risk.get('Flood_Risk_Class', 'N/A') if flood_risk else 'N/A'
                risk_score = flood_risk.get('Flood_Risk_Score', 'N/A') if flood_risk else 'N/A'
                elevation = env_features.get('elevation', 'N/A') if env_features else 'N/A'
                rainfall = env_features.get('current_rainfall_mm', 'N/A') if env_features else 'N/A'
                drain_level = env_features.get('drain_water_level', 'N/A') if env_features else 'N/A'
                soil_moisture = env_features.get('soil_moisture', 'N/A') if env_features else 'N/A'
                road_density = env_features.get('road_density', 'N/A') if env_features else 'N/A'
                
                # Generate detailed fallback response
                response_text = f"""Flood Risk Assessment for {ward_data.get('ward_name', 'the ward')}

**Current Flood Risk Level: {risk_level}**
Risk Score: {risk_score if risk_score != 'N/A' else 'Not Available'}

**Key Environmental Factors:**
- Elevation: {elevation} meters
- Current Rainfall: {rainfall} mm
- Rainfall (Past 3 hours): {env_features.get('rainfall_past_3h_mm', 'N/A') if env_features else 'N/A'} mm
- Drain Water Level: {drain_level}
- Soil Moisture: {soil_moisture}
- Road Density: {road_density}

**Risk Analysis:**
"""
                # Add risk-specific analysis
                if risk_level == 'High':
                    response_text += "This ward has a HIGH flood risk. Contributing factors likely include:\n"
                    if isinstance(elevation, (int, float)) and elevation < 210:
                        response_text += "- Lower elevation making it prone to water accumulation\n"
                    if isinstance(rainfall, (int, float)) and rainfall > 10:
                        response_text += "- High current rainfall levels\n"
                    if isinstance(drain_level, (int, float)) and drain_level > 1.5:
                        response_text += "- Elevated drain water levels indicating drainage stress\n"
                    response_text += "\n**Urgent Prevention Measures:**\n"
                elif risk_level == 'Medium':
                    response_text += "This ward has a MEDIUM flood risk. The area is moderately vulnerable to waterlogging.\n\n**Recommended Prevention Measures:**\n"
                else:
                    response_text += "This ward has a LOW flood risk. The area is relatively safe from flooding.\n\n**Maintenance Recommendations:**\n"
                
                response_text += """1. Ensure proper drainage system maintenance and regular cleaning
2. Monitor drain water levels, especially during monsoon season
3. Clear blocked drains and stormwater channels before heavy rains
4. Consider elevation improvements in low-lying sub-areas
5. Implement rainwater harvesting systems to reduce surface runoff
6. Regular inspection of drainage infrastructure
7. Coordinate with municipal authorities for timely interventions

**Note:** This assessment is based on current environmental data and predictive modeling. Risk levels may change with weather conditions."""
            else:
                response_text = "I couldn't find data for that ward. Please provide a specific ward name or number (e.g., 'FATEH NAGAR', 'Ward 5', or just '5')."
        
        return {
            "response": response_text,
            "ward_data": ward_data if ward_data else None,
            "message": request.message
        }
        
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"[CHAT] Error in chat endpoint: {tb}")
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


# ========================= SAFE ROUTE FINDING ENDPOINTS =======================

try:
    from .safe_route import get_route_manager, load_sample_roads  # type: ignore
except Exception:
    try:
        from safe_route import get_route_manager, load_sample_roads  # type: ignore
    except Exception:
        get_route_manager = None  # type: ignore
        load_sample_roads = None  # type: ignore


class RouteRequest(BaseModel):
    """Request model for finding safe routes."""
    source_lat: float
    source_lon: float
    destination_lat: float
    destination_lon: float


class RouteInitRequest(BaseModel):
    """Request model to initialize road network."""
    roads_geojson: Optional[Dict] = None
    use_sample_data: bool = True


@app.post("/safe-route/initialize")
def initialize_route_system(request: RouteInitRequest):
    """Initialize safe route system with road network data.
    
    Request JSON:
    {
      "roads_geojson": {GeoJSON FeatureCollection},
      "use_sample_data": false  // if true, uses sample roads for demo
    }
    
    Response:
    {
      "status": "success",
      "segments_count": 15,
      "timestamp": "2025-01-10T..."
    }
    """
    try:
        if get_route_manager is None:
            raise HTTPException(
                status_code=500,
                detail="Safe route system not available"
            )
        
        manager = get_route_manager()
        
        # Load roads from request or use sample data
        if request.use_sample_data or not request.roads_geojson:
            if load_sample_roads is None:
                raise HTTPException(
                    status_code=500,
                    detail="Sample data loader not available"
                )
            roads_geojson = load_sample_roads()
            print("[SAFE_ROUTE] Using sample road network")
        else:
            roads_geojson = request.roads_geojson
        
        # Add roads to manager
        segment_count = manager.add_road_network(roads_geojson)
        
        return {
            "status": "success",
            "segments_count": segment_count,
            "timestamp": datetime.datetime.now().isoformat(),
            "message": "Road network initialized successfully"
        }
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"[SAFE_ROUTE] Initialize error: {tb}")
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.post("/safe-route/find")
def find_safe_route(request: RouteRequest):
    """Find multiple alternative safe routes between two points.
    
    Returns the best route plus alternatives, allowing user to choose based on real-time
    flood risk and other factors.
    """
    try:
        if get_route_manager is None:
            raise HTTPException(
                status_code=500,
                detail="Safe route system not available"
            )
        
        manager = get_route_manager()
        source = (request.source_lon, request.source_lat)
        destination = (request.destination_lon, request.destination_lat)
        
        # Find multiple alternative routes
        routes = manager.find_multiple_routes(source, destination, num_routes=3)
        
        if not routes:
            raise HTTPException(
                status_code=404,
                detail="No route found between source and destination"
            )
        
        # Prepare visualization data for all routes
        from safe_route import convert_numpy_types
        
        routes_data = []
        for route in routes:
            viz_data = manager.get_route_visualization(route)
            routes_data.append(viz_data)
        
        # Return all routes with the best one highlighted
        return convert_numpy_types({
            "primary_route": routes_data[0],  # Best route (lowest risk)
            "alternative_routes": routes_data[1:],  # Alternative options
            "all_routes": routes_data,
            "timestamp": datetime.datetime.now().isoformat()
        })
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        print(f"[SAFE_ROUTE] Find error: {tb}")
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.get("/safe-route/segments")
def get_segments():
    """Get all road segments for visualization.
    
    Response:
    {
      "segments": [
        {
          "segment_id": "seg_0",
          "geometry": {type: "LineString", coordinates: [...]},
          "ward_id": 5,
          "ward_name": "Ward 5",
          "flood_risk": 0.45,
          "elevation": 220.5,
          "drain_distance": 150.2,
          "is_underpass": false,
          "risk_score": 0.42,
          "risk_level": "medium",
          "length": 75.3
        },
        ...
      ],
      "total_segments": 45
    }
    """
    try:
        if get_route_manager is None:
            raise HTTPException(
                status_code=500,
                detail="Safe route system not available"
            )
        
        manager = get_route_manager()
        segments = manager.get_all_segments()
        
        # Import convert_numpy_types from safe_route module
        from safe_route import convert_numpy_types
        
        result = {
            "segments": segments,
            "total_segments": len(segments),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return convert_numpy_types(result)
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})


@app.get("/safe-route/stats")
def get_route_stats():
    """Get statistics about the road network.
    
    Response:
    {
      "total_segments": 45,
      "by_risk_level": {
        "high": 8,
        "medium": 18,
        "low": 19
      },
      "by_ward": {
        "Ward 5": 12,
        "Ward 3": 15,
        ...
      },
      "elevation_range": {"min": 195.2, "max": 245.8},
      "timestamp": "2025-01-10T..."
    }
    """
    try:
        if get_route_manager is None:
            raise HTTPException(
                status_code=500,
                detail="Safe route system not available"
            )
        
        manager = get_route_manager()
        segments = manager.get_all_segments()
        
        # ADD DIAGNOSTIC INFO
        print(f"\n[STATS] === DIAGNOSTIC INFO ===")
        print(f"[STATS] Segments in manager: {len(manager.segments)}")
        print(f"[STATS] Graph nodes in manager: {len(manager.graph)}")
        print(f"[STATS] Segment graph edges: {len(manager.segment_graph)}")
        print(f"[STATS] Segments returned by get_all_segments: {len(segments)}")
        
        if manager.segments:
            first_seg_id = list(manager.segments.keys())[0]
            first_seg = manager.segments[first_seg_id]
            print(f"[STATS] First segment ID: {first_seg_id}")
            print(f"[STATS] First segment coords: {first_seg.geometry['coordinates'][:2]}")
        
        if manager.graph:
            sample_nodes = list(manager.graph.keys())[:3]
            for node in sample_nodes:
                print(f"[STATS] Node {node}: {len(manager.graph[node])} neighbors")
        
        if not segments:
            return {
                "total_segments": 0,
                "by_risk_level": {},
                "by_ward": {},
                "timestamp": datetime.datetime.now().isoformat()
            }
        
        # Compute statistics
        risk_counts = {"high": 0, "medium": 0, "low": 0}
        ward_counts = {}
        elevations = []
        
        for seg in segments:
            risk_level = seg.get("risk_level", "unknown")
            if risk_level in risk_counts:
                risk_counts[risk_level] += 1
            
            ward_name = seg.get("ward_name", "Unknown")
            if ward_name:
                ward_counts[ward_name] = ward_counts.get(ward_name, 0) + 1
            
            if seg.get("elevation"):
                elevations.append(seg["elevation"])
        
        # Import convert_numpy_types from safe_route module
        from safe_route import convert_numpy_types
        
        stats = {
            "total_segments": len(segments),
            "by_risk_level": risk_counts,
            "by_ward": ward_counts,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        if elevations:
            stats["elevation_range"] = {
                "min": float(min(elevations)),
                "max": float(max(elevations)),
                "mean": float(np.mean(elevations))
            }
        
        return convert_numpy_types(stats)
    
    except HTTPException:
        raise
    except Exception as ex:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(ex), "trace": tb})
