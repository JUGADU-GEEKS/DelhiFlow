# Pothole Detection & Mapping System - Setup Guide

## Overview
This system allows users to report potholes via image uploads (with EXIF validation) or IoT devices, and visualize them on a map for the Delhi region.

## System Architecture

### Backend Endpoints
- **POST /analyze_issue** - Analyze image for pothole detection (returns detections)
- **POST /potholes/report** - Report pothole from citizen (with EXIF validation)
- **POST /potholes/iot** - Report pothole from IoT device (fallback without EXIF)
- **GET /potholes/map** - Get all reported potholes for map display

### Frontend Routes
- **/potholes** - Pothole reporting interface
- **/potholes-map** - Interactive map showing all potholes

## Setup Instructions

### 1. Backend Setup

#### Install Dependencies
```bash
cd server
pip install -r requirements.txt
```

#### Configure Environment Variables
The `.env` file should contain:
```
MONGODB_URI=your_mongodb_connection_string
MONGODB_NAME=delhiflow
```

#### Verify Model Files
Ensure you have a YOLO model at one of these locations:
- `server/model/potholes.pt` (preferred - trained pothole detection model)
- `server/yolov8n.pt` (fallback - general YOLO model)

#### Run the Server
```bash
cd server
python main.py
# or
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend Setup

#### Install Dependencies
```bash
cd client
npm install
```

#### Configure Environment Variables
Create `client/.env`:
```
VITE_API_URL=http://127.0.0.1:8000
VITE_GOOGLE_MAPS_API_KEY=your_google_maps_api_key
```

#### Run the Development Server
```bash
cd client
npm run dev
```

## How It Works

### Citizen Reporting Flow
1. User captures photo using camera on `/potholes` page
2. Frontend sends image to `/analyze_issue` for initial detection
3. If pothole detected, frontend automatically sends to `/potholes/report`
4. Backend validates:
   - EXIF GPS data exists and matches browser location (within 40m)
   - Photo timestamp is recent (within 2 minutes)
   - YOLO model confirms pothole presence
5. If validation passes, pothole is saved to MongoDB with 50m grid bucketing
6. If EXIF validation fails (desktop/gallery images), falls back to `/potholes/iot`

### Database Structure
Each pothole record contains:
- `gridId` - 50m grid cell identifier
- `lat`, `lon` - Grid cell coordinates
- `potholeCount` - Number of reports in this grid
- `status` - "pending" or "resolved"
- `reports` - Array of individual reports with source, timestamp, coordinates

### Grid Bucketing
- Potholes are grouped into 50m x 50m grid cells
- Multiple reports in same grid increment the counter
- Prevents duplicate markers for same pothole
- Grid center coordinates shown on map

## Features

### Anti-Fake Measures
- **EXIF GPS Validation** - Image must contain GPS coordinates matching browser location
- **Timestamp Check** - Photo must be taken within last 2 minutes
- **Location Proximity** - EXIF location must be within 40m of browser location
- **YOLO Confirmation** - ML model must detect pothole with >35% confidence

### Map Visualization
- Color-coded markers by severity:
  - 🔴 Red (5+ reports) - High severity
  - 🟠 Orange (2-4 reports) - Medium severity
  - 🟡 Yellow (1 report) - Low severity
- Auto-fit bounds to show all potholes
- Status indicator (pending/resolved)

## API Response Examples

### /analyze_issue
```json
{
  "pothole_detected": true,
  "detections": [
    {
      "class": "pothole",
      "confidence": 0.87,
      "bbox": {"x1": 120, "y1": 340, "x2": 280, "y2": 450},
      "is_pothole": true
    }
  ],
  "image_size": {"width": 1920, "height": 1080}
}
```

### /potholes/report
```json
{
  "success": true,
  "detected": true,
  "gridId": "5123_1385",
  "potholeCount": 3
}
```

### /potholes/map
```json
[
  {
    "lat": 28.6139,
    "lon": 77.2090,
    "potholeCount": 5,
    "status": "pending"
  }
]
```

## Troubleshooting

### "Please capture a LIVE photo using camera"
- Desktop browsers don't support EXIF data in camera captures
- System will automatically fall back to IoT endpoint
- Mobile browsers (iOS Safari, Android Chrome) work best

### "Location mismatch"
- Ensure location permissions are enabled
- Take photo at actual pothole location
- Check GPS accuracy in phone settings

### Model not loading
- Verify `yolov8n.pt` or `model/potholes.pt` exists
- Check file permissions
- Ensure `ultralytics` package is installed

### MongoDB connection issues
- Verify MongoDB URI in `.env`
- Check network connectivity
- Ensure MongoDB cluster allows your IP

## Project Structure
```
server/
├── core/
│   ├── config.py           # Configuration (MONGO_URL, MODEL_PATH)
│   └── __init__.py
├── utils/
│   ├── exif_utils.py       # EXIF GPS extraction
│   ├── gps_utils.py        # Haversine distance, grid bucketing
│   └── __init__.py
├── app.py                   # Main FastAPI application
├── potholes_router.py      # Pothole API endpoints
├── pothole_service.py      # Business logic
├── pothole_model.py        # Pydantic models
└── requirements.txt

client/
├── src/
│   ├── components/
│   │   ├── Pothole_issue.jsx   # Reporting interface
│   │   └── PotholesMap.jsx     # Map visualization
│   └── App.jsx                  # Route configuration
└── .env                         # Frontend config
```

## MongoDB Collections

### potholes
```javascript
{
  "_id": ObjectId("..."),
  "gridId": "5123_1385",
  "lat": 28.6139,
  "lon": 77.2090,
  "potholeCount": 3,
  "latestReportTime": ISODate("2026-01-10T12:00:00Z"),
  "status": "pending",
  "reports": [
    {
      "source": "citizen",
      "lat": 28.61392,
      "lon": 77.20905,
      "timestamp": ISODate("2026-01-10T12:00:00Z")
    }
  ]
}
```

## Next Steps
- Train custom YOLO model on pothole dataset for better accuracy
- Implement resolution workflow for authorities
- Add notification system for high-severity areas
- Create heat map overlay for visualization
- Export data for analytics and planning
