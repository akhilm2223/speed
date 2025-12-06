#!/usr/bin/env python3
"""
Generate Sample Local Court CSV
Creates a realistic CSV file with 1000 speeding violation records
that a local court might upload to the DMV.

Usage:
    python generate_sample_court_csv.py
    python generate_sample_court_csv.py --count 500 --output my_court.csv
"""
import csv
import random
import argparse
from datetime import datetime, timedelta

# =============================================================================
# LOAD NY STATE COORDINATES
# =============================================================================

NY_COORDINATES = []
try:
    with open("new_york_state_coordinates.csv", "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            NY_COORDINATES.append((float(row['lat']), float(row['lon'])))
    print(f"Loaded {len(NY_COORDINATES)} coordinates from new_york_state_coordinates.csv")
except FileNotFoundError:
    print("Warning: new_york_state_coordinates.csv not found. Using default coordinates.")


def get_random_ny_coordinate():
    """Get a random coordinate from the NY state coordinates file."""
    if NY_COORDINATES:
        return random.choice(NY_COORDINATES)
    # Fallback to default
    return (42.5, -75.5)


# =============================================================================
# SAMPLE DATA
# =============================================================================

# NY State counties and their courts
NY_COURTS = [
    ("Suffolk County", "Suffolk County Traffic Court", "Suffolk County PD"),
    ("Nassau County", "Nassau County Traffic Court", "Nassau County PD"),
    ("Westchester County", "Westchester Traffic Court", "Westchester County PD"),
    ("Erie County", "Buffalo City Court", "Buffalo PD"),
    ("Monroe County", "Rochester City Court", "Rochester PD"),
    ("Onondaga County", "Syracuse City Court", "Syracuse PD"),
    ("Albany County", "Albany City Court", "Albany PD"),
    ("Orange County", "Orange County Court", "Orange County Sheriff"),
    ("Rockland County", "Rockland County Court", "Rockland County PD"),
    ("Dutchess County", "Poughkeepsie City Court", "Poughkeepsie PD"),
    ("Saratoga County", "Saratoga Springs City Court", "Saratoga Springs PD"),
    ("Schenectady County", "Schenectady City Court", "Schenectady PD"),
    ("Broome County", "Binghamton City Court", "Binghamton PD"),
    ("Oneida County", "Utica City Court", "Utica PD"),
    ("Niagara County", "Niagara Falls City Court", "Niagara Falls PD"),
    ("Ulster County", "Kingston City Court", "Kingston PD"),
    ("Rensselaer County", "Troy City Court", "Troy PD"),
    ("Chemung County", "Elmira City Court", "Elmira PD"),
    ("Tompkins County", "Ithaca City Court", "Ithaca PD"),
    ("Cayuga County", "Auburn City Court", "Auburn PD"),
]

# Sample addresses by county (approximate locations)
COUNTY_ADDRESSES = {
    "Suffolk County": [
        ("123 Main St, Riverhead", 40.9170, -72.6620),
        ("456 Montauk Hwy, Hampton Bays", 40.8690, -72.5180),
        ("789 Sunrise Hwy, Patchogue", 40.7654, -73.0151),
        ("321 Route 25A, Smithtown", 40.8557, -73.2007),
        ("555 Deer Park Ave, Babylon", 40.6954, -73.3262),
    ],
    "Nassau County": [
        ("100 Old Country Rd, Mineola", 40.7490, -73.6393),
        ("200 Hempstead Tpke, Levittown", 40.7257, -73.5143),
        ("300 Northern Blvd, Great Neck", 40.7865, -73.7285),
        ("400 Merrick Rd, Freeport", 40.6576, -73.5832),
        ("500 Glen Cove Rd, Glen Cove", 40.8623, -73.6332),
    ],
    "Westchester County": [
        ("100 Main St, White Plains", 41.0340, -73.7629),
        ("200 Boston Post Rd, Mamaroneck", 40.9487, -73.7354),
        ("300 Central Ave, Yonkers", 40.9312, -73.8987),
        ("400 Saw Mill River Rd, Elmsford", 41.0551, -73.8201),
        ("500 Route 9, Peekskill", 41.2901, -73.9204),
    ],
}

# Default addresses for counties not in the map
DEFAULT_ADDRESSES = [
    ("Main Street", 42.5, -75.5),
    ("State Route 20", 42.8, -76.0),
    ("Highway 17", 42.1, -74.5),
    ("County Road 1", 43.0, -77.0),
    ("Central Avenue", 42.6, -73.8),
]

FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Christopher", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
    "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Daniel", "Matthew", "Anthony",
    "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin",
    "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey", "Ryan",
    "Jacob", "Gary", "Nicholas", "Eric", "Jonathan", "Stephen", "Larry", "Justin",
    "Scott", "Brandon", "Benjamin", "Samuel", "Raymond", "Gregory", "Frank", "Alexander"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell"
]

