import uvicorn
import os

if __name__ == "__main__":
    print("Starting CivicPulse Localhost Server...")
    print("Access the Progressive Web App (PWA) at: http://localhost:8000")
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
