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
        # Validate Delhi coordinates (rough bounds)
        if not (28.4 <= request.latitude <= 28.9 and 76.8 <= request.longitude <= 77.3):
            raise HTTPException(status_code=400, detail="Coordinates appear to be outside Delhi region")
        
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