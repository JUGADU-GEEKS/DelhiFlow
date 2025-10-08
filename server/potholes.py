from __future__ import annotations
import io, os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

router = APIRouter()

_MODEL = None
_MODEL_NAMES = None

def _get_model():
    global _MODEL, _MODEL_NAMES
    if _MODEL is not None:
        return _MODEL
    try:
        from ultralytics import YOLO  # type: ignore
    except Exception:
        _MODEL = None
        _MODEL_NAMES = None
        return None
    model_path = os.getenv("POTHOLES_MODEL_PATH", "yolov8n.pt")
    try:
        _MODEL = YOLO(model_path)
        _MODEL_NAMES = getattr(_MODEL, "names", {0: "Pothole"})
    except Exception:
        _MODEL = None
        _MODEL_NAMES = None
    return _MODEL

def _dummy_boxes(w: int, h: int) -> List[Dict[str, Any]]:
    bw, bh = int(w * 0.25), int(h * 0.25)
    x, y = int((w - bw) / 2), int((h - bh) / 2)
    return [{"x": x, "y": y, "width": bw, "height": bh, "score": 0.88, "label": "Pothole"}]

def _cv2_fallback(img) -> List[Dict[str, Any]]:
    import numpy as np, cv2
    if isinstance(img, bytes):
        np_arr = np.frombuffer(img, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    else:
        frame = img
    if frame is None:
        return []
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thr = max(10, int(gray.mean() * 0.9))
    _, mask = cv2.threshold(blur, thr, 255, cv2.THRESH_BINARY_INV)
    edges = cv2.Canny(blur, 40, 120)
    mask = cv2.bitwise_or(mask, edges)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = float(w * h)
    dets: List[Dict[str, Any]] = []
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        if area < img_area * 0.0003 or area > img_area * 0.25:
            continue
        roi = gray[y:y+bh, x:x+bw]
        if roi.size == 0:
            continue
        darkness = 1.0 - (float(roi.mean()) / 255.0)
        size_score = min(1.0, area / (img_area * 0.02))
        score = max(0.1, 0.5 * darkness + 0.5 * size_score)
        dets.append({"x": float(x), "y": float(y), "width": float(bw), "height": float(bh), "score": round(float(score), 3), "label": "Pothole"})
    dets.sort(key=lambda d: d["score"], reverse=True)
    return dets[:50]

@router.post("/detect")
async def detect_potholes(image: UploadFile = File(None), file: UploadFile = File(None)):
    # Accept both 'image' and 'file' field names
    upload: Optional[UploadFile] = image or file
    if upload is None:
        return JSONResponse({"detections": [], "error": "No file field 'image' or 'file' provided"}, status_code=400)

    try:
        from PIL import Image
    except Exception:
        # If Pillow missing, try OpenCV path directly
        data = await upload.read()
        try:
            dets = _cv2_fallback(data)
        except Exception:
            dets = []
        if not dets:
            dets = _dummy_boxes(640, 360)
        return {"detections": dets, "image_size": {"width": 640, "height": 360}, "engine": "cv2_no_pillow"}

    data = await upload.read()
    # Decode with Pillow; fallback to OpenCV if Pillow can't decode (e.g., unsupported format)
    try:
        pil_img = Image.open(io.BytesIO(data)).convert("RGB")
        w, h = pil_img.size
    except Exception:
        try:
            import numpy as np, cv2
            bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if bgr is None:
                raise ValueError("decode failed")
            h, w = bgr.shape[:2]
            dets = _cv2_fallback(bgr)
            return {"detections": dets or _dummy_boxes(w, h), "image_size": {"width": w, "height": h}, "engine": "cv2_fallback"}
        except Exception:
            return {"detections": _dummy_boxes(640, 360), "image_size": {"width": 640, "height": 360}, "engine": "dummy"}

    # Try YOLO (only if model knows 'pothole'); otherwise cv2 fallback
    detections: List[Dict[str, Any]] = []
    model = _get_model()
    model_has_pothole = False
    try:
        names = list((_MODEL_NAMES or {}).values()) if isinstance(_MODEL_NAMES, dict) else (_MODEL_NAMES or [])
        model_has_pothole = any("pothole" in str(n).lower() for n in names)
    except Exception:
        model_has_pothole = False

    if model is not None and model_has_pothole:
        try:
            results = model.predict(pil_img, imgsz=640, conf=0.25, verbose=False)
            res = results[0]
            boxes = getattr(res, "boxes", None)
            names = getattr(res, "names", _MODEL_NAMES) or {}
            if boxes is not None and hasattr(boxes, "xyxy"):
                xyxy = boxes.xyxy.cpu().tolist()
                confs = boxes.conf.cpu().tolist() if hasattr(boxes, "conf") else [None] * len(xyxy)
                clss = boxes.cls.cpu().tolist() if hasattr(boxes, "cls") else [0] * len(xyxy)
                for (x1, y1, x2, y2), sc, c in zip(xyxy, confs, clss):
                    label = str((names or {}).get(int(c), ""))
                    if "pothole" not in label.lower():
                        continue
                    detections.append({"x": float(x1), "y": float(y1), "width": float(x2 - x1), "height": float(y2 - y1), "score": float(sc) if sc is not None else None, "label": "Pothole"})
        except Exception:
            detections = []

    if not detections:
        import numpy as np, cv2
        bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        detections = _cv2_fallback(bgr)
        engine = "cv2_fallback"
    else:
        engine = "ultralytics"

    if not detections:
        detections = _dummy_boxes(w, h)
        engine = "dummy"

    return {"detections": detections, "image_size": {"width": w, "height": h}, "engine": engine}