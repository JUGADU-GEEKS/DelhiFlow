# How Flood Risk is Calculated

## Overview
The flood risk calculation uses a machine learning model trained on historical flood data to predict the risk level for each ward in Delhi.

## Risk Calculation Process

### 1. **Data Collection**
For each ward, the system collects/generates the following environmental features:

- **Elevation** (meters): Ground elevation above sea level
- **Road Density**: Density of road networks (0-1 scale)
- **Rain_mm**: Current rainfall in millimeters
- **Rain_Past3h**: Rainfall in the past 3 hours (mm)
- **Drain_Water_Level**: Current water level in drainage systems
- **Soil_Moisture**: Soil moisture content (0-1 scale)
- **hour_of_day**: Current hour (0-23)
- **month**: Current month (1-12)
- **day_of_week**: Day of week (0-6)

### 2. **Feature Processing**
- Continuous features (Elevation, Road Density, Rainfall, etc.) are scaled using a saved scaler
- Time features (hour, month, day_of_week) are converted to cyclical features using sine/cosine transformations:
  - `hour_sin = sin(2π × hour / 24)`
  - `hour_cos = cos(2π × hour / 24)`
  - `month_sin = sin(2π × month / 12)`
  - `month_cos = cos(2π × month / 12)`
  - `dow_sin = sin(2π × day_of_week / 7)`
  - `dow_cos = cos(2π × day_of_week / 7)`

### 3. **ML Model Prediction**
The processed features are passed through a trained machine learning model (`flood_model.pkl`) which predicts:
- **Class ID**: 0 = High Risk, 1 = Low Risk, 2 = Medium Risk
- **Confidence**: Probability of the predicted class

### 4. **Class to Score Conversion**
The predicted class is converted to a normalized score (0-1 scale):
- **High Risk (Class 0)** → Score: **0.8**
- **Low Risk (Class 1)** → Score: **0.2**
- **Medium Risk (Class 2)** → Score: **0.5**

### 5. **Ward-Level Aggregation**
For wards with multiple grids:
- Scores from all grids are aggregated using one of these methods:
  - **Mean** (default): Average of all grid scores
  - **Max**: Highest grid score
  - **Median**: Middle value of grid scores
  - **Percentile_75**: 75th percentile of scores
  - **Percentile_90**: 90th percentile of scores

### 6. **Score to Class Conversion (Final Risk Level)**
The aggregated score is converted back to a risk class using thresholds:
- **Score < 0.33** → **Low Risk**
- **Score 0.33 - 0.66** → **Medium Risk**
- **Score ≥ 0.66** → **High Risk**

## Example Calculation

For Ward 5 (BAKHTAWARPUR):
1. System gets ward centroid coordinates
2. Derives environmental features from location and current time
3. Runs prediction model → Gets Class 2 (Medium)
4. Converts to score: 0.5
5. If multiple grids exist, aggregates scores (mean = 0.5)
6. Final classification: Score 0.5 → **Medium Risk**

## Key Factors Affecting Risk

- **Lower elevation** → Higher risk
- **Higher rainfall** → Higher risk
- **Higher drain water level** → Higher risk
- **Higher soil moisture** → Higher risk
- **Monsoon season (July-September)** → Generally higher risk
- **Time of day** → Certain hours may have higher risk

## Notes

- The model was trained on 1 million+ data points
- It has 98% accuracy
- Predictions are based on real-time or derived environmental data
- Risk levels are dynamic and change with weather conditions
