# 🛡️ NY State ISA Enforcement System

**Intelligent Speed Assistance (ISA) Enforcement Dashboard for NY DMV**

A government-grade enforcement system that identifies repeat speeders from NYC Open Data + NY State violations and triggers ISA device installation requirements. Built for the Vision Zero initiative.

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

### 5. Load Data

```bash
# Step 1: Ingest real NYC Open Data (100k violations)
python ingest.py

# Step 2: Add NY State synthetic violations (100k, uses coordinates CSV)
python generate_ny_state_violations.py

# Step 3: Setup AI cameras schema (optional, for camera demo)
python seed_cameras.py
```

**Data Pipeline:**
- `ingest.py` - Fetches 100k real NYC speeding violations from 2 NYC Open Data APIs:
  - **Moving Violation Summons** (`57p3-pdcj`) - Contains plate numbers and registration states
  - **Moving Violation B Summons Historic** (`bme5-7ty4`) - Historic data (plates generated synthetically)
  - Filters for speeding violations (codes 1180A, 1180B, 1180C, 1180D, 1180E, 1180F)
  - Validates coordinates and generates NY-style plates for records missing plate data
- `generate_ny_state_violations.py` - Fetches 100k **real** NY State violations from data.ny.gov API:
  - **API**: `https://data.ny.gov/resource/q4hy-kbtf.json` (10M+ traffic tickets)
  - **Real Data Fields (from API):**
    - Violation codes (1180A, 1180B, 1180C, 1180D, 1180D12, 1180D13, etc.)
    - Violation descriptions ("SPEED IN ZONE 31+", "SPEED IN ZONE 11-30", etc.)
    - Year, month, day of week
    - Driver age at violation
    - Gender (M/F/U)
    - State of license (NY, NJ, CA, etc.)
    - Police agency (NYC POLICE DEPT, NYS Troopers, etc.)
    - Court (BRONX TVB, BROOKLYN SOUTH TVB, RICHMOND TVB, etc.)
    - Source (TVB, TSLED)
  - **Synthetic Data Added:**
    - License plates (random NY formats: ABC1234, 123ABC, AB-1234)
    - Coordinates (from `new_york_state_coordinates.csv`)
    - 5% repeat offenders (reuses plates for multi-violation drivers)
- `seed_cameras.py` - Seeds camera locations for AI detection demo

### 6. Start the Application

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

### 7. Open the Dashboard

Navigate to: **http://localhost:3000**

You'll see the DMV Enforcement Dashboard with:
- KPIs computed from all 200k violations
- Top 5,000 highest-risk drivers in the enforcement queue
- Ticket issuer (NYC Dept of Finance vs local courts)

---

## 🎯 What This System Does

1. **Identifies Repeat Speeders** - Analyzes 200,000 speeding violations (100k NYC real data + 100k NY State synthetic)
2. **Calculates Risk Scores** - Points based on violation severity (1180A=2pts, 1180B=3pts, 1180C=5pts, 1180D=8pts)
3. **Triggers ISA Enforcement** - Two legal thresholds: **11+ points** OR **16+ speeding tickets**
4. **Tracks Compliance** - Full audit trail of enforcement actions

---

## 📊 Key Metrics (From Full Dataset)

| Metric | Count | Description |
|--------|-------|-------------|
| **Total Violations** | 200,000 | NYC Open Data + NY State synthetic |
| **Unique Drivers** | ~193,000 | Distinct plate/state combinations |
| **ISA Required** | ~3,578 | Meet enforcement threshold |
| **Under Monitoring** | ~106,320 | 6-10 risk points |
| **Super Speeders** | ~166 | 3+ violations |

---

## 📊 Key Features

### DMV Enforcement Dashboard (`/dmv`)
- **KPI Cards**: ISA-Required drivers, Monitoring, Super Speeders, Cross-Borough violators (computed from ALL data)
- **Enforcement Queue**: Top 5,000 highest-risk drivers with risk scores, violation counts, severity breakdown
- **Ticket Issuer Column**: Shows "NYC Dept of Finance" for NYC violations, local court names for upstate
- **Alert Activity Log**: Real-time feed of enforcement actions
- **One-Click Actions**: Send ISA Notice, Mark Compliant

### Driver Profile Page (`/dmv/drivers/:plateId`)
- **Risk Assessment**: Visual risk bar with ISA threshold marker
- **Signal Cards**: Severity (1180D vs 1180A), Nighttime %, Geography (cross-borough)
- **Violations Timeline**: Full history with HIGH/NIGHT badges
- **Case History**: Audit log of all DMV actions

### NY State Violation Map (`/map`)
- **200k Points**: Canvas-rendered for high performance
- **Color-Coded Severity**: Blue (1-10 mph), Yellow (11-20), Orange (21-30), Red (31+ mph)
- **Click-to-Inspect**: Click any point to see violation details (plate, date, agency, court)
- **Full NY State Coverage**: NYC + upstate violations

---

## 📁 Project Structure

