#!/usr/bin/env python3
"""
Run database migration for dmv_alerts enforcement lifecycle columns.
"""
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "traffic_violations_db"),
    "user": os.getenv("DB_USER", "myuser"),
    "password": os.getenv("DB_PASSWORD", "mypassword"),
}

MIGRATION_SQL = """
-- Add new columns if they don't exist
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS crash_risk_at_alert DECIMAL(5,2);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS responsible_party VARCHAR(64);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ;
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS enforcement_stage VARCHAR(32);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS court_name VARCHAR(128);
ALTER TABLE dmv_alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
"""

MIGRATION_UPDATES = """
-- Migrate existing statuses to new lifecycle
UPDATE dmv_alerts SET status = 'NOTICE_SENT' WHERE status = 'SENT';
UPDATE dmv_alerts SET enforcement_stage = status WHERE enforcement_stage IS NULL;
UPDATE dmv_alerts SET updated_at = COALESCE(resolved_at, created_at) WHERE updated_at IS NULL;
"""

def run_migration():
    print("Connecting to database...")
    print(f"  Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"  Database: {DB_CONFIG['dbname']}")
    
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("\nRunning migration: Adding new columns...")
        for statement in MIGRATION_SQL.strip().split(';'):
            if statement.strip():
                try:
                    cur.execute(statement)
                    print(f"  ✓ {statement.strip()[:60]}...")
                except Exception as e:
                    print(f"  ⚠ {e}")
        
        conn.commit()
        
        print("\nRunning migration: Updating existing data...")
        for statement in MIGRATION_UPDATES.strip().split(';'):
            if statement.strip():
                try:
                    cur.execute(statement)
                    print(f"  ✓ {statement.strip()[:60]}...")
                except Exception as e:
                    print(f"  ⚠ {e}")
        
        conn.commit()
        
        # Create index
        print("\nCreating index on due_date...")
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_dmv_alerts_due_date ON dmv_alerts(due_date)")
            print("  ✓ Index created")
        except Exception as e:
            print(f"  ⚠ {e}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migration()
