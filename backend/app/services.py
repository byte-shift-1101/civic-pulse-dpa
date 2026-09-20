import json
import math
import uuid
import re
from datetime import datetime
import urllib.request
from backend.app.database import get_db_connection

# Simple local geocoding database for Bengaluru landmarks to make the app work offline/without keys
BENGALURU_LANDMARKS = {
    "mg road metro": (12.9752, 77.6068, "MG Road Metro Station, Bengaluru"),
    "mg road": (12.9752, 77.6068, "MG Road, Bengaluru"),
    "indiranagar": (12.9784, 77.6408, "5th Cross, Indiranagar, Bengaluru"),
    "koramangala": (12.9348, 77.6224, "80 Feet Road, Koramangala, Bengaluru"),
    "jayanagar": (12.9592, 77.5731, "Jayanagar 3rd Block, Bengaluru"),
    "majestic": (12.9779, 77.5724, "Majestic Bus Stand, Bengaluru"),
    "whitefield": (12.9698, 77.7499, "Whitefield Main Road, Bengaluru"),
    "hebbal": (13.0359, 77.5970, "Hebbal Flyover, Bengaluru"),
    "electronic city": (12.8452, 77.6760, "Electronic City Phase 1, Bengaluru")
}

class GeocodingService:
    @staticmethod
    def geocode(text: str):
        """
        Extracts landmark and returns coordinates.
        If a known Bengaluru landmark is found, returns its coordinates.
        Otherwise, returns a random coordinate near Bengaluru center with LOW confidence.
        """
        text_lower = text.lower()
        for key, (lat, lng, addr) in BENGALURU_LANDMARKS.items():
            if key in text_lower:
                return {
                    "latitude": lat,
                    "longitude": lng,
                    "address": addr,
                    "landmark": key.title(),
                    "confidence": "HIGH"
                }
        
        # Fallback: Generate a coordinate near Bengaluru center (12.9716, 77.5946)
        # with a slight random offset
        import random
        lat = 12.9716 + random.uniform(-0.03, 0.03)
        lng = 77.5946 + random.uniform(-0.03, 0.03)
        return {
            "latitude": lat,
            "longitude": lng,
            "address": "Inferred Location, Bengaluru",
            "landmark": "Unknown Landmark",
            "confidence": "LOW"
        }

