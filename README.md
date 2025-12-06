# 🛡️ NYC ISA Enforcement System

**Intelligent Speed Assistance (ISA) Enforcement Dashboard for NYC DMV**

A government-grade enforcement system that identifies repeat speeders from NYC Open Data and triggers ISA device installation requirements. Built for the NYC Vision Zero initiative.

![Dashboard Preview](docs/dashboard-preview.png)

---

## 🎯 What This System Does

1. **Identifies Repeat Speeders** - Analyzes 32,000+ real NYC speeding violations (Jan-Sep 2025)
2. **Calculates Risk Scores** - Each violation = 3 points. Risk ≥10 = ISA Required
3. **Triggers Enforcement** - DMV officers can send ISA installation notices
4. **Tracks Compliance** - Full audit trail of enforcement actions

---

## 📊 Key Features

### DMV Enforcement Dashboard (`/dmv`)
- **KPI Cards**: ISA-Required drivers, Monitoring, Super Speeders, Cross-Borough violators
- **Enforcement Queue**: Sortable table with risk scores, violation counts, severity breakdown
- **Alert Activity Log**: Real-time feed of enforcement actions
- **One-Click Actions**: Send ISA Notice, Mark Compliant

### Driver Profile Page (`/dmv/drivers/:plateId`)
- **Risk Assessment**: Visual risk bar with ISA threshold marker
- **Signal Cards**: Severity (1180D vs 1180A), Nighttime %, Geography (cross-borough)
- **Violations Timeline**: Full history with HIGH/NIGHT badges
- **Case History**: Audit log of all DMV actions

### Camera Network Map (`/map`)
- **Heatmap**: Violation density across NYC
- **AI Cameras**: Click to simulate YOLO detection
- **Live Detection**: Generates new violations in real-time

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL 14+
- Docker (optional, for database)

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/stop-super-speeders.git
cd stop-super-speeders
```

### 2. Database Setup

**Option A: Docker (Recommended)**
```bash
docker run -d \
  --name postgres-isa \
  -e POSTGRES_USER=myuser \
  -e POSTGRES_PASSWORD=mypassword \
  -e POSTGRES_DB=traffic_violations_db \
  -p 5433:5432 \
  postgres:14-alpine
```

**Option B: Local PostgreSQL**
```bash
createdb traffic_violations_db
```

### 3. Configure Environment

Create `.env` file in project root:
```env
DB_HOST=localhost
DB_PORT=5433
DB_NAME=traffic_violations_db
DB_USER=myuser
DB_PASSWORD=mypassword
```

### 4. Install Dependencies

```bash
# Python backend
pip install -r requirements.txt

# React frontend
cd frontend-react
npm install
cd ..
```

### 5. Load NYC Open Data

```bash
# This fetches ~32,000 real speeding violations from NYC Open Data API
python ingest.py
```

This will:
- Create database tables
- Fetch all speeding violations (code 1180*) from NYC Open Data
- Takes ~2-5 minutes depending on connection

### 6. Setup Cameras (Optional)

```bash
python seed_cameras.py
```

### 7. Start the Application

**Terminal 1 - Backend API:**
```bash
python api.py
```
API runs at: http://localhost:5001

**Terminal 2 - Frontend:**
```bash
cd frontend-react
npm start
```
Frontend runs at: http://localhost:3000

### 8. Open the Dashboard

Navigate to: **http://localhost:3000**

You'll land on the DMV Enforcement Dashboard showing:
- 5 ISA-Required Drivers (risk ≥ 10 points)
- 479 Under Monitoring (risk 5-9 points)
- Full enforcement queue with real NYC plate data

---

## 📁 Project Structure

```
stop-super-speeders/
├── api.py                 # Main Flask API server
├── api_dmv.py             # DMV enforcement endpoints
├── api_cameras.py         # Camera/detection endpoints
├── ingest.py              # NYC Open Data ingestion
├── seed_cameras.py        # Camera location seeder
├── cv_detector.py         # YOLO detection simulation
├── requirements.txt       # Python dependencies
├── .env                   # Environment config (create this)
│
├── sql/
│   ├── schema.sql         # Core database schema
│   ├── ai_schema.sql      # AI detection tables
│   └── dmv_schema.sql     # DMV enforcement tables
│
└── frontend-react/
    ├── package.json
    ├── public/
    │   └── *.mp4          # Demo videos for cameras
    └── src/
        ├── pages/
        │   ├── DMVDashboard.jsx   # Main dashboard
        │   ├── DriverProfile.jsx  # Driver case view
        │   └── MapView.jsx        # Camera heatmap
        ├── components/
        │   ├── CameraModal.jsx    # Detection modal
        │   └── CameraMarker.jsx   # Map markers
        └── styles/
            └── dmv.css            # Government UI theme
