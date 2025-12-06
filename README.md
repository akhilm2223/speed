# 🛡️ Stop Super Speeders - NY ISA Enforcement System

A comprehensive **Intelligent Speed Assistance (ISA)** enforcement platform for New York State that identifies high-risk drivers and prevents fatal crashes using real statewide traffic violation data.

**Built for the NY State Safe Streets Hackathon**

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

### 4. Load Data
```bash
# Apply database schema
python -c "import psycopg; from dotenv import load_dotenv; import os; load_dotenv(); conn = psycopg.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'), dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD')); cur = conn.cursor(); cur.execute(open('sql/schema.sql').read()); conn.commit(); print('✓ Schema applied')"

# Load NY State violations (default: 500K violations)
python generate_ny_state_violations.py

# Optional: Load more violations for statewide coverage
python generate_ny_state_violations.py --limit 1000000

# Seed AI cameras (for camera detection demo)
python seed_cameras_simple.py
```

**Note:** The data generation script fetches real violations from NY State Open Data API (data.ny.gov). For large datasets (1M+), consider using a SODA API app token for higher rate limits (see `generate_ny_state_violations.py` for details).

### 5. Start Application
```bash
# Terminal 1: Backend
python api.py

# Terminal 2: Frontend (new terminal)
cd frontend-react
npm start
```

### 6. Access Application
| URL | Description |
|-----|-------------|
| **http://localhost:3000/dmv** | 🛡️ DMV Dashboard |
| **http://localhost:3000/map** | 🗺️ Violation Map |
| **http://localhost:3000/dmv/drivers/:plateId** | 👤 Driver Profile |

---

## 🎯 What It Does

- **Identifies high-risk drivers** who meet ISA installation thresholds (11+ points OR 16+ speeding tickets)
- **Calculates crash risk scores** based on violation severity, nighttime patterns, and cross-county behavior
- **Manages DMV enforcement workflow** from detection → notice → compliance
- **Visualizes 700,000+ violations** on an interactive statewide map
- **Integrates AI speed cameras** with real-time violation detection
- **Supports 1,800+ local courts** across all 62 NY counties

---

## 📊 Current Data

| Metric | Count |
|--------|-------|
| **Total Violations** | 700,000+ |
| **High-Risk Drivers** | 15,421 |
| **Counties Covered** | All 62 NY counties |
| **Courts Detected** | 1,800+ local courts |
| **Police Agencies** | 700+ agencies |
| **AI Cameras** | 3 (demo) |

---

## 🔍 How It Works

### 1. Data Ingestion
- Fetches violations from **NY State Open Data** (data.ny.gov)
  - Dataset: Traffic Tickets Issued: Four Year Window (10.7M records, Updated Apr 2025)
  - Covers all 62 counties, 1,800+ courts, 700+ police agencies
- Stores in PostgreSQL with driver info, coordinates, and court data
- Supports CSV upload from local courts via `/courts-upload` page

### 2. Risk Calculation
```python
# ISA Policy Thresholds
ISA_POINTS_THRESHOLD = 11    # ISA required at 11+ points
ISA_TICKET_THRESHOLD = 16    # OR 16+ speeding tickets

# Points Per Violation
1180A = 2 points   # 1-10 mph over
1180B = 3 points   # 11-20 mph over
1180C = 5 points   # 21-30 mph over
1180D = 8 points   # 31+ mph over (SEVERE)

# Crash Risk Formula
Crash Risk = (severity × 60%) + (nighttime × 30%) + (cross-county × 10%)
```

### 3. Enforcement Workflow
```
NEW → NOTICE_SENT → FOLLOW_UP_DUE → COMPLIANT
                                  ↘ ESCALATED
```

### 4. AI Camera Integration
1. YOLO detects vehicle
2. OCR reads license plate
3. Calculates speed violation
4. Logs to database
5. Creates DMV alert if high-risk

---

## 🎨 Key Features

### DMV Dashboard
- **Impact Strip** - Lives saved, pending notices, cross-jurisdiction offenders
- **KPI Cards** - ISA required, monitoring, super speeders
- **County Risk Cards** - Top risk counties, most severe violations
- **Enforcement Queue** - Sortable table with risk badges and batch actions
- **Local Courts Panel** - 1,021 counties, 1,308 courts supported

