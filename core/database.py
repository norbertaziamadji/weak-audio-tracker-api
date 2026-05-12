# sauvegarde_rapports.py
# Gestion de la base de données SQLite pour les rapports d'analyse
# sauvegarde_rapports.py
# Gestion de la base de données SQLite pour les rapports d'analyse

import sqlite3
import os
import datetime
import json
import sys
from pathlib import Path

def get_data_dir():
    """Retourne le dossier data (fonctionne en dev et en exe)"""
    if getattr(sys, 'frozen', False):
        # On est dans un exe PyInstaller
        base_dir = os.path.dirname(sys.executable)
    else:
        # On est en développement
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

class DatabaseManager:
    """
    Gère la base de données SQLite pour sauvegarder les analyses
    """
    
    def __init__(self, db_path=None):
        if db_path is None:
            data_dir = get_data_dir()
            db_path = os.path.join(data_dir, "weak_audio_reports.db")
        self.db_path = db_path
        self.init_database()

    
    def init_database(self):
        """Crée les tables si elles n'existent pas"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table des analyses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_analyse TEXT NOT NULL,
                type_analyse TEXT NOT NULL,
                chemin TEXT NOT NULL,
                duree_secondes INTEGER,
                total_fichiers_os INTEGER,
                total_fichiers_audio INTEGER,
                bons INTEGER DEFAULT 0,
                moyens INTEGER DEFAULT 0,
                faibles INTEGER DEFAULT 0,
                reparés INTEGER DEFAULT 0,
                corrompus INTEGER DEFAULT 0,
                non_audio INTEGER DEFAULT 0,
                taille_total_mb REAL DEFAULT 0,
                note TEXT
            )
        ''')
        
        # Table des fichiers détaillés
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fichiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analyse_id INTEGER NOT NULL,
                chemin TEXT NOT NULL,
                nom TEXT NOT NULL,
                extension TEXT NOT NULL,
                taille_octets INTEGER,
                bitrate INTEGER,
                qualite TEXT,
                statut TEXT,
                methode_analyse TEXT,
                erreur TEXT,
                date_modification TEXT,
                FOREIGN KEY (analyse_id) REFERENCES analyses (id) ON DELETE CASCADE
            )
        ''')
        
        # Table des doublons
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS doublons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analyse_id INTEGER NOT NULL,
                groupe_id INTEGER NOT NULL,
                type_doublon TEXT NOT NULL,
                confiance INTEGER,
                fichier_garde TEXT,
                fichier_supprimable TEXT,
                taille_octets INTEGER,
                FOREIGN KEY (analyse_id) REFERENCES analyses (id) ON DELETE CASCADE
            )
        ''')
        
        # Index pour les performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analyses_date ON analyses(date_analyse)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fichiers_analyse ON fichiers(analyse_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fichiers_qualite ON fichiers(qualite)')
        
        conn.commit()
        conn.close()
    
    def sauvegarder_analyse(self, type_analyse, chemin, categories, stats, total_os, duree_secondes, note=""):
        """
        Sauvegarde une analyse complète dans la base de données
        Retourne l'ID de l'analyse créée
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        date_analyse = datetime.datetime.now().isoformat()
        
        # Calculer la taille totale
        taille_total = 0
        for cat in ['bons', 'moyens', 'faibles', 'reparés']:
            for item in categories.get(cat, []):
                if len(item) >= 2:
                    chemin_fichier = item[1] if isinstance(item, tuple) else item
                    if os.path.exists(chemin_fichier):
                        taille_total += os.path.getsize(chemin_fichier)
        
        non_audio = total_os - stats.get('total_trouves', 0)
        
        # Insérer l'analyse
        cursor.execute('''
            INSERT INTO analyses (
                date_analyse, type_analyse, chemin, duree_secondes,
                total_fichiers_os, total_fichiers_audio,
                bons, moyens, faibles, reparés, corrompus, non_audio,
                taille_total_mb, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date_analyse,
            type_analyse,
            chemin,
            duree_secondes,
            total_os,
            stats.get('total_trouves', 0),
            len(categories.get('bons', [])),
            len(categories.get('moyens', [])),
            len(categories.get('faibles', [])),
            len(categories.get('reparés', [])),
            len(categories.get('corrompus', [])),
            non_audio,
            round(taille_total / (1024 * 1024), 2),
            note
        ))
        
        analyse_id = cursor.lastrowid
        
        # Insérer tous les fichiers
        for qualite, items in categories.items():
            if qualite in ['bons', 'moyens', 'faibles', 'reparés', 'corrompus', 'a_verifier']:
                for item in items:
                    self._inserer_fichier(cursor, analyse_id, qualite, item)
        
        conn.commit()
        conn.close()
        
        return analyse_id
    
    def _inserer_fichier(self, cursor, analyse_id, qualite, item):
        """Insère un fichier dans la base (méthode interne)"""
        try:
            if qualite in ['bons', 'moyens', 'faibles']:
                # Format: (bitrate, chemin, methode)
                bitrate, chemin, methode = item
                erreur = None
                statut = "analyse"
            elif qualite == 'reparés':
                # Format: (chemin, message)
                chemin, message = item
                bitrate = self._estimer_bitrate_apres_reparation(chemin)
                methode = "reparation"
                erreur = None
                statut = "reparé"
            elif qualite == 'corrompus':
                # Format: (chemin, erreur)
                chemin, erreur = item
                bitrate = 0
                methode = "inconnue"
                statut = "corrompu"
            else:  # a_verifier
                if len(item) == 2:
                    chemin, erreur = item
                else:
                    chemin = item[0]
                    erreur = item[1] if len(item) > 1 else "inconnue"
                bitrate = 0
                methode = "inconnue"
                statut = "a_verifier"
            
            if os.path.exists(chemin):
                taille = os.path.getsize(chemin)
                date_modif = datetime.datetime.fromtimestamp(
                    os.path.getmtime(chemin)
                ).isoformat()
            else:
                taille = 0
                date_modif = None
            
            cursor.execute('''
                INSERT INTO fichiers (
                    analyse_id, chemin, nom, extension, taille_octets,
                    bitrate, qualite, statut, methode_analyse, erreur, date_modification
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                analyse_id,
                chemin,
                os.path.basename(chemin),
                os.path.splitext(chemin)[1].lower(),
                taille,
                bitrate,
                qualite,
                statut,
                methode,
                erreur,
                date_modif
            ))
        except Exception as e:
            print(f"Erreur insertion fichier {item}: {e}")
    
    def _estimer_bitrate_apres_reparation(self, chemin):
        """Estime le bitrate d'un fichier réparé"""
        try:
            from mutagen import File
            audio = File(chemin)
            if audio and audio.info and hasattr(audio.info, "bitrate"):
                return int(audio.info.bitrate / 1000)
        except:
            pass
        return 128  # Valeur par défaut
    
    def charger_rapports(self, limite=50):
        """
        Charge les derniers rapports d'analyse
        Retourne une liste de dictionnaires
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM analyses 
            ORDER BY date_analyse DESC 
            LIMIT ?
        ''', (limite,))
        
        rapports = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return rapports
    
    def charger_rapport_par_id(self, analyse_id):
        """
        Charge un rapport spécifique avec ses fichiers
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Charger l'analyse
        cursor.execute('SELECT * FROM analyses WHERE id = ?', (analyse_id,))
        rapport = dict(cursor.fetchone() or {})
        
        if rapport:
            # Charger les fichiers
            cursor.execute('''
                SELECT * FROM fichiers 
                WHERE analyse_id = ? 
                ORDER BY 
                    CASE qualite 
                        WHEN 'faibles' THEN 1
                        WHEN 'corrompus' THEN 2
                        WHEN 'moyens' THEN 3
                        WHEN 'bons' THEN 4
                        ELSE 5
                    END,
                    nom
            ''', (analyse_id,))
            
            fichiers = [dict(row) for row in cursor.fetchall()]
            rapport['fichiers'] = fichiers
        
        conn.close()
        return rapport
    
    def charger_par_dossier(self, chemin):
        """
        Charge tous les rapports pour un dossier donné
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM analyses 
            WHERE chemin LIKE ? 
            ORDER BY date_analyse DESC
        ''', (f"{chemin}%",))
        
        rapports = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return rapports
    
    def supprimer_analyse(self, analyse_id):
        """Supprime une analyse et ses fichiers (cascade)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM analyses WHERE id = ?', (analyse_id,))
        conn.commit()
        conn.close()
    
    def get_statistiques_globales(self):
        """
        Retourne des statistiques globales sur toutes les analyses
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_analyses,
                SUM(total_fichiers_audio) as total_fichiers_analyses,
                SUM(bons) as total_bons,
                SUM(moyens) as total_moyens,
                SUM(faibles) as total_faibles,
                SUM(reparés) as total_reparés,
                SUM(corrompus) as total_corrompus,
                AVG(duree_secondes) as duree_moyenne
            FROM analyses
        ''')
        
        stats = dict(zip(
            ['total_analyses', 'total_fichiers', 'bons', 'moyens', 
             'faibles', 'reparés', 'corrompus', 'duree_moyenne'],
            cursor.fetchone()
        ))
        
        conn.close()
        return stats


# Fonctions utilitaires pour l'interface
def sauvegarder_analyse_depuis_scanner(type_analyse, chemin, categories, stats, total_os, duree_secondes):
    """Wrapper pour sauvegarder facilement depuis scanner.py"""
    db = DatabaseManager()
    return db.sauvegarder_analyse(type_analyse, chemin, categories, stats, total_os, duree_secondes)


def get_rapports_recents(limite=20):
    """Wrapper pour l'interface"""
    db = DatabaseManager()
    return db.charger_rapports(limite)