```

---

## 🔌 API Endpoints

### DMV Enforcement
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dmv/dashboard` | GET | KPIs + enforcement queue |
| `/api/dmv/drivers/<plate_id>` | GET | Full driver profile |
| `/api/dmv/alerts` | GET | Alert activity feed |
| `/api/dmv/alerts/send` | POST | Send ISA notice |
| `/api/dmv/alerts/<id>/comply` | POST | Mark compliant |

### Cameras & Detection
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | All camera locations |
| `/api/cameras/<id>/detect` | POST | Trigger AI detection |
| `/api/heatmap` | GET | Violation heatmap data |

---

## 📈 Risk Calculation

```
Risk Points = Violation Count × 3

Status Thresholds:
- OK:           < 5 points
- MONITORING:   5-9 points  
- ISA_REQUIRED: ≥ 10 points (triggers enforcement)
```

### Data Signals
- **Severity**: 1180D (high-tier) vs 1180A (low-tier) speeding codes
- **Nighttime**: Violations between 10pm-4am (higher crash risk)
- **Cross-Borough**: Drivers speeding in multiple NYC boroughs
- **Super Speeders**: Drivers with 3+ violations

---

## 🎨 UI Design

Government-grade professional theme:
- **Background**: Off-white `#F7F9FB`
- **Primary**: Navy `#0A1A3D`
- **Status Colors**:
  - OK: Gray-Green `#3E6D45`
  - Monitoring: Amber `#C98F00`
  - ISA Required: Red `#B0181A`

---

## 🧪 Demo Flow (For Judges)

1. **Start on Dashboard** → Point to 5 ISA-required drivers
2. **Click LSE6701** → Show driver profile with 15 risk points
3. **Click "Send ISA Notice"** → Watch alert appear in feed
4. **Go to Map** → Click Times Square camera
5. **Run YOLO Detection** → New violations generated
6. **Return to Dashboard** → Show updated risk scores

---

## 🔧 Troubleshooting

### Dashboard shows 0s
1. Make sure API is running: `python api.py`
2. Check API works: `curl http://localhost:5001/api/dmv/dashboard`
3. Hard refresh browser: Ctrl+Shift+R

### Database connection errors
1. Check PostgreSQL is running
2. Verify `.env` has correct port (5433 for Docker, 5432 for local)
3. Test connection: `psql -h localhost -p 5433 -U myuser -d traffic_violations_db`

### No violation data
1. Run ingestion: `python ingest.py`
2. Check data: `SELECT COUNT(*) FROM violations;` (should be ~32,000)

---

## 📜 Data Source

**NYC Open Data - Police Stop Speeding Violations**
- API: https://data.cityofnewyork.us/resource/57p3-pdcj.json
- Violation codes: 1180A, 1180D (speeding)
- Date range: January 2025 - September 2025
- ~32,697 violations from real NYC enforcement

---

## 🏆 Built For

NYC Vision Zero Hackathon - ISA Enforcement Challenge

**Goal**: Identify repeat speeders and mandate Intelligent Speed Assistance (ISA) device installation to reduce traffic fatalities.

---

## 📄 License

MIT License - See LICENSE file

---

## 👥 Team

Built with ❤️ for safer NYC streets
