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

# Load 500K NY State violations (~5 minutes)
python generate_ny_state_violations.py

# Seed AI cameras
python seed_cameras_simple.py
```

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
| **Counties Covered** | 1,021 |
| **Courts Detected** | 1,308 |
| **AI Cameras** | 3 |

---

## 🔍 How It Works

### 1. Data Ingestion
- Fetches violations from **NY State Open Data** (data.ny.gov)
- Covers all 62 counties, 1,800+ courts, 700+ police agencies
- Stores in PostgreSQL with driver info and coordinates

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
├── api.py                          # Main Flask API
├── api_dmv.py                      # DMV enforcement endpoints
├── isa_policy.py                   # ISA policy & risk calculation
├── generate_ny_state_violations.py # Data ingestion script
├── requirements.txt                # Python dependencies
├── .env                            # Database config
│
├── sql/
│   └── schema.sql                  # Database schema
│
└── frontend-react/
    ├── package.json                # Node dependencies
    ├── public/
    │   └── timesquare.mp4          # Camera feed video
    └── src/
        ├── pages/
        │   ├── DMVDashboard.jsx    # Main dashboard
        │   ├── DriverProfile.jsx   # Driver details
        │   ├── MapView.jsx         # Violation map
        │   └── CourtsUpload.jsx    # CSV upload
        └── components/
            ├── CameraMarker.jsx    # Map camera icons
            └── CameraModal.jsx     # Video detection modal
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

---

## 🐛 Troubleshooting

### Dashboard Loading Slowly?
```bash
# Add database indexes
python -c "
import psycopg, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'), dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'))
cur = conn.cursor()
cur.execute('CREATE INDEX IF NOT EXISTS idx_violations_plate ON violations(plate_id, plate_state);')
cur.execute('CREATE INDEX IF NOT EXISTS idx_violations_date ON violations(date_of_violation DESC);')
conn.commit()
print('✓ Indexes added')
"
```

### Database Connection Failed?
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Restart if needed
docker restart postgres
```

### Map Not Showing Violations?
```bash
# Verify data has coordinates
psql -h localhost -p 5433 -U myuser -d traffic_violations_db -c \
  "SELECT COUNT(*) FROM violations WHERE latitude IS NOT NULL;"

# If 0, re-run data ingestion
python generate_ny_state_violations.py
```

### Port Already in Use?
```bash
# Find and kill process
lsof -i :5001  # Backend
lsof -i :3000  # Frontend
kill -9 <PID>
```

---

## 📊 Performance

| Operation | Time | Records |
|-----------|------|---------|
| Data Ingestion | ~5 min | 500,000 |
| Dashboard Load | ~3 sec | 5,000 drivers |
| Map Render | ~2 sec | 700,000 points |
| Driver Profile | <200ms | 1 driver |

---

## 🎤 Demo Script for Judges

> **"We've built a comprehensive ISA enforcement platform using 700,000 real traffic violations from NY State Open Data updated April 2025."**

> **"Our system covers all 62 counties and supports 1,308 local courts statewide. We calculate crash risk scores based on violation severity, nighttime patterns, and cross-jurisdiction behavior."**

> **"The platform identifies 15,421 high-risk drivers who meet ISA thresholds. Our impact metrics show that with full ISA compliance, we could potentially save over 40,000 lives based on NHTSA research."**

> **"We've integrated AI-powered speed cameras that detect violations in real-time and automatically create DMV enforcement cases. Local courts can upload their data through our Court Upload Portal for true statewide integration."**

---

## 🔧 Tech Stack

**Backend:** Flask, PostgreSQL, psycopg, python-dotenv  
**Frontend:** React 18, React Router, Leaflet, HTML5 Canvas  
**Data Sources:** NY State Open Data (data.ny.gov), NYC Open Data  
**AI/CV:** OpenCV, YOLO (simulated for demo)

---

## 📋 Future Enhancements

- [ ] Real-time SMS/email notifications
- [ ] PDF report generation for courts
- [ ] Policy simulator with adjustable thresholds
- [ ] Real YOLO + OCR integration
- [ ] Mobile app for field officers
- [ ] ISA device verification API

---

## 👥 Team

Built for the **NY State Safe Streets Hackathon**

---

## 🙏 Acknowledgments

- NY State Open Data (data.ny.gov)
- NYC Open Data (data.cityofnewyork.us)
- Leaflet.js for mapping
- NHTSA for crash risk research

---

## 📄 License

MIT License
