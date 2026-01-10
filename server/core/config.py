import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB configuration
MONGO_URL = os.getenv("MONGODB_URI", "mongodb://localhost:27017/delhiflow")

# Model paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'model', 'potholes.pt')

# If potholes.pt doesn't exist, fall back to yolov8n.pt
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = os.path.join(BASE_DIR, 'yolov8n.pt')

# Toggle to relax EXIF/time/location validation for pothole citizen reports
# Set RELAX_EXIF_VALIDATION=true to allow desktop/gallery uploads during testing
RELAX_EXIF_VALIDATION = os.getenv("RELAX_EXIF_VALIDATION", "false").lower() == "true"