### Driver Profile
- **Crash Risk Score** - 0-100 with color-coded danger levels
- **Risk Factors** - Severity, nighttime, cross-jurisdiction badges
- **Violation Timeline** - Chronological list with points
- **Enforcement Actions** - Send notice, mark compliant, escalate

### Interactive Map
- **700,000+ violation points** rendered on HTML5 Canvas
- **Color-coded by severity** - Blue (low) → Red (severe)
- **Mode toggle** - Statewide / NYC / Suffolk County views
- **AI camera markers** - Live detection alerts

---

## 📁 Project Structure

```
Stop-Super-Speeders/
├── api.py                          # Main Flask API (heatmap, cameras)
├── api_dmv.py                      # DMV enforcement endpoints
├── isa_policy.py                   # ISA policy & risk calculation
├── generate_ny_state_violations.py # NY State data ingestion
├── ingest.py                       # NYC Open Data ingestion
├── cv_detector.py                  # AI camera detection (YOLO)
├── seed_cameras_simple.py          # Seed camera locations
├── requirements.txt                # Python dependencies
├── .env                            # Database config
│
├── sql/
│   └── schema.sql                  # Database schema
│
└── frontend-react/
    ├── package.json                # Node dependencies
    ├── public/
    │   ├── timesquare.mp4          # Camera feed video
    │   └── data/                   # Static data files
    └── src/
        ├── pages/
        │   ├── DMVDashboard.jsx    # Main dashboard
        │   ├── DriverProfile.jsx   # Driver details
        │   ├── MapView.jsx         # Violation map
        │   └── CourtsUpload.jsx    # CSV upload
        └── components/
            ├── CameraMarker.jsx    # Map camera icons
            ├── CameraModal.jsx      # Video detection modal
            └── DriversSidebar.jsx  # Driver list sidebar
```

---

## 📡 API Endpoints

### DMV Enforcement (`/api/dmv`)
| Endpoint | Description |
|----------|-------------|
| `GET /dashboard` | KPIs, queue, county stats |
| `GET /drivers/<plate_id>` | Driver profile + violations |
| `GET /alerts` | Activity log |
| `POST /alerts/send` | Send ISA notice |
| `POST /alerts/<id>/transition` | Update enforcement status |
| `GET /county-stats` | County-level analytics |
| `GET /impact-metrics` | Lives saved estimates |

### Map & Cameras (`/api`)
| Endpoint | Description |
|----------|-------------|
| `GET /heatmap` | Violation points for map |
| `GET /cameras` | Camera locations |
| `POST /cameras/<id>/detect` | Process AI detection |
| `GET /stats` | Database statistics |



## 🔧 Tech Stack

**Backend:** Flask, PostgreSQL, psycopg, python-dotenv  
**Frontend:** React 18, React Router, Leaflet, HTML5 Canvas  
**Data Sources:** 
- NY State Open Data (data.ny.gov) - Traffic Tickets Issued dataset
- NYC Open Data - Parking violations
- Local court CSV uploads

**AI/CV:** OpenCV, YOLO (simulated for demo)

## 📋 Database Schema

The system uses a unified schema with these main tables:

- **`vehicles`** - License plate registry
- **`violations`** - All violations (manual + AI detected)
- **`driver_license_summary`** - Aggregated driver stats (points, tickets)
- **`ai_violations`** - AI camera detections (linked to violations)
- **`cameras`** - Enforcement camera locations
- **`dmv_alerts`** - ISA enforcement workflow tracking

See `sql/schema.sql` for full schema definition.

## ⚠️ Known Issues & Notes

- **Driver Summary Count:** The `driver_license_summary` table may show high counts if data generation creates too many unique drivers. This is expected with the current data generation approach.
- **Data Volume:** Loading 1M+ violations may take 10-20 minutes depending on API rate limits. Use `--app-token` flag for higher limits.
- **AI Camera Detection:** Currently uses simulated YOLO detection. For production, integrate with real YOLO/OCR models.

---