```
stop-super-speeders/
├── api.py                          # Main Flask API server
├── api_dmv.py                      # DMV enforcement endpoints (Blueprint)
├── ingest.py                       # NYC Open Data ingestion (100k)
├── generate_ny_state_violations.py # NY State synthetic data (100k)
├── seed_cameras.py                 # Camera location seeder
├── cv_detector.py                  # YOLO detection simulation
├── requirements.txt                # Python dependencies
├── .env                            # Environment config (create this)
│
├── sql/
│   ├── schema.sql                  # Core database schema (vehicles, violations, cameras)
│   └── ai_schema.sql               # AI detection tables (drivers, ai_violations, dmv_alerts)
│
└── frontend-react/
    ├── package.json
    ├── public/
    │   └── *.mp4                   # Demo videos for cameras
    └── src/
        ├── pages/
        │   ├── DMVDashboard.jsx    # Main dashboard (top 5k drivers)
        │   ├── DriverProfile.jsx   # Driver case view
        │   └── MapView.jsx         # NY State violation map (200k points)
        ├── components/
        │   ├── CameraModal.jsx     # Detection modal
        │   └── CameraMarker.jsx    # Map markers
        └── styles/
            └── dmv.css             # Government UI theme
```

---

## 🔌 API Endpoints

### DMV Enforcement
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dmv/dashboard` | GET | KPIs (from all data) + enforcement queue (top 5k) |
| `/api/dmv/drivers/<plate_id>` | GET | Full driver profile |
| `/api/dmv/alerts` | GET | Alert activity feed |
| `/api/dmv/alerts/send` | POST | Send ISA notice |
| `/api/dmv/alerts/<id>/comply` | POST | Mark compliant |

### Map & Heatmap
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/heatmap?limit=300000` | GET | Violation points with severity |
| `/api/cameras` | GET | All camera locations |
| `/api/cameras/<id>/detect` | POST | Trigger AI detection |

---

## 📈 Risk Calculation

### Points by Violation Code
| Code | Description | Points |
|------|-------------|--------|
| 1180A | 1-10 mph over | 2 |
| 1180B | 11-20 mph over | 3 |
| 1180C | 21-30 mph over | 5 |
| 1180D | 31+ mph over | 8 |
| 1180E | School zone | 6 |
| 1180F | Work zone | 6 |

### ISA Enforcement Thresholds
```
ISA REQUIRED if:
  - risk_points >= 11   OR
  - violation_count >= 16

MONITORING if:
  - risk_points >= 6 (but not ISA required)
```

### Ticket Issuer Logic
- **NYC Boroughs** (Manhattan, Brooklyn, Queens, Bronx, Staten Island) → "NYC Dept of Finance"
- **Outside NYC** → Local court name (e.g., "Syracuse City Court", "Buffalo City Court")

---

## 🎨 UI Design

Government-grade professional theme:
- **Background**: Off-white `#F7F9FB`
- **Primary**: Navy `#0A1A3D`
- **Status Colors**:
  - OK: Gray-Green `#3E6D45`
  - Monitoring: Amber `#C98F00`
  - ISA Required: Red `#B0181A`

### Map Violation Colors
- 🔵 Blue: 1-10 mph over (standard)
- 🟡 Yellow: 11-20 mph over (moderate)
- 🟠 Orange: 21-30 mph over (high)
- 🔴 Red: 31+ mph over (severe)

---

## 🧪 Demo Flow (For Judges)

1. **Start on Dashboard** → Show KPIs: 3,578 ISA-required, 106k monitoring
2. **Scroll Queue** → 5,000 drivers with risk scores, ticket issuers
3. **Click a driver** → Show profile with violations timeline
4. **Click "Send ISA Notice"** → Watch alert appear in feed
5. **Go to Map** → Zoom out to see all 200k points across NY State
6. **Click a point** → Show violation details (plate, date, agency, court)
7. **Zoom into NYC** → See dense concentration of real violations

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
2. Run NY State generator: `python generate_ny_state_violations.py`
3. Check data: `SELECT COUNT(*) FROM violations;` (should be ~200,000)

### Map not showing points
1. Check API: `curl "http://localhost:5001/api/heatmap?limit=10"`
2. Should return JSON array with lat/lon/severity

---

## 📜 Data Sources

### NYC Open Data (Real)
- **API**: https://data.cityofnewyork.us/resource/57p3-pdcj.json
- **Violation codes**: 1180A, 1180B, 1180C, 1180D (speeding)
- **Records**: ~100,000 with coordinates

### NY State (Synthetic)
- **Source**: `new_york_state_coordinates.csv` (100k road coordinates)
- **Schema**: Based on data.ny.gov traffic violation fields
- **Fields**: violation_code, police_agency, court, age, gender, etc.

---

## 🏆 Built For

NYC Vision Zero Hackathon - ISA Enforcement Challenge

**Goal**: Identify repeat speeders and mandate Intelligent Speed Assistance (ISA) device installation to reduce traffic fatalities.

**Two Legal Triggers for ISA Device**:
1. **11+ points** on license (from violation severity)
2. **16+ speeding tickets** (regardless of points)

---

## 📄 License

MIT License - See LICENSE file

---

## 👥 Team

Built with ❤️ for safer NY streets