# Violation codes and their descriptions
VIOLATION_CODES = [
    ("1180A", "Speeding 1-10 mph over limit"),
    ("1180B", "Speeding 11-20 mph over limit"),
    ("1180C", "Speeding 21-30 mph over limit"),
    ("1180D", "Speeding 31+ mph over limit"),
    ("1180E", "Speeding in school zone"),
    ("1180F", "Speeding in work zone"),
]

# Weighted distribution (more minor violations, fewer severe)
VIOLATION_WEIGHTS = [30, 35, 20, 8, 4, 3]

DISPOSITIONS = ["GUILTY", "NOT GUILTY", "DISMISSED", "PENDING"]
DISPOSITION_WEIGHTS = [60, 15, 10, 15]

PLATE_STATES = ["NY", "NY", "NY", "NY", "NJ", "CT", "PA", "MA"]  # Mostly NY


def generate_license_number():
    """Generate a realistic NY driver license number (9 digits)."""
    return ''.join([str(random.randint(0, 9)) for _ in range(9)])


def generate_plate():
    """Generate a realistic license plate."""
    letters = ''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))
    numbers = ''.join(random.choices('0123456789', k=4))
    return f"{letters}-{numbers}"


def generate_dob():
    """Generate date of birth (age 18-75)."""
    age = random.randint(18, 75)
    year = datetime.now().year - age
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year}-{month:02d}-{day:02d}"


def generate_violation_date():
    """Generate a violation date within the last 2 years."""
    days_ago = random.randint(1, 730)
    date = datetime.now() - timedelta(days=days_ago)
    hour = random.randint(6, 22)
    minute = random.randint(0, 59)
    return date.replace(hour=hour, minute=minute, second=0).strftime("%Y-%m-%d %H:%M:%S")


# Pool of repeat offenders to simulate realistic driver behavior
DRIVER_POOL = []

def get_driver_info():
    """
    Get driver info, either by creating a new driver or reusing an existing one.
    30% chance to reuse a driver (creates repeat offenders).
    """
    # Reuse existing driver (30% chance)
    if DRIVER_POOL and random.random() < 0.30:
        driver = random.choice(DRIVER_POOL)
        return driver
    
    # Create new driver
    driver = {
        "driver_license_number": generate_license_number(),
        "driver_full_name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
        "date_of_birth": generate_dob(),
        "plate_id": generate_plate(),
        "plate_state": random.choice(PLATE_STATES)
    }
    
    # Add to pool (keep pool size manageable, e.g., 500 max)
    DRIVER_POOL.append(driver)
    if len(DRIVER_POOL) > 500:
        DRIVER_POOL.pop(0)  # Remove oldest
        
    return driver


def generate_record(court_info):
    """Generate a single violation record."""
    county, court_name, police_agency = court_info
    
    # Get random coordinates from NY state coordinates file
    lat, lon = get_random_ny_coordinate()
    
    violation_code, _ = random.choices(VIOLATION_CODES, weights=VIOLATION_WEIGHTS)[0]
    disposition = random.choices(DISPOSITIONS, weights=DISPOSITION_WEIGHTS)[0]
    
    # Get driver info (potentially reused)
    driver = get_driver_info()
    
    return {
        "driver_license_number": driver["driver_license_number"],
        "driver_full_name": driver["driver_full_name"],
        "date_of_birth": driver["date_of_birth"],
        "license_state": "NY",
        "plate_id": driver["plate_id"],
        "plate_state": driver["plate_state"],
        "violation_code": violation_code,
        "date_of_violation": generate_violation_date(),
        "disposition": disposition,
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "police_agency": police_agency,
        "ticket_issuer": court_name,
    }


def generate_csv(output_file, count, court_index=None):
    """Generate CSV file with sample court data."""
    # Select a single court for all records
    if court_index is None:
        court_info = random.choice(NY_COURTS)
    else:
        court_info = NY_COURTS[court_index % len(NY_COURTS)]
    
    county, court_name, police_agency = court_info
    print(f"Generating {count} sample court violation records...")
    print(f"Court: {court_name} ({county})")
    
    fieldnames = [
        "driver_license_number", "driver_full_name", "date_of_birth", "license_state",
        "plate_id", "plate_state", "violation_code", "date_of_violation",
        "disposition", "latitude", "longitude", "police_agency", "ticket_issuer"
    ]
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i in range(count):
            record = generate_record(court_info)
            writer.writerow(record)
            
            if (i + 1) % 100 == 0:
                print(f"  Generated {i + 1}/{count} records...")
    
    print(f"\n✓ Created {output_file} with {count} records.")
    print(f"\nCourt: {court_name} ({county})")
    print(f"Police Agency: {police_agency}")
    print(f"\nSample record:")
    print("-" * 50)
    sample = generate_record(court_info)
    for key, value in sample.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate sample court violation CSV")
    parser.add_argument("--count", type=int, default=1000, help="Number of records to generate")
    parser.add_argument("--output", type=str, default="court_violations.csv", help="Output file name")
    parser.add_argument("--court-index", type=int, default=None, help="Index of court to use (0-19). If not specified, randomly selects one.")
    args = parser.parse_args()
    
    generate_csv(args.output, args.count, args.court_index)

