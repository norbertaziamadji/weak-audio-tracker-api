# core/__init__.py
"""
Module core - Logique métier de l'application
"""

from .scanner import (
    scanner_dossier_robuste,
    analyser_fichier_robuste,
    preparer_nettoyage,
    executer_nettoyage,
    detecter_doublons_avance,
    detecter_faux_320,
    calculer_economie_espace,
    EXTENSIONS_AUDIO
)

from .database import (
    DatabaseManager,
    sauvegarder_analyse_depuis_scanner,
    get_rapports_recents,
    get_rapport_detail
)

from .analytics import Analytics

from .graphiques import GraphiquesAudio

__all__ = [
    # Scanner
    'scanner_dossier_robuste',
    'analyser_fichier_robuste',
    'preparer_nettoyage',
    'executer_nettoyage',
    'detecter_doublons_avance',
    'detecter_faux_320',
    'calculer_economie_espace',
    'EXTENSIONS_AUDIO',
    # Database
    'DatabaseManager',
    'sauvegarder_analyse_depuis_scanner',
    'get_rapports_recents',
    'get_rapport_detail',
    # Analytics
    'Analytics',
    # Graphiques
    'GraphiquesAudio'
]