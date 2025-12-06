# 🛡️ Stop Super Speeders - NY ISA Enforcement System

A comprehensive **Intelligent Speed Assistance (ISA)** enforcement platform for New York State that identifies high-risk drivers and prevents fatal crashes using real statewide traffic violation data combined with AI-powered speed camera detection.

**Built for the NY State Safe Streets Hackathon**

---

## 🎯 Project Overview

This system combines:
- **Real NY State violation data** (700,000+ records from data.ny.gov)
- **AI-powered speed cameras** with YOLO vehicle detection
- **Real-time violation screenshots** captured and displayed on map
- **DMV enforcement workflow** for ISA device installation
- **Interactive statewide map** with violation heatmap visualization

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Python 3.9+
- Node.js 16+
- PostgreSQL 13+ (or Docker)

### 1. Clone & Setup
```bash
git clone https://github.com/your-repo/Stop-Super-Speeders.git
cd Stop-Super-Speeders

# Create environment file
cat > .env << EOF
DB_HOST=localhost
DB_PORT=5433
DB_NAME=traffic_violations_db
DB_USER=myuser
DB_PASSWORD=mypassword
EOF
```

### 2. Start Database
```bash
# Using Docker (recommended)
docker run -d --name postgres -p 5433:5432 \
  -e POSTGRES_USER=myuser \
  -e POSTGRES_PASSWORD=mypassword \
  -e POSTGRES_DB=traffic_violations_db \
  postgres:13
```

### 3. Install Dependencies
```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend-react
npm install
cd ..
```

### 4. Initialize Database & Load Data
```bash
# Apply database schema
python -c "import psycopg; from dotenv import load_dotenv; import os; load_dotenv(); conn = psycopg.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'), dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD')); cur = conn.cursor(); cur.execute(open('sql/schema.sql').read()); conn.commit(); print('✓ Schema applied')"

# Load NY State violations (default: 500K violations)
python generate_ny_state_violations.py

# Seed AI cameras
python seed_cameras_simple.py

# Check database status
python check_database.py
```

### 5. Start Application
```bash
# Terminal 1: Backend API
python api.py

# Terminal 2: Frontend (new terminal)
cd frontend-react
npm start
```

### 6. Access Application
| URL | Description |
|-----|-------------|
| **http://localhost:3000/dmv** | 🛡️ DMV Dashboard - Enforcement queue & analytics |
| **http://localhost:3000/map** | 🗺️ Violation Map - Interactive map with AI cameras |
| **http://localhost:3000/courts-upload** | 📤 Court CSV Upload - Bulk violation import |
| **http://localhost:3000/dmv/drivers/:plateId** | 👤 Driver Profile - Individual driver details |

---

## 🎨 Key Features

### 1. Interactive Violation Map (`/map`)
- **700,000+ violation points** rendered on high-performance HTML5 Canvas
- **Color-coded severity**: Blue (1-10 mph over) → Yellow (11-20) → Orange (21-30) → Red (31+ mph over)
- **AI Camera markers** with glowing white icons
- **Click cameras** to view live video feed and run AI detection
- **Violation screenshots** displayed on left panel when camera detects speeders
- **Mode toggle**: Statewide / NYC Only / Suffolk County views

### 2. AI Speed Camera Detection
- **YOLO-based vehicle detection** using YOLOv8
- **Real-time speed estimation** based on vehicle tracking
- **Automatic screenshot capture** with violation details overlay
- **Screenshots include**:
  - License plate (simulated)
  - Speed detected vs speed limit
  - Violation code (1180A-D)
  - Camera location and timestamp
  - Points assessment
- **Screenshots displayed** on map left panel when viewing camera

### 3. DMV Enforcement Dashboard (`/dmv`)
- **Impact Metrics**: Lives saved estimate, pending notices, cross-jurisdiction offenders
- **KPI Cards**: ISA required count, monitoring count, super speeders
- **County Risk Analysis**: Top risk counties with violation counts
- **Enforcement Queue**: Sortable table with risk badges and batch actions
- **Local Courts Panel**: 1,800+ courts supported statewide

### 4. Driver Profile (`/dmv/drivers/:plateId`)
- **Crash Risk Score**: 0-100 with color-coded danger levels
- **Risk Factors**: Severity, nighttime violations, cross-jurisdiction badges
- **Violation Timeline**: Chronological list with points per violation
- **Enforcement Actions**: Send notice, mark compliant, escalate

