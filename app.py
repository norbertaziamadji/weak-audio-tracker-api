"""
Weak Audio Tracker API
Pont entre l'interface React Native et le scanner Python
Version avec analyse spectrale pour détection faux 320 kbps
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import de ton code existant
from core.database import DatabaseManager
from core.scanner import analyser_fichier_robuste, scanner_dossier_robuste

# Analyse spectrale (nécessite numpy, scipy, ffmpeg)
try:
    import numpy as np
    from scipy.io import wavfile
    from scipy.fft import fft
    SPECTRAL_ANALYSIS_AVAILABLE = True
except ImportError:
    SPECTRAL_ANALYSIS_AVAILABLE = False
    print("⚠️ Analyse spectrale non disponible. Installez numpy et scipy.")

app = FastAPI(title="Weak Audio Tracker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


class Fake320Response(BaseModel):
    is_fake_320: bool
    high_freq_ratio: float
    confidence: str
    bitrate: int


class StatsGlobalesResponse(BaseModel):
    total_analyses: int
    total_fichiers: int
    bons: int
    moyens: int
    faibles: int
    reparés: int
    corrompus: int


# ==================== ANALYSE SPECTRALE (FAUX 320) ====================

def detect_fake_320(filepath: str) -> dict:
    """
    Détecte les faux 320 kbps par analyse spectrale.
    Un vrai 320 kbps a de l'énergie au-dessus de 16 kHz.
    Un faux 320 (re-encodé depuis du 128) a une coupure nette à ~16 kHz.
    """
    if not SPECTRAL_ANALYSIS_AVAILABLE:
        return {
            "is_fake_320": False,
            "high_freq_ratio": 0.0,
            "confidence": "unavailable",
            "error": "numpy/scipy non installés"
        }

    # Convertir en WAV temporaire pour analyse
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Convertir en WAV mono, 44.1 kHz, 30 premières secondes
        subprocess.run([
            'ffmpeg', '-i', filepath,
            '-ar', '44100', '-ac', '1',
            '-t', '30',
            '-y', tmp_path
        ], capture_output=True, timeout=30, check=False)

        rate, data = wavfile.read(tmp_path)
        
        if len(data) == 0:
            return {
                "is_fake_320": False,
                "high_freq_ratio": 0.0,
                "confidence": "low",
                "error": "fichier trop court"
            }
        
        # Analyse spectrale FFT sur 10 secondes
        sample_size = min(rate * 10, len(data))
        spectrum = np.abs(fft(data[:sample_size]))
        freqs = np.fft.fftfreq(len(spectrum), 1/rate)
        
        # Énergie au-dessus de 16 kHz (zone discriminante)
        high_freq_mask = (freqs > 16000) & (freqs < 20000)
        high_freq_energy = np.mean(spectrum[high_freq_mask]) if np.any(high_freq_mask) else 0
        
        total_energy = np.mean(spectrum[freqs > 0])
        ratio = high_freq_energy / total_energy if total_energy > 0 else 0

        # Seuils empiriques
        if ratio < 0.005:
            confidence = "high"
            is_fake = True
        elif ratio < 0.02:
            confidence = "medium"
            is_fake = True
        elif ratio < 0.05:
            confidence = "low"
            is_fake = False
        else:
            confidence = "high"
            is_fake = False

        return {
            "is_fake_320": is_fake,
            "high_freq_ratio": round(float(ratio), 4),
            "confidence": confidence
        }
        
    except Exception as e:
        return {
            "is_fake_320": False,
            "high_freq_ratio": 0.0,
            "confidence": "low",
            "error": str(e)
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


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
            
            # Détection faux 320 si bitrate annoncé est élevé
            fake_320_info = None
            if bitrate >= 300:
                fake_320_info = detect_fake_320(tmp_path)
            
            response = {
                "path": file.filename,
                "total": 1,
                "bons": bons,
                "moyens": moyens,
                "faibles": faibles,
                "reparés": 0,
                "corrompus": 0,
                "bitrate": bitrate
            }
            
            if fake_320_info:
                response["fake_320"] = fake_320_info
            
            return response
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


@app.post("/analyze/fake320")
async def check_fake_320(file: UploadFile = File(...)):
    """Endpoint dédié à la détection des faux 320 kbps"""
    if not file.filename.lower().endswith(('.mp3', '.m4a', '.flac', '.wav', '.ogg', '.aac')):
        raise HTTPException(status_code=400, detail="Format de fichier non supporté")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        # D'abord l'analyse basique
        resultat = analyser_fichier_robuste(tmp_path)
        bitrate = resultat['bitrate'] if resultat['succes'] else 0
        
        # Puis l'analyse spectrale
        spectral_result = detect_fake_320(tmp_path)
        
        return {
            "filename": file.filename,
            "bitrate": bitrate,
            **spectral_result
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