## backend server/app.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, conlist
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import joblib
import os
import numpy as np
import traceback


BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, 'model', 'flood_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'scaler', 'scaler.pkl')
ENCODER_PATH = os.path.join(BASE_DIR, 'encoder', 'label_encoder.pkl')


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

## backend server/app.py