### 5. Court CSV Upload (`/courts-upload`)
- **Drag-and-drop interface** for CSV file upload
- **Real-time validation** of CSV structure
- **Batch processing** with progress tracking
- **Auto-integration** with driver summaries and ISA alerts

---

## 📁 Project Structure

```
Stop-Super-Speeders/
├── api.py                          # Main Flask API server
├── api_dmv.py                      # DMV enforcement endpoints (Blueprint)
├── isa_policy.py                   # ISA policy rules & risk calculation
├── cv_detector_realtime.py         # AI camera detection with YOLO
├── cv_detector.py                  # Legacy CV detector
├── generate_ny_state_violations.py # NY State data ingestion
├── generate_sample_court_csv.py    # Sample court CSV generator
├── ingest_court_csv.py             # Command-line CSV ingestion
├── ingest.py                       # NYC Open Data ingestion
├── seed_cameras_simple.py          # Seed camera locations
├── check_database.py               # Database status checker
├── requirements.txt                # Python dependencies
├── yolov8n.pt                      # YOLO model weights
├── .env                            # Database configuration
├── new_york_state_coordinates.csv  # NY coordinate data
│
├── snapshots/                      # AI camera violation screenshots
│   └── CAM-X_PLATE_TIMESTAMP.jpg   # Screenshot files
│
├── sql/
│   ├── schema.sql                  # Database schema
│   └── migrate_alerts.sql          # Migration scripts
│
└── frontend-react/
    ├── package.json
    ├── public/
    │   ├── timesquare.mp4          # Camera feed videos
    │   ├── wallstreet.mp4
    │   ├── brooklyn.mp4
    │   └── hudson valley albany.mp4
    └── src/
        ├── index.jsx               # App entry point
        ├── index.css               # Global styles
        ├── App.jsx                 # Router configuration
        ├── pages/
        │   ├── DMVDashboard.jsx    # Main dashboard
        │   ├── DriverProfile.jsx   # Driver details page
        │   ├── MapView.jsx         # Interactive map
        │   └── CourtsUpload.jsx    # CSV upload interface
        └── components/
            ├── CameraMarker.jsx    # Map camera icons
            ├── CameraModal.jsx     # Camera video + screenshots modal
            └── DriversSidebar.jsx  # Driver list sidebar
```

---

## 📡 API Endpoints

### Main API (`api.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/heatmap` | GET | Violation points for map (supports `?limit=N`) |
| `/api/cameras` | GET | All camera locations |
| `/api/cameras/<id>/violations` | GET | Existing violations with screenshots for camera |
| `/api/cameras/<id>/run-detection` | POST | Run AI detection and return new violations |
| `/api/cameras/<id>/detect` | POST | Log a detected violation |
| `/api/recent-violations` | GET | Recent violations with screenshots |
| `/api/stats` | GET | Database statistics |
| `/api/stats/lives-saved` | GET | Lives saved estimate |
| `/snapshots/<filename>` | GET | Serve violation screenshot images |

### DMV API (`api_dmv.py` - Blueprint at `/api/dmv`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | KPIs, queue, county stats |
| `/drivers/<plate_id>` | GET | Driver profile + violations |
| `/alerts` | GET | Activity log |
| `/alerts/send` | POST | Send ISA notice |
| `/alerts/<id>/transition` | POST | Update enforcement status |
| `/county-stats` | GET | County-level analytics |
| `/impact-metrics` | GET | Lives saved estimates |
| `/local-courts/upload` | POST | Upload court CSV file |

---

## 🔧 Technical Details

### ISA Policy Configuration (`isa_policy.py`)

```python
# Points Per Violation Code (NY VTL 1180)
1180A = 2 points   # 1-10 mph over limit
1180B = 3 points   # 11-20 mph over limit
1180C = 5 points   # 21-30 mph over limit
1180D = 8 points   # 31+ mph over limit (SEVERE)
1180E = 6 points   # School zone speeding
1180F = 6 points   # Work zone speeding

# ISA Requirement Thresholds (either triggers ISA)
ISA_POINTS_THRESHOLD = 11    # ISA required at 11+ points
ISA_TICKET_THRESHOLD = 16    # OR 16+ speeding tickets

# Monitoring Band
MONITORING_MIN_POINTS = 6    # Start monitoring at 6 points
```

