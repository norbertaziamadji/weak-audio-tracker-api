"""
Weak Audio Tracker API
Pont entre l'interface React Native et le scanner Python
"""

import os
import tempfile
from typing import Any, Dict, List, Optional

from core.database import DatabaseManager

# Import de ton code existant
from core.scanner import analyser_fichier_robuste, scanner_dossier_robuste
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Créer l'application FastAPI
app = FastAPI(title="Weak Audio Tracker API", version="1.0.0")

# Autoriser les requêtes depuis l'app mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèles de données
class AnalyseDossierResponse(BaseModel):
    path: str
    total: int
    bons: int
    moyens: int
    faibles: int
    reparés: int
    corrompus: int

class AnalyseFichierResponse(BaseModel):
    path: str
    total: int
    bons: int
    moyens: int
    faibles: int
    reparés: int
    corrompus: int
    bitrate: Optional[int] = 0

class StatsGlobalesResponse(BaseModel):
    total_analyses: int
    total_fichiers: int
    bons: int
    moyens: int
    faibles: int
    reparés: int
    corrompus: int


# ==================== ENDPOINTS ====================

@app.get("/")
def root():
    return {"message": "Weak Audio Tracker API", "status": "running"}

@app.post("/analyze/folder")
def analyze_folder(path: str):
    """Analyse un dossier complet"""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Le dossier {path} n'existe pas")
    
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"{path} n'est pas un dossier")
    
    categories, stats = scanner_dossier_robuste(
        path,
        deplacement_auto=False,
        tentative_reparation=True
    )
    
    return {
        "path": path,
        "total": stats.get('total_trouves', 0),
        "bons": len(categories.get('bons', [])),
        "moyens": len(categories.get('moyens', [])),
        "faibles": len(categories.get('faibles', [])),
        "reparés": len(categories.get('reparés', [])),
        "corrompus": len(categories.get('corrompus', []))
    }

@app.post("/analyze/file")
async def analyze_file(file: UploadFile = File(...)):
    """Analyse un fichier audio uploadé"""
    if not file.filename.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg', '.aac')):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté")
    
    # Sauvegarder temporairement
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        resultat = analyser_fichier_robuste(tmp_path)
        
        if resultat['succes']:
            bitrate = resultat['bitrate']
            if bitrate >= 128:
                bons, moyens, faibles = 1, 0, 0
            elif bitrate >= 64:
                bons, moyens, faibles = 0, 1, 0
            else:
                bons, moyens, faibles = 0, 0, 1
            
            return {
                "path": file.filename,
                "total": 1,
                "bons": bons,
                "moyens": moyens,
                "faibles": faibles,
                "reparés": 0,
                "corrompus": 0,
                "bitrate": bitrate
            }
        else:
            return {
                "path": file.filename,
                "total": 1,
                "bons": 0,
                "moyens": 0,
                "faibles": 0,
                "reparés": 0,
                "corrompus": 1,
                "bitrate": 0
            }
    finally:
        os.unlink(tmp_path)

@app.get("/stats/global")
def get_global_stats():
    """Retourne les statistiques globales"""
    db = DatabaseManager()
    stats = db.get_statistiques_globales()
    
    return {
        "total_analyses": stats.get('total_analyses', 0),
        "total_fichiers": stats.get('total_fichiers', 0),
        "bons": stats.get('bons', 0),
        "moyens": stats.get('moyens', 0),
        "faibles": stats.get('faibles', 0),
        "reparés": stats.get('reparés', 0),
        "corrompus": stats.get('corrompus', 0)
    }

@app.get("/history")
def get_history(limit: int = 20):
    """Retourne l'historique des analyses"""
    db = DatabaseManager()
    rapports = db.charger_rapports(limit)
    return rapports

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)