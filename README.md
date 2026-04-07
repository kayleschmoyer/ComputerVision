# ScanGuard Lite (Self-Checkout Fraud Detection MVP)

ScanGuard Lite is a production-oriented Python MVP for suspicious behavior detection at self-checkout.
It combines **YOLOv8 + ByteTrack + OpenCV** for video intelligence, a **rule engine** for fraud heuristics,
and a **FastAPI backend + HTML/JS dashboard** for alert monitoring.

## Features

- Single-machine deployment (CPU-first, optional GPU via torch/CUDA environment)
- YOLOv8 object detection and ByteTrack multi-object tracking
- Configurable scan zone and bagging zone (from `config.yaml`)
- Rule-based suspicious behavior detection:
  - Item enters scan zone but no scan-like event occurs in time
  - Barcode likely covered by hand while in scan zone
  - Item bypasses scan zone and reaches bagging area
  - Item potentially swapped after inferred scan
- Event handling:
  - Saves short event clips locally
  - Sends events to backend API
- FastAPI backend:
  - `POST /alerts`
  - `GET /alerts`
  - `GET /ws/alerts` (WebSocket)
- Lightweight dashboard for live alerts and clip playback

---

## Project Structure

```text
.
├── config.yaml
├── requirements.txt
├── src/
│   └── scanguard_lite/
│       ├── api.py
│       ├── config.py
│       ├── detection.py
│       ├── events.py
│       ├── main_api.py
│       ├── main_cv.py
│       ├── rules.py
│       ├── tracking.py
│       └── dashboard/
│           ├── app.js
│           ├── index.html
│           └── styles.css
├── clips/            # generated event clips
└── data/             # sqlite DB
```

---

## Requirements

- Python **3.10** or **3.11**
- Linux/macOS/Windows
- Webcam or RTSP stream

> Note: `ultralytics` will automatically pull PyTorch dependencies. For GPU acceleration, install a CUDA-compatible torch build in your environment.

---

## Setup

### 1) Create and activate a virtual environment

Start in your **project folder** (not `C:\Windows\System32`).

#### Windows (PowerShell)

```powershell
cd C:\path\to\ComputerVision
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If `py` is not available, try:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you see `Python was not found`, install Python from [python.org](https://www.python.org/downloads/windows/) and enable **Add python.exe to PATH** during install.

#### Windows (Command Prompt / cmd.exe)

```cmd
cd C:\path\to\ComputerVision
py -m venv .venv
.venv\Scripts\activate.bat
```

#### macOS / Linux (bash/zsh)

```bash
cd /path/to/ComputerVision
python3 -m venv .venv
source .venv/bin/activate
```

After activation, your shell prompt usually shows `(.venv)` at the beginning.

### 2) Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

To leave the virtual environment later:

```bash
deactivate
```

---

## Configuration (`config.yaml`)

Edit the following keys as needed:

- `camera.source`
  - `0` for default webcam
  - or RTSP URL string like `rtsp://user:pass@ip:554/stream1`
- `camera.id`: logical camera identifier
- `zones.scan_zone`: `{x1,y1,x2,y2}` rectangle for scan region
- `zones.bagging_zone`: bagging area rectangle
- `events.clip_duration_sec`: clip buffer length
- `events.storage_dir`: where clips are saved
- `events.api_post_url`: URL for backend alert ingestion
- `model.yolo_model`: YOLOv8 model file (e.g., `yolov8n.pt`)
- `model.tracker`: tracker config (e.g., `bytetrack.yaml`)

---

## Run

### 1) Start backend API server

From repo root:

```bash
PYTHONPATH=src python -m scanguard_lite.main_api
```

API default address: `http://127.0.0.1:8000`

### 2) Start CV process (separate terminal)

```bash
PYTHONPATH=src python -m scanguard_lite.main_cv
```

Press `q` in the OpenCV window to stop.

### 3) Open dashboard

In browser:

- `http://127.0.0.1:8000/`

The dashboard loads recent alerts and receives new alerts over WebSocket.

---

## API Endpoints

- `POST /alerts`
  - Body:
    ```json
    {
      "timestamp": 1712345678.123,
      "event_type": "bypass_scan_zone",
      "clip_path": "clips/checkout-cam-01_bypass_scan_zone_...mp4",
      "camera_id": "checkout-cam-01",
      "details": "Item reached bagging zone without passing scan zone"
    }
    ```
- `GET /alerts?limit=50`
- `WebSocket /ws/alerts`

---

## Extending Rule Logic

Add a new behavior rule inside `RuleEngine.evaluate(...)` in `src/scanguard_lite/rules.py`.
For maintainability, each rule should:

1. Use track state + zone info
2. Emit a `SuspiciousEvent`
3. Pass through `_allow_event` to debounce duplicates

---

## Operational Notes

- This MVP uses heuristic scan-event inference (not scanner hardware integration).
- Improve robustness by:
  - training custom YOLO classes (hands, barcodes, checkout items)
  - integrating real barcode scanner events
  - calibrating zones per camera
  - adding unit/integration tests around rule outcomes
