from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, json, uuid, logging
import torch
import torch.nn as nn
import numpy as np
import cv2
from PIL import Image
from torchvision import models, transforms
from werkzeug.utils import secure_filename
from treatment_recommendation import get_recommendation
from concurrent.futures import ThreadPoolExecutor
import threading
from huggingface_hub import hf_hub_download

MODEL_PATH = hf_hub_download(
    repo_id="divy-g-2005/Plant-Disease-Detection",
    filename="best_model.pth"
)
# ─────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
DEVICE          = "cuda" if torch.cuda.is_available() else "cpu"
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR      = os.path.join(BASE_DIR, "models")
CLASS_MAP_PATH  = os.path.join(MODELS_DIR, "class_map.json")
UPLOAD_FOLDER   = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MIN_CONFIDENCE  = 0.30
MIN_LEAF_RATIO  = 0.05
MAX_IMAGE_SIZE  = 800  # resize large images to save memory

SEVERITY_THRESHOLDS = {
    "Mild":     (0,  25),
    "Moderate": (25, 50),
    "Severe":   (50, 75),
    "Critical": (75, 100),
}
W_AREA, W_COLOR, W_SPREAD, W_ZONE = 0.40, 0.25, 0.20, 0.15
HEALTHY_LAB     = np.array([128, 110, 145], dtype=np.float32)
HSV_LOWER_GREEN = np.array([25, 30, 30])
HSV_UPPER_GREEN = np.array([95, 255, 255])

# Thread pool for concurrent requests
executor = ThreadPoolExecutor(max_workers=4)
model_lock = threading.Lock()

# ─────────────────────────────────────────
# LOAD CLASS MAP
# ─────────────────────────────────────────
with open(CLASS_MAP_PATH) as f:
    class_map = json.load(f)["idx_to_class"]
CLASSES = [class_map[str(i)] for i in range(len(class_map))]

# ─────────────────────────────────────────
# LOAD MODEL ONCE AT STARTUP
# ─────────────────────────────────────────
def load_model():
    logger.info(f"Loading model from {MODEL_PATH} on {DEVICE}")
    ckpt       = torch.load(MODEL_PATH, map_location=DEVICE)
    img_size   = ckpt.get("img_size", 300)
    m          = models.efficientnet_b3(weights=None)
    in_features = m.classifier[1].in_features
    m.classifier = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(in_features, 512),
        nn.ReLU(),
        nn.Dropout(0.2),
        nn.Linear(512, len(CLASSES)),
    )
    m.load_state_dict(ckpt["model_state"])
    m.to(DEVICE).eval()
    logger.info("Model loaded successfully!")
    return m, img_size

model, IMAGE_SIZE = load_model()

transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# ─────────────────────────────────────────
# IMAGE HELPERS
# ─────────────────────────────────────────
def resize_if_large(image_path):
    """Resize image if too large to save memory and speed up processing."""
    img = cv2.imread(image_path)
    if img is None:
        return
    h, w = img.shape[:2]
    if max(h, w) > MAX_IMAGE_SIZE:
        scale = MAX_IMAGE_SIZE / max(h, w)
        img   = cv2.resize(img, (int(w * scale), int(h * scale)))
        cv2.imwrite(image_path, img)

def is_leaf_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return False, 0.0
    img_hsv    = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask       = cv2.inRange(img_hsv, HSV_LOWER_GREEN, HSV_UPPER_GREEN)
    green_ratio = float(mask.sum()) / float(mask.size * 255)
    return green_ratio >= MIN_LEAF_RATIO, round(green_ratio * 100, 2)

def preprocess_image(path):
    img = Image.open(path).convert("RGB")
    return transform(img).unsqueeze(0).to(DEVICE)

# ─────────────────────────────────────────
# SEVERITY ANALYSIS
# ─────────────────────────────────────────
def severity_label(score):
    for label, (lo, hi) in SEVERITY_THRESHOLDS.items():
        if lo <= score < hi:
            return label
    return "Critical"

def segment_leaf(img_bgr):
    img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask    = cv2.inRange(img_hsv, HSV_LOWER_GREEN, HSV_UPPER_GREEN)
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask    = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask    = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel, iterations=2)
    if mask.sum() / (mask.size * 255) < 0.10:
        mask = np.ones(img_bgr.shape[:2], dtype=np.uint8) * 255
    return mask