class AIService:
    @staticmethod
    def analyze_complaint(text: str):
        """
        Analyzes complaint text. Uses Groq API if GROQ_API_KEY is set in environment.
        Otherwise, falls back to a highly intelligent local rule-based NLP parser.
        """
        import os
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            try:
                # Simple synchronous request to Groq API to avoid extra dependencies
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                prompt = f"""
                Analyze this civic complaint: "{text}"
                Return a JSON object with exactly these keys:
                - category_id: one of ("cat_pothole", "cat_garbage", "cat_street_light", "cat_drainage", "cat_water_leak", "cat_traffic_signal", "cat_stray_animals")
                - category_confidence: float between 0.0 and 1.0
                - summary: 1-2 sentence concise summary
                - landmark: extracted landmark or null
                - citizen_priority: "LOW", "MEDIUM", or "HIGH" based on tone/urgency
                """
                data = {
                    "model": "llama3-8b-8192",
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"}
                }
                req = urllib.request.Request(
                    url, 
                    data=json.dumps(data).encode('utf-8'), 
                    headers=headers, 
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    res_data = json.loads(response.read().decode('utf-8'))
                    content = res_data['choices'][0]['message']['content']
                    return json.loads(content)
            except Exception as e:
                print(f"Groq API failed, falling back to local NLP: {e}")

        # Local Rule-Based NLP Parser
        text_lower = text.lower()
        
        # 1. Category Classification
        category_id = "cat_pothole" # Default
        confidence = 0.6
        
        cat_keywords = {
            "cat_pothole": ["pothole", "road", "crater", "asphalt", "tar", "damage", "pit", "bump"],
            "cat_garbage": ["garbage", "waste", "trash", "dump", "bin", "litter", "smell", "stink", "plastic"],
            "cat_street_light": ["light", "dark", "lamp", "bulb", "wire", "electricity", "street light", "street-light"],
            "cat_drainage": ["drain", "sewage", "waterlogging", "flood", "clog", "gutter", "overflow", "storm"],
            "cat_water_leak": ["leak", "pipe", "burst", "water supply", "gush", "wasting water"],
            "cat_traffic_signal": ["traffic", "signal", "light", "junction", "congestion", "timer"],
            "cat_stray_animals": ["dog", "stray", "cow", "cattle", "animal", "bite", "bark", "carcass"]
        }
        
        best_cat = None
        max_matches = 0
        for cat, keywords in cat_keywords.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > max_matches:
                max_matches = matches
                best_cat = cat
                
        if best_cat:
            category_id = best_cat
            confidence = min(0.5 + (max_matches * 0.15), 0.99)

        # 2. Summarization
        summary = text
        if len(text) > 80:
            # Simple truncation/sentence extraction
            sentences = re.split(r'[.!?]+', text)
            summary = sentences[0].strip() + "."
            if len(summary) < 30 and len(sentences) > 1:
                summary += " " + sentences[1].strip() + "."

        # 3. Landmark Extraction
        landmark = None
        for key in BENGALURU_LANDMARKS.keys():
            if key in text_lower:
                landmark = key.title()
                break

        # 4. Citizen Priority
        citizen_priority = "MEDIUM"
        high_urgency_words = ["dangerous", "accident", "severe", "emergency", "critical", "immediate", "dying", "flooded", "gushing", "injury"]
        low_urgency_words = ["beautification", "request", "suggestion", "minor", "could be improved"]
        
        if any(w in text_lower for w in high_urgency_words):
            citizen_priority = "HIGH"
        elif any(w in text_lower for w in low_urgency_words):
            citizen_priority = "LOW"

        return {
            "category_id": category_id,
            "category_confidence": confidence,
            "summary": summary,
            "landmark": landmark,
            "citizen_priority": citizen_priority
        }

class PrioritizationEngine:
    @staticmethod
    def calculate_priority(
        category_id: str, 
        created_at_str: str, 
        upvotes: int, 
        similar_count: int,
        citizen_priority: str
    ):
        """
        Computes operational priority score (0-100) and assigns a band.
        Formula:
            priority_score = W_age * age_score 
                           + W_category * category_score 
                           + W_similar * similar_score 
                           + W_upvotes * upvote_score
        """
        # 1. Age Score (Max 100, saturates at 72 hours)
        try:
            created_at = datetime.fromisoformat(created_at_str)
            hours_open = (datetime.utcnow() - created_at).total_seconds() / 3600.0
        except Exception:
            hours_open = 0.0
        
        age_score = min(100.0, (hours_open / 72.0) * 100.0)

        # 2. Category Score (from DB or default weights)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT base_priority_weight FROM categories WHERE id = ?;", (category_id,))
        row = cursor.fetchone()
        conn.close()
        category_score = row["base_priority_weight"] if row else 50.0

        # 3. Similar Complaint Score (Saturates at 10 similar complaints)
        similar_score = min(100.0, (similar_count / 10.0) * 100.0)

        # 4. Upvote Score (Logarithmic scale, saturates at 50 upvotes)
        upvote_score = min(100.0, (math.log1p(upvotes) / math.log1p(50)) * 100.0)

        # Weights
        W_age = 0.25
        W_category = 0.35
        W_similar = 0.25
        W_upvotes = 0.15

        score = (W_age * age_score) + (W_category * category_score) + (W_similar * similar_score) + (W_upvotes * upvote_score)
        
        # Boost if citizen priority is HIGH
        if citizen_priority == "HIGH":
            score = min(100.0, score + 5.0)
        elif citizen_priority == "LOW":
            score = max(0.0, score - 5.0)

        # Determine Band
        if score >= 85.0:
            band = "CRITICAL"
        elif score >= 65.0:
            band = "HIGH"
        elif score >= 40.0:
            band = "MEDIUM"
        else:
            band = "LOW"

        explanation = {
            "age_contribution": round(W_age * age_score, 1),
            "category_contribution": round(W_category * category_score, 1),
            "similar_contribution": round(W_similar * similar_score, 1),
            "upvotes_contribution": round(W_upvotes * upvote_score, 1),
            "citizen_priority_adjustment": 5.0 if citizen_priority == "HIGH" else (-5.0 if citizen_priority == "LOW" else 0.0)
        }

        return round(score, 1), band, json.dumps(explanation)

class SimilarityService:
    @staticmethod
    def find_similar_complaints(latitude: float, longitude: float, category_id: str, max_radius_km: float = 1.0):
        """
        Finds open complaints of the same category within a given radius (in km).
        Uses Haversine formula to calculate distance.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, public_id, latitude, longitude, description_original, status, created_at, upvote_count
            FROM complaints
            WHERE category_id = ? AND status != 'RESOLVED' AND parent_id IS NULL;
        """, (category_id,))
        
        rows = cursor.fetchall()
        conn.close()

        similar = []
        for row in rows:
            # Haversine distance
            lat1, lon1 = math.radians(latitude), math.radians(longitude)
            lat2, lon2 = math.radians(row["latitude"]), math.radians(row["longitude"])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = 6371.0 * c # Radius of earth in km

            if distance <= max_radius_km:
                similar.append({
                    "id": row["id"],
                    "public_id": row["public_id"],
                    "distance_meters": round(distance * 1000.0, 1),
                    "description": row["description_original"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "upvote_count": row["upvote_count"]
                })
                
        return sorted(similar, key=lambda x: x["distance_meters"])
