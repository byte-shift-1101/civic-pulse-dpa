import os
import json
import uuid
import random
import sqlite3
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, Header, Query, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.database import get_db_connection, init_db
from backend.app.services import GeocodingService, AIService, PrioritizationEngine, SimilarityService

app = FastAPI(
    title="CivicPulse - Smart Civic Complaint & Issue Management System",
    description="FastAPI backend with embedded PWA frontend",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()

# --- Pydantic Models ---
class OTPRequest(BaseModel):
    phone: str

class OTPVerify(BaseModel):
    phone: str
    otp: str

class ComplaintCreate(BaseModel):
    description: str
    category_id: Optional[str] = None
    citizen_priority: str = "MEDIUM"
    latitude: float
    longitude: float
    address: Optional[str] = None
    landmark: Optional[str] = None
    reporter_visibility: str = "private" # anonymous, private, public
    source: str = "pwa"

class CommentCreate(BaseModel):
    text: str
    visibility: str = "public" # public, internal

class AssignRequest(BaseModel):
    department_id: Optional[str] = None
    assignee_id: Optional[str] = None
    reason: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: str
    resolution_note: Optional[str] = None
    reason: Optional[str] = None

class MergeRequest(BaseModel):
    parent_id: str
    reason: str

# --- Helper Functions ---
def get_user_by_id(user_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def log_audit_event(complaint_id: str, actor_id: str, actor_role: str, action: str, old_val: str = None, new_val: str = None, reason: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO audit_events (id, complaint_id, actor_id, actor_role, action, old_value, new_value, reason, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        f"audit_{uuid.uuid4().hex[:8]}",
        complaint_id,
        actor_id,
        actor_role,
        action,
        old_val,
        new_val,
        reason,
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

# --- API Endpoints ---

# 1. Authentication
@app.post("/api/v1/auth/request-otp")
def request_otp(payload: OTPRequest):
    # Mock OTP generation
    return {"message": "OTP sent successfully", "otp": "123456"}

@app.post("/api/v1/auth/verify-otp")
def verify_otp(payload: OTPVerify):
    if payload.otp != "123456":
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone = ?;", (payload.phone,))
    user = cursor.fetchone()
    
    if not user:
        # Create new citizen user
        user_id = f"usr_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO users (id, phone, display_name, role, verified, created_at)
            VALUES (?, ?, ?, 'citizen', 1, ?);
        """, (user_id, payload.phone, f"Citizen {payload.phone[-4:]}", datetime.utcnow().isoformat()))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
        user = cursor.fetchone()
        
    conn.close()
    return {
        "user_id": user["id"],
        "phone": user["phone"],
        "display_name": user["display_name"],
        "role": user["role"]
    }

@app.get("/api/v1/auth/me")
def auth_me(x_user_id: Optional[str] = Header(None)):
    if not x_user_id:
        return {"role": "anonymous", "id": "usr_anonymous"}
    user = get_user_by_id(x_user_id)
    if not user:
        return {"role": "anonymous", "id": "usr_anonymous"}
    return dict(user)

# 2. Metadata
@app.get("/api/v1/departments")
def get_departments():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM departments WHERE active = 1;")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/v1/categories")
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, d.name as department_name 
        FROM categories c
        LEFT JOIN departments d ON c.department_id = d.id
        WHERE c.active = 1;
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# 3. Duplicate Prevention / Relevant Discovery
@app.get("/api/v1/complaints/relevant")
def get_relevant_complaints(
    latitude: float, 
    longitude: float, 
    category_id: str, 
    radius_km: float = 1.0
):
    similar = SimilarityService.find_similar_complaints(latitude, longitude, category_id, radius_km)
    return similar

# 4. Complaints CRUD
@app.post("/api/v1/complaints")
def create_complaint(payload: ComplaintCreate, x_user_id: Optional[str] = Header(None)):
    # 1. AI Analysis
    ai_res = AIService.analyze_complaint(payload.description)
    
    category_id = payload.category_id or ai_res["category_id"]
    summary = ai_res["summary"]
    landmark = payload.landmark or ai_res["landmark"]
    citizen_priority = payload.citizen_priority or ai_res["citizen_priority"]
    
    # 2. Geocoding if address/landmark is missing or coordinates are default
    address = payload.address
    geocoding_confidence = "HIGH"
    
    if not address:
        # Reverse geocode or infer
        geo_res = GeocodingService.geocode(payload.description)
        address = geo_res["address"]
        geocoding_confidence = geo_res["confidence"]
        
    # 3. Find similar complaints to calculate priority score
    similar = SimilarityService.find_similar_complaints(payload.latitude, payload.longitude, category_id, 1.0)
    similar_count = len(similar)
    
    # 4. Calculate Priority
    created_at_str = datetime.utcnow().isoformat()
    score, band, explanation = PrioritizationEngine.calculate_priority(
        category_id, created_at_str, 0, similar_count, citizen_priority
    )
    
    # 5. Determine Department
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT department_id FROM categories WHERE id = ?;", (category_id,))
    cat_row = cursor.fetchone()
    department_id = cat_row["department_id"] if cat_row else "dept_roads"
    
    # 6. Insert Complaint
    complaint_id = f"comp_{uuid.uuid4().hex[:8]}"
    public_id = f"CP-2026-{random.randint(10000, 99999)}"
    
    cursor.execute("""
        INSERT INTO complaints (
            id, public_id, reporter_id, reporter_visibility, source,
            description_original, description_summary, category_id, category_confidence,
            citizen_priority, system_priority, priority_score, priority_explanation,
            status, department_id, assignee_id, latitude, longitude, address, landmark,
            geocoding_confidence, created_at, last_updated_at, upvote_count, follower_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, 0, 0);
    """, (
        complaint_id,
        public_id,
        x_user_id if payload.reporter_visibility != "anonymous" else None,
        payload.reporter_visibility,
        payload.source,
        payload.description,
        summary,
        category_id,
        ai_res.get("category_confidence", 1.0),
        citizen_priority,
        band,
        score,
        explanation,
        "NEW",
        department_id,
        payload.latitude,
        payload.longitude,
        address,
        landmark,
        geocoding_confidence,
        created_at_str,
        created_at_str
    ))
    
    conn.commit()
    conn.close()
    
    # Log Audit Event
    log_audit_event(
        complaint_id, 
        x_user_id or "usr_anonymous", 
        "citizen" if x_user_id else "anonymous", 
        "CREATE", 
        new_val="NEW"
    )
    
    return {"id": complaint_id, "public_id": public_id, "status": "NEW", "priority": band, "score": score}

@app.get("/api/v1/complaints")
def list_complaints(
    status: Optional[str] = None,
    category_id: Optional[str] = None,
    department_id: Optional[str] = None,
    priority: Optional[str] = None,
    reporter_id: Optional[str] = None,
    sort_by: str = "created_at", # created_at, priority_score, upvote_count
    order: str = "desc"
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT c.*, cat.name as category_name, d.name as department_name, u.display_name as assignee_name
        FROM complaints c
        LEFT JOIN categories cat ON c.category_id = cat.id
        LEFT JOIN departments d ON c.department_id = d.id
        LEFT JOIN users u ON c.assignee_id = u.id
        WHERE c.parent_id IS NULL
    """
    params = []
    
    if status:
        query += " AND c.status = ?"
        params.append(status)
    if category_id:
        query += " AND c.category_id = ?"
        params.append(category_id)
    if department_id:
        query += " AND c.department_id = ?"
        params.append(department_id)
    if priority:
        query += " AND c.system_priority = ?"
        params.append(priority)
    if reporter_id:
        query += " AND c.reporter_id = ?"
        params.append(reporter_id)
        
    # Sorting
    allowed_sorts = ["created_at", "priority_score", "upvote_count"]
    if sort_by not in allowed_sorts:
        sort_by = "created_at"
    
    direction = "DESC" if order.lower() == "desc" else "ASC"
    query += f" ORDER BY c.{sort_by} {direction}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]

@app.get("/api/v1/complaints/{id}")
def get_complaint(id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, cat.name as category_name, d.name as department_name, u.display_name as assignee_name
        FROM complaints c
        LEFT JOIN categories cat ON c.category_id = cat.id
        LEFT JOIN departments d ON c.department_id = d.id
        LEFT JOIN users u ON c.assignee_id = u.id
        WHERE c.id = ?;
    """, (id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")
        
    complaint = dict(row)
    
    # Fetch comments
    cursor.execute("""
        SELECT c.*, u.display_name as author_name 
        FROM comments c
        LEFT JOIN users u ON c.author_id = u.id
        WHERE c.complaint_id = ?
        ORDER BY c.created_at ASC;
    """, (id,))
    complaint["comments"] = [dict(r) for r in cursor.fetchall()]
    
    # Fetch child/merged complaints
    cursor.execute("SELECT id, public_id, description_summary, created_at FROM complaints WHERE parent_id = ?;", (id,))
    complaint["merged_complaints"] = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return complaint

# 5. Citizen Actions (Upvote, Follow, Comment)
@app.post("/api/v1/complaints/{id}/upvote")
def upvote_complaint(id: str, x_user_id: str = Header(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO upvotes (user_id, complaint_id) VALUES (?, ?);", (x_user_id, id))
        cursor.execute("UPDATE complaints SET upvote_count = upvote_count + 1 WHERE id = ?;", (id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Already upvoted")
    
    # Recalculate priority score
    cursor.execute("SELECT category_id, created_at, upvote_count, citizen_priority FROM complaints WHERE id = ?;", (id,))
    row = cursor.fetchone()
    if row:
        similar = SimilarityService.find_similar_complaints(0, 0, row["category_id"], 1.0) # dummy coords
        score, band, explanation = PrioritizationEngine.calculate_priority(
            row["category_id"], row["created_at"], row["upvote_count"], len(similar), row["citizen_priority"]
        )
        cursor.execute("""
            UPDATE complaints 
            SET priority_score = ?, system_priority = ?, priority_explanation = ? 
            WHERE id = ?;
        """, (score, band, explanation, id))
        conn.commit()
        
    conn.close()
    return {"message": "Upvoted successfully"}

@app.delete("/api/v1/complaints/{id}/upvote")
def remove_upvote(id: str, x_user_id: str = Header(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM upvotes WHERE user_id = ? AND complaint_id = ?;", (x_user_id, id))
    if cursor.rowcount > 0:
        cursor.execute("UPDATE complaints SET upvote_count = MAX(0, upvote_count - 1) WHERE id = ?;", (id,))
        conn.commit()
    conn.close()
    return {"message": "Upvote removed"}

@app.post("/api/v1/complaints/{id}/follow")
def follow_complaint(id: str, x_user_id: str = Header(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO followers (user_id, complaint_id) VALUES (?, ?);", (x_user_id, id))
        cursor.execute("UPDATE complaints SET follower_count = follower_count + 1 WHERE id = ?;", (id,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Already following")
    conn.close()
    return {"message": "Following successfully"}

@app.delete("/api/v1/complaints/{id}/follow")
def unfollow_complaint(id: str, x_user_id: str = Header(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM followers WHERE user_id = ? AND complaint_id = ?;", (x_user_id, id))
    if cursor.rowcount > 0:
        cursor.execute("UPDATE complaints SET follower_count = MAX(0, follower_count - 1) WHERE id = ?;", (id,))
        conn.commit()
    conn.close()
    return {"message": "Unfollowed successfully"}

@app.post("/api/v1/complaints/{id}/comments")
def add_comment(id: str, payload: CommentCreate, x_user_id: str = Header(...)):
    user = get_user_by_id(x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    comment_id = f"comm_{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat()
    
    cursor.execute("""
        INSERT INTO comments (id, complaint_id, author_id, author_role, visibility, text, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        comment_id,
        id,
        x_user_id,
        user["role"],
        payload.visibility,
        payload.text,
        created_at
    ))
    conn.commit()
    conn.close()
    
    return {"id": comment_id, "created_at": created_at}

# 6. Admin Operations
@app.post("/api/v1/admin/complaints/{id}/assign")
def assign_complaint(id: str, payload: AssignRequest, x_user_id: str = Header(...)):
    admin_user = get_user_by_id(x_user_id)
    if not admin_user or admin_user["role"] not in ["admin", "operator"]:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get old values
    cursor.execute("SELECT department_id, assignee_id, status FROM complaints WHERE id = ?;", (id,))
    old_row = cursor.fetchone()
    if not old_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")
        
    new_status = "ASSIGNED" if old_row["status"] == "NEW" else old_row["status"]
    
    cursor.execute("""
        UPDATE complaints 
        SET department_id = COALESCE(?, department_id),
            assignee_id = COALESCE(?, assignee_id),
            status = ?,
            assigned_at = CASE WHEN assigned_at IS NULL THEN ? ELSE assigned_at END,
            last_updated_at = ?
        WHERE id = ?;
    """, (
        payload.department_id,
        payload.assignee_id,
        new_status,
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat(),
        id
    ))
    conn.commit()
    conn.close()
    
    # Audit logs
    if payload.department_id and payload.department_id != old_row["department_id"]:
        log_audit_event(id, x_user_id, admin_user["role"], "REASSIGN_DEPT", old_row["department_id"], payload.department_id, payload.reason)
    if payload.assignee_id and payload.assignee_id != old_row["assignee_id"]:
        log_audit_event(id, x_user_id, admin_user["role"], "REASSIGN_WORKER", old_row["assignee_id"], payload.assignee_id, payload.reason)
    if new_status != old_row["status"]:
        log_audit_event(id, x_user_id, admin_user["role"], "STATUS_CHANGE", old_row["status"], new_status, "Auto-assigned on worker assignment")
        
    return {"message": "Assignment updated successfully"}

@app.post("/api/v1/admin/complaints/{id}/status")
def update_status(id: str, payload: StatusUpdateRequest, x_user_id: str = Header(...)):
    user = get_user_by_id(x_user_id)
    if not user or user["role"] not in ["admin", "operator", "worker"]:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT status FROM complaints WHERE id = ?;", (id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Complaint not found")
        
    old_status = row["status"]
    new_status = payload.status.upper()
    
    # Validate state machine transitions
    allowed = False
    if old_status == "NEW" and new_status in ["ASSIGNED", "RESOLVED"]:
        allowed = True
    elif old_status == "ASSIGNED" and new_status in ["IN_PROGRESS", "RESOLVED"]:
        allowed = True
    elif old_status == "IN_PROGRESS" and new_status in ["RESOLVED"]:
        allowed = True
    elif old_status == "RESOLVED" and new_status in ["IN_PROGRESS"]: # Reopen
        allowed = True
        
    if not allowed and old_status != new_status:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Invalid status transition from {old_status} to {new_status}")
        
    now_str = datetime.utcnow().isoformat()
    
    if new_status == "IN_PROGRESS":
        cursor.execute("""
            UPDATE complaints 
            SET status = ?, started_at = COALESCE(started_at, ?), last_updated_at = ? 
            WHERE id = ?;
        """, (new_status, now_str, now_str, id))
    elif new_status == "RESOLVED":
        cursor.execute("""
            UPDATE complaints 
            SET status = ?, resolved_at = ?, last_updated_at = ?, 
                resolution_note = ?, resolution_ts = ?, resolution_actor = ?
            WHERE id = ?;
        """, (new_status, now_str, now_str, payload.resolution_note, now_str, x_user_id, id))
    else:
        cursor.execute("UPDATE complaints SET status = ?, last_updated_at = ? WHERE id = ?;", (new_status, now_str, id))
        
    conn.commit()
    conn.close()
    
    log_audit_event(id, x_user_id, user["role"], "STATUS_CHANGE", old_status, new_status, payload.reason or payload.resolution_note)
    return {"message": f"Status updated to {new_status}"}

@app.post("/api/v1/admin/complaints/{id}/merge")
def merge_complaints(id: str, payload: MergeRequest, x_user_id: str = Header(...)):
    user = get_user_by_id(x_user_id)
    if not user or user["role"] not in ["admin", "operator"]:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Verify parent exists
    cursor.execute("SELECT id FROM complaints WHERE id = ?;", (payload.parent_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Parent complaint not found")
        
    # Update child complaint
    cursor.execute("""
        UPDATE complaints 
        SET parent_id = ?, status = 'RESOLVED', 
            resolution_note = ?, resolution_ts = ?, resolution_actor = ?
        WHERE id = ?;
    """, (
        payload.parent_id,
        f"Merged into parent complaint {payload.parent_id}",
        datetime.utcnow().isoformat(),
        x_user_id,
        id
    ))
    conn.commit()
    conn.close()
    
    log_audit_event(id, x_user_id, user["role"], "MERGE", None, payload.parent_id, payload.reason)
    return {"message": "Complaints merged successfully"}

@app.get("/api/v1/admin/audit/{complaint_id}")
def get_audit_trail(complaint_id: str, x_user_id: str = Header(...)):
    user = get_user_by_id(x_user_id)
    if not user or user["role"] not in ["admin", "operator"]:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.*, u.display_name as actor_name 
        FROM audit_events a
        LEFT JOIN users u ON a.actor_id = u.id
        WHERE a.complaint_id = ?
        ORDER BY a.timestamp DESC;
    """, (complaint_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/v1/admin/analytics")
def get_analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Status Distribution
    cursor.execute("SELECT status, COUNT(*) as count FROM complaints GROUP BY status;")
    status_dist = {row["status"]: row["count"] for row in cursor.fetchall()}
    
    # 2. Category Distribution
    cursor.execute("""
        SELECT cat.name, COUNT(c.id) as count 
        FROM complaints c
        JOIN categories cat ON c.category_id = cat.id
        GROUP BY cat.name;
    """)
    category_dist = {row["name"]: row["count"] for row in cursor.fetchall()}
    
    # 3. Priority Distribution
    cursor.execute("SELECT system_priority, COUNT(*) as count FROM complaints GROUP BY system_priority;")
    priority_dist = {row["system_priority"]: row["count"] for row in cursor.fetchall()}
    
    # 4. Department Workload
    cursor.execute("""
        SELECT d.name, COUNT(c.id) as count 
        FROM complaints c
        JOIN departments d ON c.department_id = d.id
        WHERE c.status != 'RESOLVED'
        GROUP BY d.name;
    """)
    dept_workload = {row["name"]: row["count"] for row in cursor.fetchall()}
    
    # 5. Total counts
    cursor.execute("SELECT COUNT(*) FROM complaints;")
    total_complaints = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM complaints WHERE status = 'RESOLVED';")
    resolved_complaints = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total": total_complaints,
        "resolved": resolved_complaints,
        "status_distribution": status_dist,
        "category_distribution": category_dist,
        "priority_distribution": priority_dist,
        "department_workload": dept_workload
    }

# 7. Voice Helpline Webhook Simulator
@app.post("/api/v1/webhooks/voice")
def voice_webhook(payload: dict = Body(...)):
    """
    Simulates a voice call transcript arriving from Vapi/telephony provider.
    Extracts fields using AI/NLP, geocodes, calculates priority, and creates a complaint.
    """
    transcript = payload.get("transcript", "")
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript is required")
        
    # 1. AI Analysis
    ai_res = AIService.analyze_complaint(transcript)
    
    # 2. Geocoding
    geo_res = GeocodingService.geocode(transcript)
    
    # 3. Create Complaint
    conn = get_db_connection()
    cursor = conn.cursor()
    
    category_id = ai_res["category_id"]
    created_at_str = datetime.utcnow().isoformat()
    
    # Find similar
    similar = SimilarityService.find_similar_complaints(geo_res["latitude"], geo_res["longitude"], category_id, 1.0)
    
    # Priority
    score, band, explanation = PrioritizationEngine.calculate_priority(
        category_id, created_at_str, 0, len(similar), ai_res["citizen_priority"]
    )
    
    # Department
    cursor.execute("SELECT department_id FROM categories WHERE id = ?;", (category_id,))
    cat_row = cursor.fetchone()
    department_id = cat_row["department_id"] if cat_row else "dept_roads"
    
    complaint_id = f"comp_{uuid.uuid4().hex[:8]}"
    public_id = f"CP-2026-{random.randint(10000, 99999)}"
    
    cursor.execute("""
        INSERT INTO complaints (
            id, public_id, reporter_id, reporter_visibility, source,
            description_original, description_summary, category_id, category_confidence,
            citizen_priority, system_priority, priority_score, priority_explanation,
            status, department_id, assignee_id, latitude, longitude, address, landmark,
            geocoding_confidence, created_at, last_updated_at, upvote_count, follower_count
        ) VALUES (?, ?, NULL, 'anonymous', 'voice', ?, ?, ?, ?, ?, ?, ?, ?, 'NEW', ?, NULL, ?, ?, ?, ?, ?, ?, ?, 0, 0);
    """, (
        complaint_id,
        public_id,
        transcript,
        ai_res["summary"],
        category_id,
        ai_res.get("category_confidence", 1.0),
        ai_res["citizen_priority"],
        band,
        score,
        explanation,
        department_id,
        geo_res["latitude"],
        geo_res["longitude"],
        geo_res["address"],
        geo_res["landmark"],
        geo_res["confidence"],
        created_at_str,
        created_at_str
    ))
    
    conn.commit()
    conn.close()
    
    log_audit_event(complaint_id, "usr_anonymous", "anonymous", "CREATE_VOICE", new_val="NEW")
    
    return {
        "status": "success",
        "complaint_id": complaint_id,
        "public_id": public_id,
        "extracted_fields": {
            "category_id": category_id,
            "summary": ai_res["summary"],
            "landmark": geo_res["landmark"],
            "address": geo_res["address"],
            "priority": band,
            "score": score
        }
    }

# --- Serve Embedded PWA Frontend ---
@app.get("/", response_class=HTMLResponse)
def serve_pwa():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CivicPulse - Smart Civic Complaint System</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Leaflet CSS & JS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        .leaflet-container { font-family: inherit; }
        body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">

    <!-- Top Navigation Bar -->
    <header class="bg-indigo-600 text-white shadow-md sticky top-0 z-[1000] px-4 py-3 flex items-center justify-between">
        <div class="flex items-center space-x-2">
            <i data-lucide="activity" class="w-6 h-6 text-emerald-400"></i>
            <span class="text-xl font-bold tracking-tight">CivicPulse</span>
        </div>
        <div class="flex items-center space-x-4">
            <!-- Role Switcher -->
            <select id="role-selector" onchange="switchRole()" class="bg-indigo-700 text-white text-xs rounded px-2 py-1 border border-indigo-500 focus:outline-none">
                <option value="usr_citizen1">Citizen (Aarav)</option>
                <option value="usr_operator1">Operator (Ramesh)</option>
                <option value="usr_worker1">Field Worker (Suresh)</option>
                <option value="usr_admin">Admin (Chief)</option>
            </select>
            <div class="relative">
                <button onclick="toggleNotifications()" class="relative p-1 hover:bg-indigo-700 rounded-full transition">
                    <i data-lucide="bell" class="w-5 h-5"></i>
                    <span id="notif-badge" class="absolute top-0 right-0 w-2.5 h-2.5 bg-rose-500 rounded-full hidden"></span>
                </button>
                <!-- Notifications Dropdown -->
                <div id="notif-dropdown" class="absolute right-0 mt-2 w-80 bg-white text-slate-800 rounded-lg shadow-xl border border-slate-100 py-2 hidden z-[1100]">
                    <div class="px-4 py-2 border-b border-slate-100 font-semibold text-sm flex justify-between items-center">
                        <span>Notifications</span>
                        <button onclick="clearNotifications()" class="text-xs text-indigo-600 hover:underline">Clear all</button>
                    </div>
                    <div id="notif-list" class="max-h-64 overflow-y-auto px-2 py-1 text-xs space-y-1">
                        <p class="text-slate-400 text-center py-4">No new notifications</p>
                    </div>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col md:flex-row max-w-7xl w-full mx-auto p-4 gap-4">
        
        <!-- Left Sidebar: Navigation Tabs -->
        <div class="w-full md:w-64 flex flex-row md:flex-col gap-2 bg-white p-2 rounded-xl shadow-sm border border-slate-100 h-fit">
            <button onclick="switchTab('citizen-feed')" class="tab-btn flex-1 md:flex-none flex items-center justify-center md:justify-start space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition bg-indigo-50 text-indigo-600">
                <i data-lucide="map-pin" class="w-5 h-5"></i>
                <span class="hidden md:inline">Citizen Feed</span>
            </button>
            <button onclick="switchTab('report-issue')" class="tab-btn flex-1 md:flex-none flex items-center justify-center md:justify-start space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition text-slate-600 hover:bg-slate-50">
                <i data-lucide="plus-circle" class="w-5 h-5"></i>
                <span class="hidden md:inline">Report Issue</span>
            </button>
            <button onclick="switchTab('admin-portal')" class="tab-btn flex-1 md:flex-none flex items-center justify-center md:justify-start space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition text-slate-600 hover:bg-slate-50">
                <i data-lucide="shield" class="w-5 h-5"></i>
                <span class="hidden md:inline">Admin Portal</span>
            </button>
            <button onclick="switchTab('voice-simulator')" class="tab-btn flex-1 md:flex-none flex items-center justify-center md:justify-start space-x-3 px-4 py-3 rounded-lg text-sm font-medium transition text-slate-600 hover:bg-slate-50">
                <i data-lucide="phone-call" class="w-5 h-5"></i>
                <span class="hidden md:inline">Voice Helpline</span>
            </button>
        </div>

        <!-- Right Content Panel -->
        <div class="flex-1 bg-white rounded-xl shadow-sm border border-slate-100 p-4 md:p-6 min-h-[600px] flex flex-col">
            
            <!-- TAB 1: Citizen Feed -->
            <div id="tab-citizen-feed" class="tab-content space-y-6">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-2xl font-bold text-slate-900">Bengaluru Civic Feed</h2>
                        <p class="text-sm text-slate-500">Explore nearby issues, upvote to support, and track resolutions.</p>
                    </div>
                    <div class="flex items-center space-x-2">
                        <select id="feed-category-filter" onchange="loadCitizenFeed()" class="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                            <option value="">All Categories</option>
                        </select>
                        <select id="feed-sort" onchange="loadCitizenFeed()" class="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                            <option value="created_at">Newest First</option>
                            <option value="priority_score">Highest Priority</option>
                            <option value="upvote_count">Most Upvoted</option>
                        </select>
                    </div>
                </div>

                <!-- Map Container -->
                <div class="relative h-72 w-full rounded-xl overflow-hidden border border-slate-200 shadow-inner">
                    <div id="citizen-map" class="h-full w-full"></div>
                    <div class="absolute bottom-2 left-2 bg-white/90 backdrop-blur px-2 py-1 rounded text-[10px] font-semibold shadow z-[500]">
                        📍 Simulating GPS: Bengaluru Center
                    </div>
                </div>

                <!-- Feed List -->
                <div id="citizen-feed-list" class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Dynamic Cards -->
                </div>
            </div>

            <!-- TAB 2: Report Issue -->
            <div id="tab-report-issue" class="tab-content hidden max-w-2xl mx-auto w-full space-y-6">
                <div>
                    <h2 class="text-2xl font-bold text-slate-900">Report a Civic Issue</h2>
                    <p class="text-sm text-slate-500">Submit details to alert municipal departments. AI will automatically classify and prioritize your report.</p>
                </div>

                <form id="report-form" onsubmit="handleReportSubmit(event)" class="space-y-4">
                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1">Describe the Issue *</label>
                        <textarea id="report-description" required rows="4" oninput="checkDuplicatesDebounced()"
                            placeholder="E.g., There is a huge pothole near MG Road metro station. It is very dangerous for two-wheelers..."
                            class="w-full px-4 py-3 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition text-sm"></textarea>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1">Category (Optional - AI can auto-detect)</label>
                            <select id="report-category" class="w-full px-4 py-2.5 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition text-sm">
                                <option value="">Auto-Detect Category</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1">Your Urgency Level</label>
                            <select id="report-priority" class="w-full px-4 py-2.5 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition text-sm">
                                <option value="LOW">Low (Minor inconvenience)</option>
                                <option value="MEDIUM" selected>Medium (Standard issue)</option>
                                <option value="HIGH">High (Safety hazard / Urgent)</option>
                            </select>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1">Latitude</label>
                            <input type="number" step="any" id="report-lat" required value="12.9716" class="w-full px-4 py-2.5 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition text-sm">
                        </div>
                        <div>
                            <label class="block text-sm font-semibold text-slate-700 mb-1">Longitude</label>
                            <input type="number" step="any" id="report-lng" required value="77.5946" class="w-full px-4 py-2.5 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition text-sm">
                        </div>
                    </div>

                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1">Visibility</label>
                        <select id="report-visibility" class="w-full px-4 py-2.5 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition text-sm">
                            <option value="private">Private (Only admins see my name)</option>
                            <option value="public">Public (Show my name on the feed)</option>
                            <option value="anonymous">Anonymous (Completely hidden)</option>
                        </select>
                    </div>

                    <!-- Duplicate Prevention Alert -->
                    <div id="duplicate-alert" class="hidden bg-amber-50 border border-amber-200 rounded-xl p-4 space-y-3">
                        <div class="flex items-center space-x-2 text-amber-800 font-semibold text-sm">
                            <i data-lucide="alert-triangle" class="w-5 h-5 text-amber-600"></i>
                            <span>Similar Issues Already Reported Nearby!</span>
                        </div>
                        <p class="text-xs text-amber-700">We found existing reports matching your description in this area. You can upvote them to increase priority instead of creating a duplicate.</p>
                        <div id="duplicate-list" class="space-y-2 max-h-40 overflow-y-auto">
                            <!-- Dynamic duplicates -->
                        </div>
                    </div>

                    <button type="submit" class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-lg transition shadow-md hover:shadow-lg flex items-center justify-center space-x-2">
                        <i data-lucide="send" class="w-5 h-5"></i>
                        <span>Submit Complaint</span>
                    </button>
                </form>
            </div>

            <!-- TAB 3: Admin Portal -->
            <div id="tab-admin-portal" class="tab-content hidden space-y-6">
                <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div>
                        <h2 class="text-2xl font-bold text-slate-900">Municipal Operations Dashboard</h2>
                        <p class="text-sm text-slate-500">Monitor city-wide complaints, assign departments, and track SLAs.</p>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <button onclick="loadAdminData()" class="bg-slate-100 hover:bg-slate-200 text-slate-700 px-3 py-2 rounded-lg text-sm font-medium flex items-center space-x-1 transition">
                            <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                            <span>Refresh</span>
                        </button>
                    </div>
                </div>

                <!-- KPI Cards -->
                <div class="grid grid-cols-2 lg:grid-cols-6 gap-4">
                    <div class="bg-indigo-50 border border-indigo-100 p-4 rounded-xl">
                        <p class="text-xs font-semibold text-indigo-600 uppercase tracking-wider">Total Open</p>
                        <p id="kpi-total" class="text-2xl font-bold text-indigo-900 mt-1">0</p>
                    </div>
                    <div class="bg-amber-50 border border-amber-100 p-4 rounded-xl">
                        <p class="text-xs font-semibold text-amber-600 uppercase tracking-wider">New</p>
                        <p id="kpi-new" class="text-2xl font-bold text-amber-900 mt-1">0</p>
                    </div>
                    <div class="bg-blue-50 border border-blue-100 p-4 rounded-xl">
                        <p class="text-xs font-semibold text-blue-600 uppercase tracking-wider">Assigned</p>
                        <p id="kpi-assigned" class="text-2xl font-bold text-blue-900 mt-1">0</p>
                    </div>
                    <div class="bg-purple-50 border border-purple-100 p-4 rounded-xl">
                        <p class="text-xs font-semibold text-purple-600 uppercase tracking-wider">In Progress</p>
                        <p id="kpi-progress" class="text-2xl font-bold text-purple-900 mt-1">0</p>
                    </div>
                    <div class="bg-emerald-50 border border-emerald-100 p-4 rounded-xl">
                        <p class="text-xs font-semibold text-emerald-600 uppercase tracking-wider">Resolved</p>
                        <p id="kpi-resolved" class="text-2xl font-bold text-emerald-900 mt-1">0</p>
                    </div>
                    <div class="bg-rose-50 border border-rose-100 p-4 rounded-xl">
                        <p class="text-xs font-semibold text-rose-600 uppercase tracking-wider">Critical</p>
                        <p id="kpi-critical" class="text-2xl font-bold text-rose-900 mt-1">0</p>
                    </div>
                </div>

                <!-- Admin Map & Queue Split -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <!-- Left: Queue List -->
                    <div class="lg:col-span-2 space-y-4">
                        <div class="flex items-center justify-between">
                            <h3 class="font-bold text-slate-900 flex items-center space-x-2">
                                <i data-lucide="list-todo" class="w-5 h-5 text-indigo-600"></i>
                                <span>Operational Priority Queue</span>
                            </h3>
                            <div class="flex items-center space-x-2">
                                <select id="admin-status-filter" onchange="loadAdminData()" class="bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs">
                                    <option value="">All Statuses</option>
                                    <option value="NEW">NEW</option>
                                    <option value="ASSIGNED">ASSIGNED</option>
                                    <option value="IN_PROGRESS">IN_PROGRESS</option>
                                    <option value="RESOLVED">RESOLVED</option>
                                </select>
                            </div>
                        </div>

                        <div class="border border-slate-100 rounded-xl overflow-hidden bg-white shadow-sm max-h-[500px] overflow-y-auto">
                            <table class="w-full text-left border-collapse text-xs">
                                <thead class="bg-slate-50 text-slate-500 uppercase font-semibold border-b border-slate-100 sticky top-0 z-10">
                                    <tr>
                                        <th class="p-3">ID</th>
                                        <th class="p-3">Category</th>
                                        <th class="p-3">Summary</th>
                                        <th class="p-3">Priority Score</th>
                                        <th class="p-3">Status</th>
                                        <th class="p-3">Action</th>
                                    </tr>
                                </thead>
                                <tbody id="admin-queue-rows" class="divide-y divide-slate-100">
                                    <!-- Dynamic rows -->
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Right: Map & Analytics -->
                    <div class="space-y-4">
                        <h3 class="font-bold text-slate-900 flex items-center space-x-2">
                            <i data-lucide="map" class="w-5 h-5 text-indigo-600"></i>
                            <span>Geographic Clusters</span>
                        </h3>
                        <div class="h-64 w-full rounded-xl overflow-hidden border border-slate-200 shadow-inner">
                            <div id="admin-map" class="h-full w-full"></div>
                        </div>

                        <!-- Simple Analytics Chart Simulation -->
                        <div class="bg-slate-50 border border-slate-100 rounded-xl p-4 space-y-3">
                            <h4 class="text-xs font-bold text-slate-700 uppercase tracking-wider">Department Workload</h4>
                            <div id="analytics-bars" class="space-y-2 text-xs">
                                <!-- Dynamic bars -->
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 4: Voice Helpline Simulator -->
            <div id="tab-voice-simulator" class="tab-content hidden max-w-2xl mx-auto w-full space-y-6">
                <div>
                    <h2 class="text-2xl font-bold text-slate-900">Voice Helpline Simulator</h2>
                    <p class="text-sm text-slate-500">Simulate a citizen calling the 311 helpline. The AI agent transcribes, extracts landmarks, classifies categories, and computes priority in real-time.</p>
                </div>

                <div class="bg-indigo-50 border border-indigo-100 rounded-xl p-4 flex items-start space-x-3">
                    <i data-lucide="info" class="w-5 h-5 text-indigo-600 mt-0.5"></i>
                    <div class="text-xs text-indigo-800 space-y-1">
                        <p class="font-semibold">How to test:</p>
                        <p>1. Select a sample voice script or type your own natural language complaint.</p>
                        <p>2. Click "Simulate Call Intake".</p>
                        <p>3. Watch the AI extract structured fields and geocode the location instantly.</p>
                    </div>
                </div>

                <div class="space-y-3">
                    <label class="block text-sm font-semibold text-slate-700">Select Sample Script</label>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <button onclick="setVoiceScript(1)" class="text-left p-2.5 border border-slate-200 rounded-lg text-xs hover:bg-slate-50 transition">
                            <strong>Pothole near Metro:</strong> "Hello, there is a massive pothole near MG Road metro station. It's causing huge traffic jams..."
                        </button>
                        <button onclick="setVoiceScript(2)" class="text-left p-2.5 border border-slate-200 rounded-lg text-xs hover:bg-slate-50 transition">
                            <strong>Garbage in Indiranagar:</strong> "Hi, garbage has been piling up at 5th Cross Indiranagar for 3 days. The smell is terrible..."
                        </button>
                    </div>
                </div>

                <div class="space-y-4">
                    <div>
                        <label class="block text-sm font-semibold text-slate-700 mb-1">Live Transcript Input</label>
                        <textarea id="voice-transcript" rows="4" class="w-full px-4 py-3 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition text-sm" placeholder="Type what the citizen is saying..."></textarea>
                    </div>

                    <button onclick="submitVoiceSimulation()" class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3 rounded-lg transition shadow-md hover:shadow-lg flex items-center justify-center space-x-2">
                        <i data-lucide="phone-incoming" class="w-5 h-5"></i>
                        <span>Simulate Call Intake</span>
                    </button>
                </div>

                <!-- Simulation Result -->
                <div id="voice-result" class="hidden bg-slate-900 text-slate-100 rounded-xl p-6 space-y-4 font-mono text-xs">
                    <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                        <span class="text-emerald-400 font-bold">✓ CALL PROCESSED SUCCESSFULLY</span>
                        <span id="voice-res-id" class="text-slate-400">ID: -</span>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <p class="text-slate-400">Extracted Category:</p>
                            <p id="voice-res-cat" class="font-bold text-white">-</p>
                        </div>
                        <div>
                            <p class="text-slate-400">Geocoded Landmark:</p>
                            <p id="voice-res-landmark" class="font-bold text-white">-</p>
                        </div>
                        <div>
                            <p class="text-slate-400">Inferred Address:</p>
                            <p id="voice-res-address" class="font-bold text-white">-</p>
                        </div>
                        <div>
                            <p class="text-slate-400">Operational Priority:</p>
                            <p id="voice-res-priority" class="font-bold text-white">-</p>
                        </div>
                    </div>
                    <div class="border-t border-slate-800 pt-2">
                        <p class="text-slate-400">AI Summary:</p>
                        <p id="voice-res-summary" class="text-slate-200 italic mt-1">-</p>
                    </div>
                </div>
            </div>

        </div>
    </main>

    <!-- Complaint Detail Modal -->
    <div id="detail-modal" class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 hidden z-[2000]">
        <div class="bg-white rounded-2xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto flex flex-col">
            <!-- Modal Header -->
            <div class="px-6 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50 rounded-t-2xl">
                <div>
                    <span id="modal-public-id" class="text-xs font-bold bg-indigo-100 text-indigo-800 px-2 py-1 rounded">CP-2026-XXXX</span>
                    <h3 id="modal-category" class="text-lg font-bold text-slate-900 mt-1">Category Name</h3>
                </div>
                <button onclick="closeModal()" class="p-1 hover:bg-slate-200 rounded-full transition">
                    <i data-lucide="x" class="w-6 h-6"></i>
                </button>
            </div>

            <!-- Modal Body -->
            <div class="p-6 space-y-6 flex-1 overflow-y-auto text-sm">
                <!-- Status & Priority Badges -->
                <div class="flex flex-wrap gap-2 items-center">
                    <span id="modal-status" class="px-2.5 py-1 rounded-full text-xs font-bold uppercase">NEW</span>
                    <span id="modal-priority" class="px-2.5 py-1 rounded-full text-xs font-bold uppercase">MEDIUM</span>
                    <span id="modal-score" class="text-xs text-slate-500 font-medium">Priority Score: 0.0</span>
                </div>

                <!-- Description -->
                <div class="space-y-1">
                    <h4 class="font-bold text-slate-900">Original Description</h4>
                    <p id="modal-desc" class="text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100"></p>
                </div>

                <!-- AI Summary -->
                <div class="space-y-1">
                    <h4 class="font-bold text-slate-900 flex items-center space-x-1">
                        <i data-lucide="sparkles" class="w-4 h-4 text-indigo-500"></i>
                        <span>AI Summary</span>
                    </h4>
                    <p id="modal-summary" class="text-slate-600 italic"></p>
                </div>

                <!-- Location Details -->
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div class="space-y-1">
                        <h4 class="font-bold text-slate-900">Address</h4>
                        <p id="modal-address" class="text-slate-600"></p>
                    </div>
                    <div class="space-y-1">
                        <h4 class="font-bold text-slate-900">Landmark</h4>
                        <p id="modal-landmark" class="text-slate-600"></p>
                    </div>
                </div>

                <!-- Priority Explanation (Admin Only) -->
                <div id="modal-priority-explanation-section" class="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-2 hidden">
                    <h4 class="font-bold text-slate-900 flex items-center space-x-1">
                        <i data-lucide="bar-chart-3" class="w-4 h-4 text-indigo-600"></i>
                        <span>Priority Score Breakdown</span>
                    </h4>
                    <div id="modal-priority-breakdown" class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                        <!-- Dynamic breakdown -->
                    </div>
                </div>

                <!-- Admin Controls Section -->
                <div id="modal-admin-controls" class="border-t border-slate-100 pt-4 space-y-4 hidden">
                    <h4 class="font-bold text-slate-900">Operator Actions</h4>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <!-- Assign Department & Worker -->
                        <div class="space-y-2">
                            <label class="block text-xs font-semibold text-slate-600">Assign Department</label>
                            <select id="modal-assign-dept" onchange="handleDeptChange()" class="w-full px-3 py-2 rounded border border-slate-200 text-xs">
                                <!-- Dynamic -->
                            </select>
                            <label class="block text-xs font-semibold text-slate-600 mt-2">Assign Field Worker</label>
                            <select id="modal-assign-worker" class="w-full px-3 py-2 rounded border border-slate-200 text-xs">
                                <option value="">Unassigned</option>
                                <option value="usr_worker1">Field Engineer Suresh</option>
                                <option value="usr_worker2">Sanitation Lead Rajesh</option>
                            </select>
                            <button onclick="submitAssignment()" class="mt-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-3 py-2 rounded transition">
                                Update Assignment
                            </button>
                        </div>

                        <!-- Update Status -->
                        <div class="space-y-2">
                            <label class="block text-xs font-semibold text-slate-600">Update Status</label>
                            <select id="modal-update-status" onchange="toggleResolutionNote()" class="w-full px-3 py-2 rounded border border-slate-200 text-xs">
                                <option value="NEW">NEW</option>
                                <option value="ASSIGNED">ASSIGNED</option>
                                <option value="IN_PROGRESS">IN_PROGRESS</option>
                                <option value="RESOLVED">RESOLVED</option>
                            </select>
                            <div id="modal-resolution-note-container" class="hidden space-y-1">
                                <label class="block text-xs font-semibold text-slate-600">Resolution Note *</label>
                                <textarea id="modal-resolution-note" rows="2" class="w-full px-3 py-2 rounded border border-slate-200 text-xs" placeholder="Describe how the issue was resolved..."></textarea>
                            </div>
                            <button onclick="submitStatusUpdate()" class="bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3 py-2 rounded transition">
                                Update Status
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Comments Section -->
                <div class="border-t border-slate-100 pt-4 space-y-3">
                    <h4 class="font-bold text-slate-900">Updates & Comments</h4>
                    <div id="modal-comments-list" class="space-y-2 max-h-48 overflow-y-auto">
                        <!-- Dynamic comments -->
                    </div>
                    <div class="flex gap-2">
                        <input type="text" id="modal-new-comment" placeholder="Add a public update..." class="flex-1 px-3 py-2 rounded border border-slate-200 text-xs outline-none focus:ring-1 focus:ring-indigo-500">
                        <button onclick="submitComment()" class="bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold px-4 py-2 rounded transition">
                            Send
                        </button>
                    </div>
                </div>

                <!-- Audit Trail (Admin Only) -->
                <div id="modal-audit-section" class="border-t border-slate-100 pt-4 space-y-2 hidden">
                    <h4 class="font-bold text-slate-900">Audit Trail</h4>
                    <div id="modal-audit-list" class="space-y-1 text-xs text-slate-500 max-h-32 overflow-y-auto">
                        <!-- Dynamic audit logs -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="bg-slate-900 text-slate-400 text-center py-6 border-t border-slate-800 text-xs mt-auto">
        <p>© 2026 CivicPulse. Built for DPA Hackathon Stage 2.</p>
    </footer>

    <!-- Frontend Logic -->
    <script>
        let currentUserId = "usr_citizen1";
        let currentUserRole = "citizen";
        let categories = [];
        let departments = [];
        let citizenMap, adminMap;
        let citizenMarkers = [];
        let adminMarkers = [];
        let activeComplaintId = null;
        let notifications = [];

        // Initialize App
        window.addEventListener('DOMContentLoaded', async () => {
            lucide.createIcons();
            await loadMetadata();
            initMaps();
            switchTab('citizen-feed');
        });

        async function loadMetadata() {
            try {
                const catRes = await fetch('/api/v1/categories');
                categories = await catRes.json();
                
                const deptRes = await fetch('/api/v1/departments');
                departments = await deptRes.json();

                // Populate category dropdowns
                const catFilter = document.getElementById('feed-category-filter');
                const catReport = document.getElementById('report-category');
                const modalDept = document.getElementById('modal-assign-dept');

                categories.forEach(cat => {
                    catFilter.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
                    catReport.innerHTML += `<option value="${cat.id}">${cat.name}</option>`;
                });

                departments.forEach(dept => {
                    modalDept.innerHTML += `<option value="${dept.id}">${dept.name}</option>`;
                });
            } catch (err) {
                console.error("Failed to load metadata", err);
            }
        }

        function initMaps() {
            // Center of Bengaluru
            const center = [12.9716, 77.5946];

            citizenMap = L.map('citizen-map').setView(center, 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(citizenMap);

            adminMap = L.map('admin-map').setView(center, 12);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(adminMap);
        }

        function switchRole() {
            const selector = document.getElementById('role-selector');
            currentUserId = selector.value;
            
            if (currentUserId === "usr_citizen1") currentUserRole = "citizen";
            else if (currentUserId === "usr_operator1") currentUserRole = "operator";
            else if (currentUserId === "usr_worker1") currentUserRole = "worker";
            else if (currentUserId === "usr_admin") currentUserRole = "admin";

            addNotification(`Switched role to ${currentUserRole.toUpperCase()}`);
            
            // Refresh active tab
            const activeTab = document.querySelector('.tab-btn.bg-indigo-50').getAttribute('onclick').match(/'([^']+)'/)[1];
            switchTab(activeTab);
        }

        function switchTab(tabId) {
            // Update buttons
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('bg-indigo-50', 'text-indigo-600');
                btn.classList.add('text-slate-600', 'hover:bg-slate-50');
            });

            const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.getAttribute('onclick').includes(tabId));
            if (activeBtn) {
                activeBtn.classList.remove('text-slate-600', 'hover:bg-slate-50');
                activeBtn.classList.add('bg-indigo-50', 'text-indigo-600');
            }

            // Update content panels
            document.querySelectorAll('.tab-content').forEach(content => content.classList.add('hidden'));
            document.getElementById(`tab-${tabId}`).classList.remove('hidden');

            // Trigger map updates
            if (tabId === 'citizen-feed') {
                setTimeout(() => {
                    citizenMap.invalidateSize();
                    loadCitizenFeed();
                }, 100);
            } else if (tabId === 'admin-portal') {
                setTimeout(() => {
                    adminMap.invalidateSize();
                    loadAdminData();
                }, 100);
            }
        }

        // --- Citizen Feed Logic ---
        async function loadCitizenFeed() {
            const catFilter = document.getElementById('feed-category-filter').value;
            const sortBy = document.getElementById('feed-sort').value;

            let url = `/api/v1/complaints?sort_by=${sortBy}`;
            if (catFilter) url += `&category_id=${catFilter}`;

            try {
                const res = await fetch(url);
                const complaints = await res.json();

                // Clear markers
                citizenMarkers.forEach(m => citizenMap.removeLayer(m));
                citizenMarkers = [];

                const feedList = document.getElementById('citizen-feed-list');
                feedList.innerHTML = '';

                if (complaints.length === 0) {
                    feedList.innerHTML = `<p class="text-slate-400 text-center col-span-2 py-8">No complaints found matching filters.</p>`;
                    return;
                }

                complaints.forEach(comp => {
                    // Add marker
                    const markerColor = comp.status === 'RESOLVED' ? '#10b981' : (comp.system_priority === 'CRITICAL' ? '#f43f5e' : '#6366f1');
                    const marker = L.circleMarker([comp.latitude, comp.longitude], {
                        radius: 8,
                        fillColor: markerColor,
                        color: '#fff',
                        weight: 2,
                        fillOpacity: 0.8
                    }).addTo(citizenMap)
                    .bindPopup(`<strong>${comp.public_id}</strong><br>${comp.description_summary}<br><button onclick="openComplaintDetail('${comp.id}')" class="text-indigo-600 font-semibold text-xs mt-1 hover:underline">View Details</button>`);
                    
                    citizenMarkers.push(marker);

                    // Add card
                    const statusColors = {
                        'NEW': 'bg-amber-100 text-amber-800',
                        'ASSIGNED': 'bg-blue-100 text-blue-800',
                        'IN_PROGRESS': 'bg-purple-100 text-purple-800',
                        'RESOLVED': 'bg-emerald-100 text-emerald-800'
                    };

                    const priorityColors = {
                        'LOW': 'bg-slate-100 text-slate-800',
                        'MEDIUM': 'bg-yellow-100 text-yellow-800',
                        'HIGH': 'bg-orange-100 text-orange-800',
                        'CRITICAL': 'bg-rose-100 text-rose-800'
                    };

                    feedList.innerHTML += `
                        <div class="bg-white border border-slate-100 rounded-xl p-4 shadow-sm hover:shadow-md transition flex flex-col justify-between space-y-3">
                            <div class="space-y-2">
                                <div class="flex items-center justify-between">
                                    <span class="text-xs font-bold text-indigo-600">${comp.public_id}</span>
                                    <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full ${statusColors[comp.status]}">${comp.status}</span>
                                </div>
                                <h4 class="font-bold text-slate-900 text-sm">${comp.category_name}</h4>
                                <p class="text-xs text-slate-500 line-clamp-2">${comp.description_summary || comp.description_original}</p>
                                <div class="flex items-center space-x-2 text-[10px] text-slate-400">
                                    <span class="flex items-center"><i data-lucide="map-pin" class="w-3 h-3 mr-1"></i>${comp.landmark || 'Bengaluru'}</span>
                                    <span>•</span>
                                    <span>${new Date(comp.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                            <div class="flex items-center justify-between border-t border-slate-50 pt-3">
                                <span class="text-[10px] font-semibold px-2 py-0.5 rounded ${priorityColors[comp.system_priority]}">${comp.system_priority} Priority</span>
                                <div class="flex items-center space-x-2">
                                    <button onclick="handleUpvote('${comp.id}')" class="flex items-center space-x-1 text-xs text-slate-500 hover:text-indigo-600 transition">
                                        <i data-lucide="thumbs-up" class="w-4 h-4"></i>
                                        <span>${comp.upvote_count}</span>
                                    </button>
                                    <button onclick="openComplaintDetail('${comp.id}')" class="text-xs text-indigo-600 font-semibold hover:underline">
                                        Details
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                });

                lucide.createIcons();
            } catch (err) {
                console.error("Failed to load citizen feed", err);
            }
        }

        // --- Report Issue Logic ---
        let duplicateTimeout;
        function checkDuplicatesDebounced() {
            clearTimeout(duplicateTimeout);
            duplicateTimeout = setTimeout(checkDuplicates, 500);
        }

        async function checkDuplicates() {
            const desc = document.getElementById('report-description').value;
            const lat = parseFloat(document.getElementById('report-lat').value);
            const lng = parseFloat(document.getElementById('report-lng').value);
            const cat = document.getElementById('report-category').value || 'cat_pothole';

            if (desc.length < 15) return;

            try {
                const res = await fetch(`/api/v1/complaints/relevant?latitude=${lat}&longitude=${lng}&category_id=${cat}&radius_km=2.0`);
                const duplicates = await res.json();

                const alertBox = document.getElementById('duplicate-alert');
                const list = document.getElementById('duplicate-list');
                list.innerHTML = '';

                if (duplicates.length > 0) {
                    alertBox.classList.remove('hidden');
                    duplicates.forEach(dup => {
                        list.innerHTML += `
                            <div class="bg-white p-2.5 rounded border border-amber-100 flex justify-between items-center text-xs">
                                <div class="space-y-0.5">
                                    <span class="font-bold text-indigo-600">${dup.public_id}</span>
                                    <p class="text-slate-600 line-clamp-1">${dup.description}</p>
                                    <span class="text-[10px] text-slate-400">${dup.distance_meters}m away</span>
                                </div>
                                <button type="button" onclick="handleUpvote('${dup.id}')" class="bg-indigo-50 hover:bg-indigo-100 text-indigo-600 font-semibold px-2 py-1 rounded transition">
                                    Upvote Existing
                                </button>
                            </div>
                        `;
                    });
                } else {
                    alertBox.classList.add('hidden');
                }
            } catch (err) {
                console.error("Failed to check duplicates", err);
            }
        }

        async function handleReportSubmit(e) {
            e.preventDefault();
            const desc = document.getElementById('report-description').value;
            const cat = document.getElementById('report-category').value;
            const priority = document.getElementById('report-priority').value;
            const lat = parseFloat(document.getElementById('report-lat').value);
            const lng = parseFloat(document.getElementById('report-lng').value);
            const visibility = document.getElementById('report-visibility').value;

            try {
                const res = await fetch('/api/v1/complaints', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-Id': currentUserId
                    },
                    body: JSON.stringify({
                        description: desc,
                        category_id: cat || null,
                        citizen_priority: priority,
                        latitude: lat,
                        longitude: lng,
                        reporter_visibility: visibility,
                        source: 'pwa'
                    })
                });

                const data = await res.json();
                addNotification(`Complaint ${data.public_id} created successfully! Priority: ${data.priority}`);
                
                // Reset form
                document.getElementById('report-form').reset();
                document.getElementById('duplicate-alert').classList.add('hidden');
                
                // Switch to feed
                switchTab('citizen-feed');
            } catch (err) {
                console.error("Failed to submit report", err);
            }
        }

        // --- Admin Portal Logic ---
        async function loadAdminData() {
            const statusFilter = document.getElementById('admin-status-filter').value;
            let url = '/api/v1/complaints?sort_by=priority_score';
            if (statusFilter) url += `&status=${statusFilter}`;

            try {
                // Load Queue
                const res = await fetch(url);
                const complaints = await res.json();

                // Load Analytics
                const analyticsRes = await fetch('/api/v1/admin/analytics');
                const analytics = await analyticsRes.json();

                // Update KPIs
                document.getElementById('kpi-total').innerText = analytics.total || 0;
                document.getElementById('kpi-new').innerText = analytics.status_distribution['NEW'] || 0;
                document.getElementById('kpi-assigned').innerText = analytics.status_distribution['ASSIGNED'] || 0;
                document.getElementById('kpi-progress').innerText = analytics.status_distribution['IN_PROGRESS'] || 0;
                document.getElementById('kpi-resolved').innerText = analytics.resolved || 0;
                document.getElementById('kpi-critical').innerText = analytics.priority_distribution['CRITICAL'] || 0;

                // Populate Queue Rows
                const rowsContainer = document.getElementById('admin-queue-rows');
                rowsContainer.innerHTML = '';

                if (complaints.length === 0) {
                    rowsContainer.innerHTML = `<tr><td colspan="6" class="p-4 text-center text-slate-400">No complaints in queue.</td></tr>`;
                } else {
                    complaints.forEach(comp => {
                        const priorityBadge = comp.system_priority === 'CRITICAL' ? 'bg-rose-100 text-rose-800 font-bold' : (comp.system_priority === 'HIGH' ? 'bg-orange-100 text-orange-800' : 'bg-slate-100 text-slate-800');
                        rowsContainer.innerHTML += `
                            <tr class="hover:bg-slate-50 transition cursor-pointer" onclick="openComplaintDetail('${comp.id}')">
                                <td class="p-3 font-bold text-indigo-600">${comp.public_id}</td>
                                <td class="p-3 font-semibold">${comp.category_name}</td>
                                <td class="p-3 text-slate-600 max-w-xs truncate">${comp.description_summary || comp.description_original}</td>
                                <td class="p-3">
                                    <span class="px-2 py-0.5 rounded text-[10px] ${priorityBadge}">${comp.priority_score} (${comp.system_priority})</span>
                                </td>
                                <td class="p-3 font-semibold text-slate-700">${comp.status}</td>
                                <td class="p-3">
                                    <button class="text-indigo-600 hover:underline font-semibold">Manage</button>
                                </td>
                            </tr>
                        `;
                    });
                }

                // Update Admin Map
                adminMarkers.forEach(m => adminMap.removeLayer(m));
                adminMarkers = [];

                complaints.forEach(comp => {
                    const markerColor = comp.status === 'RESOLVED' ? '#10b981' : (comp.system_priority === 'CRITICAL' ? '#f43f5e' : '#6366f1');
                    const marker = L.circleMarker([comp.latitude, comp.longitude], {
                        radius: 9,
                        fillColor: markerColor,
                        color: '#fff',
                        weight: 2,
                        fillOpacity: 0.9
                    }).addTo(adminMap)
                    .bindPopup(`<strong>${comp.public_id}</strong><br>Priority: ${comp.system_priority}<br>Status: ${comp.status}<br><button onclick="openComplaintDetail('${comp.id}')" class="text-indigo-600 font-semibold text-xs mt-1 hover:underline">Manage</button>`);
                    
                    adminMarkers.push(marker);
                });

                // Populate Workload Analytics
                const barsContainer = document.getElementById('analytics-bars');
                barsContainer.innerHTML = '';
                Object.entries(analytics.department_workload).forEach(([dept, count]) => {
                    const percentage = Math.min(100, (count / Math.max(1, analytics.total)) * 100);
                    barsContainer.innerHTML += `
                        <div class="space-y-1">
                            <div class="flex justify-between text-[10px] font-semibold text-slate-600">
                                <span>${dept}</span>
                                <span>${count} open</span>
                            </div>
                            <div class="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                                <div class="bg-indigo-600 h-full" style="width: ${percentage}%"></div>
                            </div>
                        </div>
                    `;
                });

            } catch (err) {
                console.error("Failed to load admin data", err);
            }
        }

        // --- Complaint Detail Modal ---
        async function openComplaintDetail(id) {
            activeComplaintId = id;
            try {
                const res = await fetch(`/api/v1/complaints/${id}`);
                const comp = await res.json();

                document.getElementById('modal-public-id').innerText = comp.public_id;
                document.getElementById('modal-category').innerText = comp.category_name;
                document.getElementById('modal-desc').innerText = comp.description_original;
                document.getElementById('modal-summary').innerText = comp.description_summary || "No summary generated.";
                document.getElementById('modal-address').innerText = comp.address || "Not specified";
                document.getElementById('modal-landmark').innerText = comp.landmark || "Not specified";
                document.getElementById('modal-status').innerText = comp.status;
                document.getElementById('modal-priority').innerText = comp.system_priority;
                document.getElementById('modal-score').innerText = `Priority Score: ${comp.priority_score}`;

                // Status badge colors
                const statusBadge = document.getElementById('modal-status');
                statusBadge.className = "px-2.5 py-1 rounded-full text-xs font-bold uppercase ";
                if (comp.status === 'NEW') statusBadge.classList.add('bg-amber-100', 'text-amber-800');
                else if (comp.status === 'ASSIGNED') statusBadge.classList.add('bg-blue-100', 'text-blue-800');
                else if (comp.status === 'IN_PROGRESS') statusBadge.classList.add('bg-purple-100', 'text-purple-800');
                else if (comp.status === 'RESOLVED') statusBadge.classList.add('bg-emerald-100', 'text-emerald-800');

                // Priority badge colors
                const priorityBadge = document.getElementById('modal-priority');
                priorityBadge.className = "px-2.5 py-1 rounded-full text-xs font-bold uppercase ";
                if (comp.system_priority === 'CRITICAL') priorityBadge.classList.add('bg-rose-100', 'text-rose-800');
                else if (comp.system_priority === 'HIGH') priorityBadge.classList.add('bg-orange-100', 'text-orange-800');
                else if (comp.system_priority === 'MEDIUM') priorityBadge.classList.add('bg-yellow-100', 'text-yellow-800');
                else priorityBadge.classList.add('bg-slate-100', 'text-slate-800');

                // Show/Hide Admin Controls & Audit Trail
                const adminControls = document.getElementById('modal-admin-controls');
                const auditSection = document.getElementById('modal-audit-section');
                const priorityExplSection = document.getElementById('modal-priority-explanation-section');

                if (['admin', 'operator', 'worker'].includes(currentUserRole)) {
                    adminControls.classList.remove('hidden');
                    auditSection.classList.remove('hidden');
                    priorityExplSection.classList.remove('hidden');

                    // Populate assignment dropdowns
                    document.getElementById('modal-assign-dept').value = comp.department_id || '';
                    document.getElementById('modal-assign-worker').value = comp.assignee_id || '';
                    document.getElementById('modal-update-status').value = comp.status;

                    // Load Audit Trail
                    const auditRes = await fetch(`/api/v1/admin/audit/${id}`, {
                        headers: { 'X-User-Id': currentUserId }
                    });
                    const audits = await auditRes.json();
                    const auditList = document.getElementById('modal-audit-list');
                    auditList.innerHTML = '';
                    if (audits.length === 0) {
                        auditList.innerHTML = `<p class="text-slate-400 italic">No audit events recorded.</p>`;
                    } else {
                        audits.forEach(aud => {
                            auditList.innerHTML += `
                                <div class="py-1 border-b border-slate-50">
                                    <span class="font-semibold text-slate-700">[${aud.action}]</span> 
                                    by ${aud.actor_name || 'System'} 
                                    <span class="text-slate-400">(${new Date(aud.timestamp).toLocaleTimeString()})</span>
                                    ${aud.reason ? `<p class="text-[10px] text-slate-500 italic">Reason: ${aud.reason}</p>` : ''}
                                </div>
                            `;
                        });
                    }

                    // Populate Priority Breakdown
                    const breakdown = JSON.parse(comp.priority_explanation || '{}');
                    const breakdownContainer = document.getElementById('modal-priority-breakdown');
                    breakdownContainer.innerHTML = `
                        <div class="bg-white p-2 rounded border border-slate-100">
                            <p class="text-slate-400">Age</p>
                            <p class="font-bold text-slate-800">+${breakdown.age_contribution || 0}</p>
                        </div>
                        <div class="bg-white p-2 rounded border border-slate-100">
                            <p class="text-slate-400">Category</p>
                            <p class="font-bold text-slate-800">+${breakdown.category_contribution || 0}</p>
                        </div>
                        <div class="bg-white p-2 rounded border border-slate-100">
                            <p class="text-slate-400">Similar</p>
                            <p class="font-bold text-slate-800">+${breakdown.similar_contribution || 0}</p>
                        </div>
                        <div class="bg-white p-2 rounded border border-slate-100">
                            <p class="text-slate-400">Upvotes</p>
                            <p class="font-bold text-slate-800">+${breakdown.upvotes_contribution || 0}</p>
                        </div>
                    `;
                } else {
                    adminControls.classList.add('hidden');
                    auditSection.classList.add('hidden');
                    priorityExplSection.classList.add('hidden');
                }

                // Populate Comments
                const commentsList = document.getElementById('modal-comments-list');
                commentsList.innerHTML = '';
                if (comp.comments.length === 0) {
                    commentsList.innerHTML = `<p class="text-slate-400 italic text-xs">No updates yet.</p>`;
                } else {
                    comp.comments.forEach(comm => {
                        const isInternal = comm.visibility === 'internal';
                        if (isInternal && !['admin', 'operator', 'worker'].includes(currentUserRole)) return;

                        commentsList.innerHTML += `
                            <div class="p-2.5 rounded-lg text-xs ${isInternal ? 'bg-amber-50 border border-amber-100' : 'bg-slate-50 border border-slate-100'}">
                                <div class="flex justify-between font-semibold text-slate-700 mb-1">
                                    <span>${comm.author_name} (${comm.author_role.toUpperCase()})</span>
                                    <span class="text-slate-400">${new Date(comm.created_at).toLocaleTimeString()}</span>
                                </div>
                                <p class="text-slate-600">${comm.text}</p>
                                ${isInternal ? `<span class="text-[9px] font-bold text-amber-700 uppercase tracking-wider mt-1 block">🔒 Internal Note</span>` : ''}
                            </div>
                        `;
                    });
                }

                // Show Modal
                document.getElementById('detail-modal').classList.remove('hidden');
                lucide.createIcons();
            } catch (err) {
                console.error("Failed to load complaint details", err);
            }
        }

        function closeModal() {
            document.getElementById('detail-modal').classList.add('hidden');
            activeComplaintId = null;
        }

        function toggleResolutionNote() {
            const status = document.getElementById('modal-update-status').value;
            const container = document.getElementById('modal-resolution-note-container');
            if (status === 'RESOLVED') {
                container.classList.remove('hidden');
            } else {
                container.classList.add('hidden');
            }
        }

        async function submitAssignment() {
            const deptId = document.getElementById('modal-assign-dept').value;
            const workerId = document.getElementById('modal-assign-worker').value;

            try {
                const res = await fetch(`/api/v1/admin/complaints/${activeComplaintId}/assign`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-Id': currentUserId
                    },
                    body: JSON.stringify({
                        department_id: deptId,
                        assignee_id: workerId || null,
                        reason: "Manual assignment update"
                    })
                });

                if (res.ok) {
                    addNotification(`Assignment updated for complaint.`);
                    openComplaintDetail(activeComplaintId);
                    loadAdminData();
                }
            } catch (err) {
                console.error("Failed to update assignment", err);
            }
        }

        async function submitStatusUpdate() {
            const status = document.getElementById('modal-update-status').value;
            const note = document.getElementById('modal-resolution-note').value;

            if (status === 'RESOLVED' && !note) {
                alert("Resolution note is required to resolve a complaint.");
                return;
            }

            try {
                const res = await fetch(`/api/v1/admin/complaints/${activeComplaintId}/status`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-Id': currentUserId
                    },
                    body: JSON.stringify({
                        status: status,
                        resolution_note: note || null,
                        reason: "Status updated by operator"
                    })
                });

                if (res.ok) {
                    addNotification(`Status updated to ${status}`);
                    openComplaintDetail(activeComplaintId);
                    loadAdminData();
                } else {
                    const err = await res.json();
                    alert(err.detail);
                }
            } catch (err) {
                console.error("Failed to update status", err);
            }
        }

        async function submitComment() {
            const text = document.getElementById('modal-new-comment').value;
            if (!text) return;

            try {
                const res = await fetch(`/api/v1/complaints/${activeComplaintId}/comments`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-User-Id': currentUserId
                    },
                    body: JSON.stringify({
                        text: text,
                        visibility: ['admin', 'operator', 'worker'].includes(currentUserRole) ? 'internal' : 'public'
                    })
                });

                if (res.ok) {
                    document.getElementById('modal-new-comment').value = '';
                    openComplaintDetail(activeComplaintId);
                }
            } catch (err) {
                console.error("Failed to submit comment", err);
            }
        }

        async function handleUpvote(id) {
            try {
                const res = await fetch(`/api/v1/complaints/${id}/upvote`, {
                    method: 'POST',
                    headers: { 'X-User-Id': currentUserId }
                });

                if (res.ok) {
                    addNotification("Upvoted complaint successfully!");
                    loadCitizenFeed();
                    checkDuplicates();
                } else {
                    const err = await res.json();
                    addNotification(err.detail);
                }
            } catch (err) {
                console.error("Failed to upvote", err);
            }
        }

        // --- Voice Helpline Simulator Logic ---
        function setVoiceScript(num) {
            const transcript = document.getElementById('voice-transcript');
            if (num === 1) {
                transcript.value = "Hello, there is a massive pothole right in the middle of the road near MG Road metro station. It is extremely dangerous for two-wheelers, especially at night. Please fix it immediately.";
            } else if (num === 2) {
                transcript.value = "Hi, garbage has been piling up at 5th Cross Indiranagar for the last 4 days. The entire corner is overflowing with plastic bags and food waste. Stray dogs are scattering it everywhere and the smell is terrible.";
            }
        }

        async function submitVoiceSimulation() {
            const transcript = document.getElementById('voice-transcript').value;
            if (!transcript) {
                alert("Please enter a transcript to simulate.");
                return;
            }

            try {
                const res = await fetch('/api/v1/webhooks/voice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ transcript: transcript })
                });

                const data = await res.json();
                if (data.status === 'success') {
                    addNotification(`Voice call processed! Created ${data.public_id}`);
                    
                    // Show result
                    document.getElementById('voice-result').classList.remove('hidden');
                    document.getElementById('voice-res-id').innerText = `ID: ${data.public_id}`;
                    document.getElementById('voice-res-cat').innerText = data.extracted_fields.category_id;
                    document.getElementById('voice-res-landmark').innerText = data.extracted_fields.landmark || "None";
                    document.getElementById('voice-res-address').innerText = data.extracted_fields.address;
                    document.getElementById('voice-res-priority').innerText = `${data.extracted_fields.priority} (${data.extracted_fields.score})`;
                    document.getElementById('voice-res-summary').innerText = `"${data.extracted_fields.summary}"`;
                }
            } catch (err) {
                console.error("Failed to simulate voice call", err);
            }
        }

        // --- Notifications Logic ---
        function toggleNotifications() {
            const dropdown = document.getElementById('notif-dropdown');
            dropdown.classList.toggle('hidden');
        }

        function addNotification(text) {
            notifications.unshift({
                text: text,
                time: new Date().toLocaleTimeString()
            });
            updateNotificationsUI();
        }

        function clearNotifications() {
            notifications = [];
            updateNotificationsUI();
        }

        function updateNotificationsUI() {
            const badge = document.getElementById('notif-badge');
            const list = document.getElementById('notif-list');

            if (notifications.length > 0) {
                badge.classList.remove('hidden');
                list.innerHTML = '';
                notifications.forEach(n => {
                    list.innerHTML += `
                        <div class="p-2 hover:bg-slate-50 rounded border-b border-slate-100">
                            <p class="text-slate-700 font-medium">${n.text}</p>
                            <span class="text-[10px] text-slate-400">${n.time}</span>
                        </div>
                    `;
                });
            } else {
                badge.classList.add('hidden');
                list.innerHTML = `<p class="text-slate-400 text-center py-4">No new notifications</p>`;
            }
        }
    </script>
</body>
</html>
"""
