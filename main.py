from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI(title="Veklom VNP Standalone Node")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "veklom-vnp-standalone",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/vnp/score/{api_id}")
async def get_score(api_id: str):
    # Dummy implementation for VNP API scoring
    return {
        "api_id": api_id,
        "score": 98.5,
        "status": "verified"
    }

@app.get("/")
async def root():
    return {"message": "VNP Protocol Gateway Online"}
