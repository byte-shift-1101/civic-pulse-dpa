import sqlite3
import os
import json
import uuid
from datetime import datetime, timedelta
import random

DB_PATH = "civicpulse.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create Departments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS departments (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        service_area TEXT,
        active INTEGER DEFAULT 1
    );
    """)

    # Create Categories Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        department_id TEXT,
        base_priority_weight REAL DEFAULT 50.0,
        sla_hours INTEGER DEFAULT 48,
        active INTEGER DEFAULT 1,
        FOREIGN KEY (department_id) REFERENCES departments(id)
    );
    """)

    # Create Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        phone TEXT UNIQUE,
        display_name TEXT,
        role TEXT DEFAULT 'citizen', -- citizen, operator, worker, admin
        verified INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    # Create Complaints Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY,
        public_id TEXT UNIQUE NOT NULL,
        reporter_id TEXT,
        reporter_visibility TEXT DEFAULT 'private', -- anonymous, private, public
        source TEXT DEFAULT 'web', -- web, pwa, voice, admin
        description_original TEXT NOT NULL,
        description_summary TEXT,
        category_id TEXT,
        category_confidence REAL DEFAULT 1.0,
        citizen_priority TEXT DEFAULT 'MEDIUM', -- LOW, MEDIUM, HIGH
        system_priority TEXT DEFAULT 'MEDIUM', -- LOW, MEDIUM, HIGH, CRITICAL
        priority_score REAL DEFAULT 0.0,
        priority_explanation TEXT, -- JSON string of breakdown
        status TEXT DEFAULT 'NEW', -- NEW, ASSIGNED, IN_PROGRESS, RESOLVED
        department_id TEXT,
        assignee_id TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        address TEXT,
        landmark TEXT,
        geocoding_confidence TEXT DEFAULT 'HIGH', -- HIGH, MEDIUM, LOW
        created_at TEXT NOT NULL,
        assigned_at TEXT,
        started_at TEXT,
        resolved_at TEXT,
        last_updated_at TEXT NOT NULL,
        upvote_count INTEGER DEFAULT 0,
        follower_count INTEGER DEFAULT 0,
        parent_id TEXT, -- For clubbed/merged complaints
        ai_metadata TEXT, -- JSON string
        resolution_note TEXT,
        resolution_ts TEXT,
        resolution_actor TEXT,
        FOREIGN KEY (category_id) REFERENCES categories(id),
        FOREIGN KEY (department_id) REFERENCES departments(id),
        FOREIGN KEY (assignee_id) REFERENCES users(id),
        FOREIGN KEY (parent_id) REFERENCES complaints(id)
    );
    """)

    # Create Comments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id TEXT PRIMARY KEY,
        complaint_id TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_role TEXT NOT NULL,
        visibility TEXT DEFAULT 'public', -- public, internal
        text TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
        FOREIGN KEY (author_id) REFERENCES users(id)
    );
    """)

    # Create Upvotes Table (to prevent duplicate voting)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS upvotes (
        user_id TEXT NOT NULL,
        complaint_id TEXT NOT NULL,
        PRIMARY KEY (user_id, complaint_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
    );
    """)

    # Create Followers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS followers (
        user_id TEXT NOT NULL,
        complaint_id TEXT NOT NULL,
        PRIMARY KEY (user_id, complaint_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
    );
    """)

    # Create Audit Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_events (
        id TEXT PRIMARY KEY,
        complaint_id TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        actor_role TEXT NOT NULL,
        action TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        reason TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    seed_data(conn)
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()

    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM departments;")
    if cursor.fetchone()[0] > 0:
        return

    print("Seeding database with initial departments, categories, users, and NYC 311-like complaints...")

    # 1. Seed Departments
    departments = [
        ("dept_roads", "Roads & Traffic Department", "Bengaluru Metropolitan Area", 1),
        ("dept_sanitation", "Solid Waste & Sanitation Department", "Bengaluru Metropolitan Area", 1),
        ("dept_electricity", "Street Lighting & Electricity Department", "Bengaluru Metropolitan Area", 1),
        ("dept_water", "Water Supply & Sewerage Board", "Bengaluru Metropolitan Area", 1),
        ("dept_health", "Public Health & Safety Department", "Bengaluru Metropolitan Area", 1)
    ]
    cursor.executemany("INSERT INTO departments VALUES (?, ?, ?, ?);", departments)

    # 2. Seed Categories
    categories = [
        ("cat_pothole", "Pothole & Road Damage", "Potholes, craters, broken asphalt, or road cave-ins.", "dept_roads", 75.0, 36, 1),
        ("cat_garbage", "Garbage Accumulation", "Overflowing bins, illegal dumping, or uncollected waste.", "dept_sanitation", 55.0, 24, 1),
        ("cat_street_light", "Broken Street Light", "Non-functional street lights, dark stretches, or hanging wires.", "dept_electricity", 60.0, 48, 1),
        ("cat_drainage", "Drainage & Waterlogging", "Clogged storm drains, sewage overflow, or street flooding.", "dept_water", 80.0, 24, 1),
        ("cat_water_leak", "Water Pipeline Leakage", "Burst drinking water pipes or continuous water wastage.", "dept_water", 70.0, 12, 1),
        ("cat_traffic_signal", "Broken Traffic Signal", "Malfunctioning traffic lights causing congestion or hazards.", "dept_roads", 90.0, 8, 1),
        ("cat_stray_animals", "Stray Animal Hazard", "Aggressive stray dogs, cattle blocking roads, or carcass removal.", "dept_health", 50.0, 48, 1)
    ]
    cursor.executemany("INSERT INTO categories VALUES (?, ?, ?, ?, ?, ?, ?);", categories)

    # 3. Seed Users (Admins, Operators, Workers, Citizens)
    now_str = datetime.utcnow().isoformat()
    users = [
        ("usr_admin", "+919999999999", "Chief Administrator", "admin", 1, now_str),
        ("usr_operator1", "+918888888888", "Operator Ramesh", "operator", 1, now_str),
        ("usr_worker1", "+917777777777", "Field Engineer Suresh", "worker", 1, now_str),
        ("usr_worker2", "+917777777778", "Sanitation Lead Rajesh", "worker", 1, now_str),
        ("usr_citizen1", "+919876543210", "Aarav Mehta", "citizen", 1, now_str),
        ("usr_citizen2", "+919123456789", "Priya Sharma", "citizen", 1, now_str)
    ]
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?);", users)

    # 4. Seed NYC 311-like complaints mapped to Bengaluru coordinates
    # Center: Bengaluru (12.9716, 77.5946)
    base_lat, base_lng = 12.9716, 77.5946

    seed_complaints = [
        {
            "id": "comp_1",
            "public_id": "CP-2026-1001",
            "reporter_id": "usr_citizen1",
            "reporter_visibility": "private",
            "source": "pwa",
            "description_original": "Huge pothole right in the middle of the main road near MG Road metro station. It is extremely dangerous for two-wheelers, especially at night.",
            "description_summary": "Dangerous pothole near MG Road metro station posing hazard to two-wheelers.",
            "category_id": "cat_pothole",
            "category_confidence": 0.98,
            "citizen_priority": "HIGH",
            "system_priority": "HIGH",
            "priority_score": 82.5,
            "priority_explanation": json.dumps({"age": 20.0, "category": 75.0, "similar": 0.0, "upvotes": 15.0, "cluster": 10.0}),
            "status": "ASSIGNED",
            "department_id": "dept_roads",
            "assignee_id": "usr_worker1",
            "latitude": 12.9752,
            "longitude": 77.6068,
            "address": "MG Road, near Metro Station, Bengaluru",
            "landmark": "MG Road Metro Station",
            "geocoding_confidence": "HIGH",
            "created_at": (datetime.utcnow() - timedelta(hours=18)).isoformat(),
            "assigned_at": (datetime.utcnow() - timedelta(hours=17)).isoformat(),
            "upvote_count": 12,
            "follower_count": 5
        },
        {
            "id": "comp_2",
            "public_id": "CP-2026-1002",
            "reporter_id": "usr_citizen2",
            "reporter_visibility": "public",
            "source": "web",
            "description_original": "Garbage has not been cleared for the last 4 days. The entire corner of 5th Cross Indiranagar is overflowing with plastic bags and food waste. Stray dogs are scattering it everywhere.",
            "description_summary": "Overflowing garbage pile at Indiranagar 5th Cross uncleared for 4 days.",
            "category_id": "cat_garbage",
            "category_confidence": 0.95,
            "citizen_priority": "MEDIUM",
            "system_priority": "HIGH",
            "priority_score": 78.0,
            "priority_explanation": json.dumps({"age": 45.0, "category": 55.0, "similar": 10.0, "upvotes": 8.0, "cluster": 5.0}),
            "status": "IN_PROGRESS",
            "department_id": "dept_sanitation",
            "assignee_id": "usr_worker2",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "address": "5th Cross, Indiranagar, Bengaluru",
            "landmark": "Opposite Corner Bakery",
            "geocoding_confidence": "HIGH",
            "created_at": (datetime.utcnow() - timedelta(hours=36)).isoformat(),
            "assigned_at": (datetime.utcnow() - timedelta(hours=35)).isoformat(),
            "started_at": (datetime.utcnow() - timedelta(hours=34)).isoformat(),
            "upvote_count": 24,
            "follower_count": 11
        },
        {
            "id": "comp_3",
            "public_id": "CP-2026-1003",
            "reporter_id": None,
            "reporter_visibility": "anonymous",
            "source": "voice",
            "description_original": "Hello, I want to report that the street lights are not working on the 80 Feet Road in Koramangala. The entire stretch from the Sony World signal to the next junction is pitch dark. It feels very unsafe for women walking home.",
            "description_summary": "Non-functional street lights on Koramangala 80 Feet Road creating dark, unsafe stretch.",
            "category_id": "cat_street_light",
            "category_confidence": 0.92,
            "citizen_priority": "HIGH",
            "system_priority": "MEDIUM",
            "priority_score": 58.5,
            "priority_explanation": json.dumps({"age": 10.0, "category": 60.0, "similar": 0.0, "upvotes": 0.0, "cluster": 0.0}),
            "status": "NEW",
            "department_id": "dept_electricity",
            "assignee_id": None,
            "latitude": 12.9348,
            "longitude": 77.6224,
            "address": "80 Feet Road, Koramangala, Bengaluru",
            "landmark": "Near Sony World Signal",
            "geocoding_confidence": "MEDIUM",
            "created_at": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
            "upvote_count": 0,
            "follower_count": 0
        },
        {
            "id": "comp_4",
            "public_id": "CP-2026-1004",
            "reporter_id": "usr_citizen1",
            "reporter_visibility": "private",
            "source": "pwa",
            "description_original": "Severe waterlogging after yesterday's rain. The storm drain is completely blocked with silt and plastic. Water has entered the basements of nearby houses.",
            "description_summary": "Blocked storm drain causing severe waterlogging and basement flooding.",
            "category_id": "cat_drainage",
            "category_confidence": 0.97,
            "citizen_priority": "HIGH",
            "system_priority": "CRITICAL",
            "priority_score": 92.0,
            "priority_explanation": json.dumps({"age": 30.0, "category": 80.0, "similar": 20.0, "upvotes": 15.0, "cluster": 15.0}),
            "status": "NEW",
            "department_id": "dept_water",
            "assignee_id": None,
            "latitude": 12.9279,
            "longitude": 77.6271,
            "address": "4th Block, Koramangala, Bengaluru",
            "landmark": "Near Post Office",
            "geocoding_confidence": "HIGH",
            "created_at": (datetime.utcnow() - timedelta(hours=12)).isoformat(),
            "upvote_count": 35,
            "follower_count": 18
        },
        {
            "id": "comp_5",
            "public_id": "CP-2026-1005",
            "reporter_id": "usr_citizen2",
            "reporter_visibility": "private",
            "source": "pwa",
            "description_original": "A huge water pipeline leak on the side of the road. Clean drinking water is gushing out and flooding the street. Thousands of litres are being wasted.",
            "description_summary": "Major drinking water pipeline leak flooding the street.",
            "category_id": "cat_water_leak",
            "category_confidence": 0.99,
            "citizen_priority": "HIGH",
            "system_priority": "HIGH",
            "priority_score": 76.5,
            "priority_explanation": json.dumps({"age": 15.0, "category": 70.0, "similar": 0.0, "upvotes": 5.0, "cluster": 0.0}),
            "status": "RESOLVED",
            "department_id": "dept_water",
            "assignee_id": "usr_worker1",
            "latitude": 12.9592,
            "longitude": 77.5731,
            "address": "Jayanagar 3rd Block, Bengaluru",
            "landmark": "Near Shalini Ground",
            "geocoding_confidence": "HIGH",
            "created_at": (datetime.utcnow() - timedelta(hours=24)).isoformat(),
            "assigned_at": (datetime.utcnow() - timedelta(hours=23)).isoformat(),
            "started_at": (datetime.utcnow() - timedelta(hours=22)).isoformat(),
            "resolved_at": (datetime.utcnow() - timedelta(hours=20)).isoformat(),
            "upvote_count": 8,
            "follower_count": 2,
            "resolution_note": "The main distribution valve was damaged. Our team replaced the gasket and welded the joint. Leakage has been completely stopped.",
            "resolution_ts": (datetime.utcnow() - timedelta(hours=20)).isoformat(),
            "resolution_actor": "usr_worker1"
        }
    ]

    for comp in seed_complaints:
        comp.setdefault("assigned_at", None)
        comp.setdefault("started_at", None)
        comp.setdefault("resolved_at", None)
        comp.setdefault("last_updated_at", comp.get("created_at"))
        comp.setdefault("resolution_note", None)
        comp.setdefault("resolution_ts", None)
        comp.setdefault("resolution_actor", None)

        cursor.execute("""
        INSERT INTO complaints (
            id, public_id, reporter_id, reporter_visibility, source,
            description_original, description_summary, category_id, category_confidence,
            citizen_priority, system_priority, priority_score, priority_explanation,
            status, department_id, assignee_id, latitude, longitude, address, landmark,
            geocoding_confidence, created_at, assigned_at, started_at, resolved_at,
            last_updated_at, upvote_count, follower_count, resolution_note, resolution_ts, resolution_actor
        ) VALUES (
            :id, :public_id, :reporter_id, :reporter_visibility, :source,
            :description_original, :description_summary, :category_id, :category_confidence,
            :citizen_priority, :system_priority, :priority_score, :priority_explanation,
            :status, :department_id, :assignee_id, :latitude, :longitude, :address, :landmark,
            :geocoding_confidence, :created_at, :assigned_at, :started_at, :resolved_at,
            :last_updated_at, :upvote_count, :follower_count, :resolution_note, :resolution_ts, :resolution_actor
        );
        """, comp)

        # Seed some comments
        if comp["id"] == "comp_1":
            cursor.execute("""
            INSERT INTO comments VALUES (
                'comm_1', 'comp_1', 'usr_operator1', 'operator', 'internal',
                'Assigned to Suresh from Roads dept. High priority due to metro traffic.',
                ?
            );
            """, [(datetime.utcnow() - timedelta(hours=17)).isoformat()])
            cursor.execute("""
            INSERT INTO comments VALUES (
                'comm_2', 'comp_1', 'usr_worker1', 'worker', 'public',
                'We have scheduled the asphalt patching for tomorrow morning. Temporary barricades have been placed.',
                ?
            );
            """, [(datetime.utcnow() - timedelta(hours=16)).isoformat()])

        if comp["id"] == "comp_2":
            cursor.execute("""
            INSERT INTO comments VALUES (
                'comm_3', 'comp_2', 'usr_worker2', 'worker', 'public',
                'Sanitation truck is on its way to clear the pile. Will update once cleared.',
                ?
            );
            """, [(datetime.utcnow() - timedelta(hours=34)).isoformat()])

        # Seed upvotes
        for i in range(comp["upvote_count"]):
            user_id = f"usr_citizen_gen_{i}"
            # Create dummy user if not exists
            cursor.execute("INSERT OR IGNORE INTO users VALUES (?, NULL, ?, 'citizen', 0, ?);", 
                           (user_id, f"Citizen {i+1}", now_str))
            cursor.execute("INSERT INTO upvotes VALUES (?, ?);", (user_id, comp["id"]))

    # Add some nearby complaints to demonstrate clustering/clubbing
    # Let's add another pothole very close to comp_1 (MG Road)
    cursor.execute("""
    INSERT INTO complaints (
        id, public_id, reporter_id, reporter_visibility, source,
        description_original, description_summary, category_id, category_confidence,
        citizen_priority, system_priority, priority_score, priority_explanation,
        status, department_id, assignee_id, latitude, longitude, address, landmark,
        geocoding_confidence, created_at, last_updated_at, upvote_count, follower_count
    ) VALUES (
        'comp_6', 'CP-2026-1006', 'usr_citizen2', 'private', 'pwa',
        'There is a bad road patch and a deep pothole near the MG Road metro pillar 120. It is causing traffic slowdown.',
        'Pothole near MG Road metro pillar 120 causing traffic slowdown.', 'cat_pothole', 0.95,
        'MEDIUM', 'HIGH', 70.0, '{}',
        'NEW', 'dept_roads', NULL, 12.9754, 77.6071, 'MG Road, Pillar 120, Bengaluru', 'Metro Pillar 120',
        'HIGH', ?, ?, 3, 1
    );
    """, [(datetime.utcnow() - timedelta(hours=2)).isoformat(), (datetime.utcnow() - timedelta(hours=2)).isoformat()])

    conn.commit()