def get_rapport_detail(analyse_id):
    """Wrapper pour l'interface"""
    db = DatabaseManager()
    return db.charger_rapport_par_id(analyse_id)


# Test rapide si exécuté directement
if __name__ == "__main__":
    print("🔍 Test de la base de données...")
    db = DatabaseManager("test_reports.db")
    
    # Créer des données de test
    categories_test = {
        'bons': [(320, "D:/test/song1.mp3", "mutagen")],
        'moyens': [(128, "D:/test/song2.mp3", "mutagen")],
        'faibles': [(48, "D:/test/song3.mp3", "mutagen")],
        'reparés': [("D:/test/song4.mp3", "réparé")],
        'corrompus': [("D:/test/song5.mp3", "corrompu")]
    }
    
    stats_test = {
        'total_trouves': 5,
        'total_analyses': 3,
        'total_reparations': 1,
        'total_erreurs': 1
    }
    
    # Sauvegarder
    analyse_id = db.sauvegarder_analyse(
        "dossier", 
        "D:/test", 
        categories_test, 
        stats_test, 
        10,  # total_os
        120,  # duree_secondes
        "Test initial"
    )
    
    print(f"✅ Analyse sauvegardée avec ID: {analyse_id}")
    
    # Charger
    rapports = db.charger_rapports()
    print(f"📊 {len(rapports)} rapports trouvés")
    
    if rapports:
        print("\n📋 Détail du premier rapport:")
        for key, value in rapports[0].items():
            print(f"  {key}: {value}")
    
    print("\n✅ Test terminé")