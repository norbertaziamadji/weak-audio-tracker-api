"""
Gestion centralisée des couleurs et styles
"""

from kivy.metrics import dp
from kivy.utils import get_color_from_hex


class AppTheme:
    """Classe centralisée pour les thèmes"""
    
    # Couleurs principales
    PRIMARY = get_color_from_hex("#2196F3")  # Bleu Material
    PRIMARY_DARK = get_color_from_hex("#1976D2")
    PRIMARY_LIGHT = get_color_from_hex("#BBDEFB")
    
    # Couleurs de qualité
    GOOD = get_color_from_hex("#4CAF50")   # Vert
    MEDIUM = get_color_from_hex("#FF9800")  # Orange
    WEAK = get_color_from_hex("#F44336")    # Rouge
    REPAIRED = get_color_from_hex("#2196F3")  # Bleu
    CORRUPTED = get_color_from_hex("#9E9E9E")  # Gris
    
    # Couleurs de fond
    @staticmethod
    def get_card_bg(theme_cls):
        """Retourne la couleur de fond pour les cartes selon le thème"""
        if theme_cls.theme_style == "Dark":
            return (0.15, 0.15, 0.15, 1)  # Gris très foncé
        else:
            return (0.98, 0.98, 0.98, 1)  # Blanc cassé
    
    @staticmethod
    def get_bg_color(theme_cls):
        """Retourne la couleur de fond principale"""
        if theme_cls.theme_style == "Dark":
            return (0.1, 0.1, 0.1, 1)
        else:
            return (0.95, 0.95, 0.95, 1)
    
    @staticmethod
    def get_text_color(theme_cls):
        """Retourne la couleur du texte selon le thème"""
        if theme_cls.theme_style == "Dark":
            return (1, 1, 1, 1)  # Blanc
        else:
            return (0, 0, 0, 1)  # Noir
    
    @staticmethod
    def get_secondary_text_color(theme_cls):
        """Retourne la couleur du texte secondaire"""
        if theme_cls.theme_style == "Dark":
            return (0.7, 0.7, 0.7, 1)
        else:
            return (0.4, 0.4, 0.4, 1)