def detect_infected_region(img_bgr, leaf_mask):
    img_hsv      = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    healthy_mask = cv2.inRange(img_hsv, HSV_LOWER_GREEN, HSV_UPPER_GREEN)
    infected     = cv2.bitwise_and(cv2.bitwise_not(healthy_mask), leaf_mask)
    kernel       = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    infected     = cv2.morphologyEx(infected, cv2.MORPH_CLOSE, kernel, iterations=2)
    infected     = cv2.morphologyEx(infected, cv2.MORPH_OPEN,  kernel, iterations=1)
    return infected

def compute_area_score(infected_mask, leaf_mask):
    return min(100.0, int((infected_mask > 0).sum()) / max(1, int((leaf_mask > 0).sum())) * 100.0)

def compute_color_score(img_bgr, leaf_mask):
    img_lab     = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    leaf_pixels = img_lab[leaf_mask > 0]
    if len(leaf_pixels) == 0:
        return 0.0
    return min(100.0, float(np.linalg.norm(leaf_pixels - HEALTHY_LAB, axis=1).mean()) / 260.0 * 100.0)

def compute_spread_score(infected_mask):
    contours, _ = cv2.findContours(infected_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours    = [c for c in contours if cv2.contourArea(c) > infected_mask.size * 0.0001]
    num_spots   = len(contours)
    if num_spots == 0:
        return 0.0, 0
    centroids = []
    for c in contours:
        m = cv2.moments(c)
        if m["m00"] > 0:
            centroids.append((m["m10"] / m["m00"], m["m01"] / m["m00"]))
    avg_dist = 0.0
    if len(centroids) >= 2:
        distances = [np.sqrt((centroids[i][0]-centroids[j][0])**2 + (centroids[i][1]-centroids[j][1])**2)
                     for i in range(len(centroids)) for j in range(i+1, len(centroids))]
        avg_dist = float(np.mean(distances))
    h, w = infected_mask.shape
    max_dist = np.sqrt(h**2 + w**2) / 2
    return (0.5 * min(1.0, num_spots/20.0) + 0.5 * (min(1.0, avg_dist/max_dist) if max_dist > 0 else 0.0)) * 100.0, num_spots

def compute_zone_score(infected_mask, grid=3):
    h, w = infected_mask.shape
    zone_h, zone_w = h // grid, w // grid
    zones_infected = sum(
        1 for row in range(grid) for col in range(grid)
        if infected_mask[row*zone_h:(row+1)*zone_h if row < grid-1 else h,
                         col*zone_w:(col+1)*zone_w if col < grid-1 else w].size > 0 and
           (infected_mask[row*zone_h:(row+1)*zone_h if row < grid-1 else h,
                          col*zone_w:(col+1)*zone_w if col < grid-1 else w] > 0).mean() > 0.01
    )
    return zones_infected / (grid * grid) * 100.0, zones_infected

def build_severity_overlay(img_bgr, leaf_mask, infected_mask):
    overlay = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).copy()
    overlay[leaf_mask > 0]     = (overlay[leaf_mask > 0]     * 0.6 + np.array([0, 180, 0])   * 0.4).astype(np.uint8)
    overlay[infected_mask > 0] = (overlay[infected_mask > 0] * 0.4 + np.array([220, 50, 50]) * 0.6).astype(np.uint8)
    h, w = infected_mask.shape
    for i in range(1, 3):
        cv2.line(overlay, (int(w*i/3), 0), (int(w*i/3), h), (255,255,255), 1)
        cv2.line(overlay, (0, int(h*i/3)), (w, int(h*i/3)), (255,255,255), 1)
    return cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)