### Crash Risk Formula

```python
Crash Risk = (severity_factor × 60%) + (nighttime_factor × 30%) + (cross_jurisdiction × 10%)

# Where:
# - severity_factor: normalized points / ISA threshold
# - nighttime_factor: % of violations between 10pm-4am
# - cross_jurisdiction: 1 if multiple boroughs/counties, 0 otherwise
```

### AI Camera Detection (`cv_detector_realtime.py`)

- **Model**: YOLOv8n (nano) for fast inference
- **Vehicle Classes**: Car, Motorcycle, Bus, Truck
- **Speed Estimation**: Pixel displacement over time with calibration
- **Violation Threshold**: Only captures SEVERE violations (20+ mph over limit)
- **Max Violations**: 5 per detection session to prevent duplicates
- **Screenshot Format**: Full frame + info panel with violation details

### Database Schema

| Table | Purpose |
|-------|---------|
| `vehicles` | License plate registry |
| `violations` | All violations (manual + AI detected) |
| `driver_license_summary` | Aggregated driver stats (points, tickets) |
| `ai_violations` | AI camera detections with screenshot paths |
| `cameras` | Enforcement camera locations |
| `dmv_alerts` | ISA enforcement workflow tracking |

---

## 🎥 AI Camera Locations

| Camera ID | Location | Speed Limit | Video |
|-----------|----------|-------------|-------|
| CAM-1 | Times Square, Manhattan | 15 MPH | timesquare.mp4 |
| CAM-2 | Wall Street, Manhattan | 30 MPH | wallstreet.mp4 |
| CAM-3 | Barclays Center, Brooklyn | 30 MPH | brooklyn.mp4 |
| CAM-4 | Hudson Valley, Albany | 55 MPH | hudson valley albany.mp4 |

---

## 📊 Data Sources

1. **NY State Open Data** (data.ny.gov)
   - Dataset: Traffic Tickets Issued: Four Year Window
   - Records: 10.7M+ (we load 500K-1M for demo)
   - Coverage: All 62 NY counties, 1,800+ courts, 700+ police agencies

2. **AI Camera Detection**
   - Real-time YOLO vehicle detection
   - Simulated license plates and speeds
   - Screenshots saved to `/snapshots/` directory

3. **Local Court CSV Upload**
   - Web interface for drag-and-drop upload
   - Command-line tool for batch processing

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Flask, PostgreSQL, psycopg3, python-dotenv |
| **Frontend** | React 18, React Router v6, Leaflet, HTML5 Canvas |
| **AI/CV** | OpenCV, Ultralytics YOLOv8, NumPy |
| **Data** | NY State Open Data API, NYC Open Data |

---

## 📝 Usage Examples

### Run AI Detection on a Camera
```bash
# Command line
python cv_detector_realtime.py --camera-id CAM-3 --video frontend-react/public/brooklyn.mp4 --no-display

# Or click a camera on the map UI
```

### Check Database Status
```bash
python check_database.py
```

### Generate Sample Court CSV
```bash
python generate_sample_court_csv.py --count 1000 --output court_data.csv
```

### Ingest Court CSV
```bash
python ingest_court_csv.py court_data.csv
```

---

## ⚠️ Known Issues & Notes

- **Screenshot Loading**: Screenshots are served from `/snapshots/` directory. Ensure the API server has access to this folder.
- **Detection Time**: AI detection can take 30-60 seconds to process video. The UI shows existing violations first for faster response.
- **Duplicate Prevention**: The CV detector tracks captured plates to prevent multiple screenshots of the same vehicle.
- **Large Datasets**: Loading 1M+ violations may take 10-20 minutes. Use `--app-token` for higher API rate limits.

---

## 🔮 Future Enhancements

- [ ] Real license plate OCR integration
- [ ] Live camera feed support (RTSP streams)
- [ ] Mobile app for field enforcement
- [ ] Integration with NY DMV systems
- [ ] Predictive crash risk modeling
- [ ] Multi-state violation tracking

---

## 📄 License

MIT License - Built for NY State Safe Streets Hackathon

---

## 👥 Contributors

Built with ❤️ for safer New York streets
# speed