def calculate_severity(image_path, severity_image_name=None):
    img = cv2.imread(image_path)
    if img is None:
        return {"percentage": 0.0, "label": "Unknown", "infected_pct": 0.0,
                "spot_count": 0, "zones_infected": 0,
                "breakdown": {"area_score": 0.0, "color_score": 0.0, "spread_score": 0.0, "zone_score": 0.0},
                "severity_image_url": None}
    leaf_mask              = segment_leaf(img)
    infected_mask          = detect_infected_region(img, leaf_mask)
    area_score             = compute_area_score(infected_mask, leaf_mask)
    color_score            = compute_color_score(img, leaf_mask)
    spread_score, num_spots = compute_spread_score(infected_mask)
    zone_score, zones_infected = compute_zone_score(infected_mask)
    final_score = W_AREA*area_score + W_COLOR*color_score + W_SPREAD*spread_score + W_ZONE*zone_score
    severity_image_url = None
    if severity_image_name:
        severity_path = os.path.join(UPLOAD_FOLDER, severity_image_name)
        cv2.imwrite(severity_path, build_severity_overlay(img, leaf_mask, infected_mask))
        severity_image_url = f"/uploads/{severity_image_name}"
    return {"percentage": round(float(final_score), 2), "label": severity_label(final_score),
            "infected_pct": round(float(area_score), 2), "spot_count": num_spots,
            "zones_infected": zones_infected,
            "breakdown": {"area_score": round(float(area_score), 2), "color_score": round(float(color_score), 2),
                          "spread_score": round(float(spread_score), 2), "zone_score": round(float(zone_score), 2)},
            "severity_image_url": severity_image_url}

# ─────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────
app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return jsonify({"status": "Plant Disease Detection API running ✅", "device": DEVICE})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/predict", methods=["POST"])
def predict():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file          = request.files["file"]
    original_name = secure_filename(file.filename) or "upload.jpg"
    stem, ext     = os.path.splitext(original_name)
    ext           = ext or ".jpg"
    unique_id     = uuid.uuid4().hex[:12]
    stored_name   = f"{stem}_{unique_id}{ext}"
    severity_name = f"{stem}_{unique_id}_severity.png"
    filepath      = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(filepath)

    try:
        # Resize large images
        resize_if_large(filepath)

        # Validate leaf
        leaf_detected, green_pct = is_leaf_image(filepath)
        if not leaf_detected:
            os.remove(filepath)
            return jsonify({
                "error": "no_leaf",
                "message": f"No leaf detected (green area: {green_pct}%). Please upload a clear plant leaf photo."
            }), 422

        # Disease detection (thread-safe)
        with model_lock:
            with torch.no_grad():
                probs = torch.softmax(model(preprocess_image(filepath)), dim=1)
                confidence, class_index = torch.max(probs, 1)

        disease        = CLASSES[class_index.item()]
        confidence_pct = round(float(confidence.item()) * 100, 1)

        # Low confidence check
        if confidence_pct < MIN_CONFIDENCE * 100:
            return jsonify({
                "error": "low_confidence",
                "message": f"Confidence too low ({confidence_pct}%). Please upload a clearer image with good lighting."
            }), 422

        # Severity analysis
        if disease.lower() == "healthy":
            severity = {"percentage": 0.0, "label": "Healthy", "infected_pct": 0.0,
                        "spot_count": 0, "zones_infected": 0,
                        "breakdown": {"area_score": 0.0, "color_score": 0.0, "spread_score": 0.0, "zone_score": 0.0},
                        "severity_image_url": None}
        else:
            severity = calculate_severity(filepath, severity_image_name=severity_name)

        # Treatment
        rec = get_recommendation(disease, confidence_pct, severity["percentage"], severity["label"])

        logger.info(f"Predicted: {disease} ({confidence_pct}%) | Severity: {severity['label']}")

        return jsonify({
            "disease":                disease,
            "confidence":             confidence_pct,
            "severity":               severity["percentage"],
            "severity_label":         severity["label"],
            "infected_pct":           severity["infected_pct"],
            "spot_count":             severity["spot_count"],
            "zones_infected":         severity["zones_infected"],
            "breakdown":              severity["breakdown"],
            "severity_image_url":     severity["severity_image_url"],
            "treatment":              rec["recommended_treatment"],
            "dose":                   rec["dose"],
            "timing":                 rec["timing"],
            "method":                 rec["method"],
            "interval":               rec["interval"],
            "warning":                rec["warning"],
            "cultural_advice":        rec["cultural_advice"],
            "monitoring":             rec["monitoring"],
            "urgency_note":           rec["urgency_note"],
            "low_confidence_warning": rec["low_confidence_warning"],
            "reason":                 rec["reason"],
        })

    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return jsonify({"error": "server_error", "message": "Something went wrong. Please try again."}), 500

    finally:
        # Cleanup old uploads (keep last 100)
        try:
            files = sorted([os.path.join(UPLOAD_FOLDER, f) for f in os.listdir(UPLOAD_FOLDER)],
                           key=os.path.getmtime)
            if len(files) > 100:
                for f in files[:-100]:
                    os.remove(f)
        except:
            pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)