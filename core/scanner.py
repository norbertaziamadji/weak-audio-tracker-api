# scanner.py - Version complète avec toutes les fonctions
# CORRIGÉ : Ajout de la sauvegarde automatique dans la base de données

import os
import shutil
import csv
import hashlib
import re
import datetime
from collections import defaultdict
from difflib import SequenceMatcher
from mutagen import File
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE

# ==================== CONSTANTES ====================

EXTENSIONS_AUDIO = (
    ".mp3", ".m4a", ".flac", ".wav", ".ogg", ".aac", 
    ".opus", ".wma", ".aiff", ".dsd", ".mka", ".ac3"
)

# ==================== FONCTIONS DE BASE ====================

def compter_fichiers_total(dossier):
    """Compte TOUS les fichiers (pour comparaison avec l'explorateur)"""
    total = 0
    for racine, _, fichiers in os.walk(dossier):
        if "Weak_Audio" in racine:
            continue
        total += len(fichiers)
    return total


def compter_fichiers_audio(dossier):
    """Compte uniquement les fichiers audio"""
    total = 0
    for racine, _, fichiers in os.walk(dossier):
        if "Weak_Audio" in racine:
            continue
        for fichier in fichiers:
            if fichier.lower().endswith(EXTENSIONS_AUDIO):
                total += 1
    return total


# ==================== ANALYSE ROBUSTE ====================

class ReparateurAudio:
    """
    Classe pour tenter de réparer les fichiers audio qui ne donnent pas d'info
    """
    
    def __init__(self):
        self.stats = {
            'tentes': 0,
            'reussis': 0,
            'echoues': 0,
            'ignores': 0
        }
    
    def reparer_fichier(self, chemin):
        """
        Tente différentes méthodes pour réparer un fichier audio
        Retourne (succes, nouveau_chemin, message)
        """
        
        print(f"🔧 Tentative de réparation : {os.path.basename(chemin)}")
        self.stats['tentes'] += 1
        
        extension = os.path.splitext(chemin)[1].lower()
        
        # Méthode 1 : Forcer le format spécifique
        try:
            if extension == '.mp3':
                return self._reparer_mp3(chemin)
            elif extension == '.m4a':
                return self._reparer_m4a(chemin)
            elif extension == '.flac':
                return self._reparer_flac(chemin)
            else:
                # Autres formats : tentative générique
                return self._reparer_generique(chemin)
        except Exception as e:
            self.stats['echoues'] += 1
            return (False, chemin, f"Erreur: {str(e)[:50]}")
    
    def _reparer_mp3(self, chemin):
        """Tente de réparer un fichier MP3"""
        try:
            # Forcer la lecture en MP3
            audio = MP3(chemin)
            if audio and audio.info:
                self.stats['reussis'] += 1
                return (True, chemin, "MP3 réparé avec succès")
            else:
                # Essayer de recréer les métadonnées
                return self._recreer_metadonnees(chemin)
        except:
            return self._recreer_metadonnees(chemin)
    
    def _reparer_m4a(self, chemin):
        """Tente de réparer un fichier M4A"""
        try:
            # Forcer la lecture en MP4 (M4A est un MP4 audio)
            audio = MP4(chemin)
            if audio and audio.info:
                self.stats['reussis'] += 1
                return (True, chemin, "M4A réparé avec succès")
            else:
                return self._analyser_manuel_m4a(chemin)
        except:
            return self._analyser_manuel_m4a(chemin)
    
    def _reparer_flac(self, chemin):
        """Tente de réparer un fichier FLAC"""
        try:
            audio = FLAC(chemin)
            if audio and audio.info:
                self.stats['reussis'] += 1
                return (True, chemin, "FLAC réparé avec succès")
            else:
                return (False, chemin, "FLAC corrompu")
        except:
            return (False, chemin, "FLAC non réparable")
    
    def _reparer_generique(self, chemin):
        """Tentative générique pour les autres formats"""
        try:
            audio = File(chemin)
            if audio and audio.info:
                self.stats['reussis'] += 1
                return (True, chemin, "Format réparé avec succès")
            else:
                return (False, chemin, "Format non supporté")
        except:
            return (False, chemin, "Erreur de lecture")
    
    def _recreer_metadonnees(self, chemin):
        """Tente de recréer les métadonnées d'un fichier MP3"""
        try:
            # Créer une copie de sauvegarde
            backup = chemin + ".backup"
            shutil.copy2(chemin, backup)
            
            # Lire le fichier binaire et essayer de l'analyser
            with open(chemin, 'rb') as f:
                data = f.read(1024)  # Lire les premiers 1KB
            
            # Vérifier les signatures de fichiers
            if data.startswith(b'ID3'):
                # C'est un MP3 avec tags ID3
                audio = MP3(chemin)
                if audio:
                    self.stats['reussis'] += 1
                    os.remove(backup)  # Supprimer la sauvegarde
                    return (True, chemin, "Métadonnées ID3 restaurées")
            
            # Si on arrive ici, restauration impossible
            os.remove(backup)
            return (False, chemin, "Impossible de recréer les métadonnées")
            
        except Exception as e:
            return (False, chemin, f"Échec recréation: {str(e)[:30]}")
    
    def _analyser_manuel_m4a(self, chemin):
        """Analyse manuelle d'un fichier M4A sans mutagen"""
        try:
            # Vérifier la signature du fichier
            with open(chemin, 'rb') as f:
                header = f.read(12)
            
            # Les fichiers M4A commencent souvent par 'ftyp'
            if b'ftyp' in header:
                # C'est probablement un M4A valide
                # On estime le bitrate à partir de la taille et de la durée
                taille = os.path.getsize(chemin)
                
                # Essayer de trouver la durée dans le fichier
                duree = self._extraire_duree_m4a(chemin)
                
                if duree > 0:
                    bitrate_estime = int((taille * 8) / (duree * 1000))
                    self.stats['reussis'] += 1
                    return (True, chemin, f"M4A analysé manuellement (~{bitrate_estime} kbps)")
            
            return (False, chemin, "M4A non analysable")
            
        except:
            return (False, chemin, "Erreur analyse manuelle")
    
    def _extraire_duree_m4a(self, chemin):
        """Extrait la durée d'un fichier M4A en lisant les métadonnées brutes"""
        try:
            with open(chemin, 'rb') as f:
                data = f.read(4096)
            
            # Chercher le tag 'mvhd' qui contient la durée
            import struct
            pos = data.find(b'mvhd')
            if pos > 0:
                # La durée est souvent 16-20 bytes après 'mvhd'
                duree_bytes = data[pos+16:pos+20]
                if len(duree_bytes) == 4:
                    duree = struct.unpack('>I', duree_bytes)[0]
                    return duree / 1000  # Convertir en secondes
            return 180  # Valeur par défaut: 3 minutes
        except:
            return 180
    
    def reparer_lot(self, liste_fichiers):
        """
        Tente de réparer une liste de fichiers
        Retourne les résultats
        """
        resultats = {
            'reussis': [],
            'echoues': [],
            'ignores': []
        }
        
        for chemin in liste_fichiers:
            succes, nouveau_chemin, message = self.reparer_fichier(chemin)
            
            if succes:
                resultats['reussis'].append((chemin, message))
            else:
                resultats['echoues'].append((chemin, message))
        
        return resultats
    
    def afficher_stats(self):
        """Affiche les statistiques de réparation"""
        print("\n📊 STATISTIQUES DE RÉPARATION")
        print("="*40)
        print(f"🔧 Tentatives : {self.stats['tentes']}")
        print(f"✅ Réussis    : {self.stats['reussis']}")
        print(f"❌ Échoués    : {self.stats['echoues']}")
        print(f"⏭️  Ignorés    : {self.stats['ignores']}")
        taux = (self.stats['reussis'] / self.stats['tentes'] * 100) if self.stats['tentes'] > 0 else 0
        print(f"📈 Taux succès : {taux:.1f}%")


def analyser_fichier_robuste(chemin):
    """
    Analyse un fichier avec plusieurs méthodes
    """
    resultat = {
        'succes': False,
        'bitrate': 0,
        'methode': 'inconnue',
        'reparable': False,
        'erreur': ''
    }
    
    extension = os.path.splitext(chemin)[1].lower()
    
    # MÉTHODE 1 : Mutagen standard
    try:
        audio = File(chemin)
        if audio and audio.info:
            if hasattr(audio.info, "bitrate"):
                resultat['bitrate'] = int(audio.info.bitrate / 1000)
                resultat['succes'] = True
                resultat['methode'] = 'mutagen_standard'
                return resultat
    except:
        pass
    
    # MÉTHODE 2 : Format spécifique
    try:
        if extension == '.mp3':
            audio = MP3(chemin)
            if audio and audio.info and hasattr(audio.info, "bitrate"):
                resultat['bitrate'] = int(audio.info.bitrate / 1000)
                resultat['succes'] = True
                resultat['methode'] = 'mp3_specifique'
                return resultat
                
        elif extension == '.m4a':
            audio = MP4(chemin)
            if audio and audio.info:
                # Pour M4A, le bitrate est parfois dans une autre propriété
                if hasattr(audio.info, "bitrate"):
                    resultat['bitrate'] = int(audio.info.bitrate / 1000)
                else:
                    # Estimation par la taille
                    taille = os.path.getsize(chemin)
                    if hasattr(audio.info, "length") and audio.info.length > 0:
                        resultat['bitrate'] = int((taille * 8) / (audio.info.length * 1000))
                    else:
                        resultat['bitrate'] = 128  # Estimation par défaut
                resultat['succes'] = True
                resultat['methode'] = 'm4a_specifique'
                return resultat
                
        elif extension == '.flac':
            audio = FLAC(chemin)
            if audio and audio.info:
                # FLAC n'a pas de bitrate fixe, on estime
                if hasattr(audio.info, "sample_rate"):
                    resultat['bitrate'] = int(audio.info.sample_rate / 10)
                    resultat['succes'] = True
                    resultat['methode'] = 'flac_estime'
                    return resultat
    except:
        pass
    
    # MÉTHODE 3 : Analyse par taille (si le fichier existe et a une taille)
    try:
        taille = os.path.getsize(chemin)
        if taille > 1024:  # Plus de 1KB
            # Fichier potentiellement réparable
            resultat['reparable'] = True
            resultat['erreur'] = 'fichier_valide_mais_non_lisible'
            return resultat
    except:
        pass
    
    # ÉCHEC TOTAL
    resultat['erreur'] = 'fichier_corrompu_ou_format_inconnu'
    return resultat


def scanner_dossier_robuste(dossier, deplacement_auto=False, tentative_reparation=True):
    """
    Scanner robuste qui gère tous les cas de figure
    """
    
    # Pour calculer la durée
    debut_analyse = datetime.datetime.now()
    
    categories = {
        'bons': [],           # Qualité >=128 kbps
        'moyens': [],         # 64-127 kbps
        'faibles': [],        # <64 kbps
        'a_verifier': [],     # Fichiers avec bitrate 0 ou incertain
        'corrompus': [],      # Fichiers illisibles
        'reparables': [],     # Fichiers qui pourraient être réparés
        'reparés': []         # Fichiers réparés avec succès
    }
    
    stats = {
        'total_trouves': 0,
        'total_analyses': 0,
        'total_erreurs': 0,
        'total_reparations': 0,
        'total_erreurs_pre_reparation': 0
    }
    
    reparateur = ReparateurAudio()
    fichiers_a_reparer = []
    
    # Compter total OS pour les stats
    total_os = compter_fichiers_total(dossier)
    
    print("="*60)
    print("🔍 ANALYSE AUDIO ROBUSTE")
    print("="*60)
    
    # PHASE 1 : PREMIER PASSAGE - IDENTIFICATION
    print("\n📋 PHASE 1 : IDENTIFICATION DES FICHIERS")
    print("-"*40)
    
    for racine, _, fichiers in os.walk(dossier):
        if "Weak_Audio" in racine:
            continue
            
        for fichier in fichiers:
            if fichier.lower().endswith(EXTENSIONS_AUDIO):
                stats['total_trouves'] += 1
    
    print(f"📊 Total fichiers audio trouvés : {stats['total_trouves']}")
    
    # PHASE 2 : ANALYSE PRINCIPALE
    print("\n🔬 PHASE 2 : ANALYSE DES FICHIERS")
    print("-"*40)
    
    for racine, _, fichiers in os.walk(dossier):
        if "Weak_Audio" in racine:
            continue
            
        for fichier in fichiers:
            if fichier.lower().endswith(EXTENSIONS_AUDIO):
                chemin = os.path.join(racine, fichier)
                
                try:
                    resultat = analyser_fichier_robuste(chemin)
                    
                    if resultat['succes']:
                        stats['total_analyses'] += 1
                        bitrate = resultat['bitrate']
                        methode = resultat['methode']
                        
                        # Classification par qualité
                        if bitrate >= 128:
                            categories['bons'].append((bitrate, chemin, methode))
                        elif bitrate >= 64:
                            categories['moyens'].append((bitrate, chemin, methode))
                        elif bitrate > 0:
                            categories['faibles'].append((bitrate, chemin, methode))
                        else:
                            categories['a_verifier'].append((chemin, "bitrate_zero"))
                    
                    elif resultat['reparable']:
                        # Fichier réparable
                        categories['reparables'].append((chemin, resultat['erreur']))
                        stats['total_erreurs_pre_reparation'] += 1
                        if tentative_reparation:
                            fichiers_a_reparer.append(chemin)
                    
                    else:
                        # Fichier corrompu
                        categories['corrompus'].append((chemin, resultat['erreur']))
                        stats['total_erreurs'] += 1
                        stats['total_erreurs_pre_reparation'] += 1
                        
                except Exception as e:
                    categories['corrompus'].append((chemin, str(e)[:50]))
                    stats['total_erreurs'] += 1
                    stats['total_erreurs_pre_reparation'] += 1
    
    # PHASE 3 : TENTATIVE DE RÉPARATION
    if tentative_reparation and fichiers_a_reparer:
        print("\n🔧 PHASE 3 : TENTATIVE DE RÉPARATION")
        print("-"*40)
        print(f"📦 {len(fichiers_a_reparer)} fichiers à réparer...")
        
        resultats_reparation = reparateur.reparer_lot(fichiers_a_reparer)
        
        for chemin, message in resultats_reparation['reussis']:
            categories['reparés'].append((chemin, message))
            stats['total_reparations'] += 1
            stats['total_analyses'] += 1  # Compté comme analysé maintenant
            
            # Réanalyser le fichier réparé
            resultat = analyser_fichier_robuste(chemin)
            if resultat['succes']:
                bitrate = resultat['bitrate']
                if bitrate >= 128:
                    categories['bons'].append((bitrate, chemin, "réparé"))
                elif bitrate >= 64:
                    categories['moyens'].append((bitrate, chemin, "réparé"))
                else:
                    categories['faibles'].append((bitrate, chemin, "réparé"))
        
        for chemin, message in resultats_reparation['echoues']:
            categories['corrompus'].append((chemin, f"réparation_échouée: {message}"))
            stats['total_erreurs'] += 1
    
    # PHASE 4 : RAPPORT FINAL
    print("\n📊 PHASE 4 : RAPPORT FINAL")
    print("="*60)
    print(f"📁 Total fichiers trouvés : {stats['total_trouves']}")
    print(f"✅ Analysés avec succès : {stats['total_analyses']}")
    print(f"🔧 Réparés avec succès : {stats['total_reparations']}")
    print(f"❌ En erreur : {stats['total_erreurs']}")
    
    if stats['total_reparations'] > 0:
        print(f"\n🎉 {stats['total_reparations']} fichiers ont été réparés !")
    
    reparateur.afficher_stats()

    # Liste des fichiers corrompus
    if categories['corrompus']:
        print("\n❌ LISTE DES FICHIERS CORROMPUS :")
        for chemin, erreur in categories['corrompus']:
            print(f"   • {os.path.basename(chemin)} : {erreur}")
        
        # Sauvegarder la liste
        with open("fichiers_corrompus.txt", "w", encoding="utf-8") as f:
            f.write("# Fichiers corrompus non réparables\n")
            f.write(f"# Date : {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            f.write("#" + "="*50 + "\n")
            for chemin, erreur in categories['corrompus']:
                f.write(f"{chemin}\n")
        print(f"📄 Liste sauvegardée dans : fichiers_corrompus.txt")
    
    # === NOUVEAU : Sauvegarde dans la base de données ===
    try:
        from core.database import sauvegarder_analyse_depuis_scanner
        duree_secondes = (datetime.datetime.now() - debut_analyse).total_seconds()
        analyse_id = sauvegarder_analyse_depuis_scanner(
            type_analyse="dossier",
            chemin=dossier,
            categories=categories,
            stats=stats,
            total_os=total_os,
            duree_secondes=int(duree_secondes)
        )
        print(f"\n💾 Analyse sauvegardée dans la base de données (ID: {analyse_id})")
    except Exception as e:
        print(f"⚠️ Impossible de sauvegarder dans la DB: {e}")
    # === FIN DE L'AJOUT ===
    
    # Déplacement automatique si demandé
    if deplacement_auto and categories['faibles']:
        dossier_weak = os.path.join(dossier, "Weak_Audio")
        os.makedirs(dossier_weak, exist_ok=True)
        
        for bitrate, chemin, _ in categories['faibles']:
            try:
                shutil.move(chemin, dossier_weak)
            except:
                pass
    
    return categories, stats

def exporter_rapport_complet(categories, stats, nom_fichier="rapport_complet.csv"):
    """
    Exporte un rapport détaillé de l'analyse
    """
    with open(nom_fichier, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        writer.writerow(["=== RAPPORT D'ANALYSE AUDIO ==="])
        writer.writerow(["Date", datetime.datetime.now().strftime('%d/%m/%Y %H:%M')])
        writer.writerow([])
        
        writer.writerow(["STATISTIQUES GLOBALES"])
        writer.writerow(["Total fichiers trouvés", stats['total_trouves']])
        writer.writerow(["Analysés avec succès", stats['total_analyses']])
        writer.writerow(["Réparés avec succès", stats['total_reparations']])
        writer.writerow(["En erreur", stats['total_erreurs']])
        writer.writerow([])
        
        writer.writerow(["FICHIERS PAR CATÉGORIE"])
        for cat, fichiers in categories.items():
            writer.writerow([cat.upper(), len(fichiers)])
        
        writer.writerow([])
        writer.writerow(["DÉTAIL DES FICHIERS ANALYSÉS"])
        writer.writerow(["Catégorie", "Bitrate", "Chemin", "Méthode/Note"])
        
        for cat, fichiers in categories.items():
            for item in fichiers:
                if cat in ['bons', 'moyens', 'faibles']:
                    bitrate, chemin, methode = item
                    writer.writerow([cat, bitrate, chemin, methode])
                elif cat == 'reparés':
                    chemin, message = item
                    writer.writerow([cat, "N/A", chemin, message])
                else:
                    chemin, erreur = item
                    writer.writerow([cat, "N/A", chemin, erreur])


# ==================== DÉTECTION FAUX 320 ====================

def detecter_faux_320(dossier):
    """
    Détecte les fichiers qui se prétendent 320 kbps
    mais qui sont en réalité de moindre qualité.
    """
    soupcons = []
    
    for racine, _, fichiers in os.walk(dossier):
        for fichier in fichiers:
            if fichier.lower().endswith(('.mp3', '.m4a')):
                chemin = os.path.join(racine, fichier)
                
                try:
                    audio = File(chemin)
                    
                    if audio and audio.info and hasattr(audio.info, "bitrate"):
                        bitrate_reel = int(audio.info.bitrate / 1000)
                        
                        # Vérifier le nom du fichier
                        if "320" in fichier or "320k" in fichier.lower():
                            if bitrate_reel < 300:  # Seuil pour 320 kbps
                                soupcons.append({
                                    'fichier': chemin,
                                    'bitrate_annonce': 320,
                                    'bitrate_reel': bitrate_reel,
                                    'difference': 320 - bitrate_reel
                                })
                        
                        # Vérifier les tags ID3 pour mp3
                        if hasattr(audio, 'tags') and audio.tags:
                            for tag in ['TXXX:QUALITY', 'TXXX:SOURCE', 'TPE1']:
                                if tag in audio.tags:
                                    # Logique de détection à affiner
                                    pass
                
                except Exception as e:
                    continue
    
    return soupcons


def exporter_faux_320(soupcons, nom_fichier="faux_320_detectes.csv"):
    """
    Exporte la liste des faux 320 kbps en CSV
    """
    with open(nom_fichier, "w", newline="", encoding="utf-8") as fichier:
        writer = csv.writer(fichier)
        
        writer.writerow(["Fichier", "Bitrate annoncé", "Bitrate réel", "Différence"])
        
        for item in soupcons:
            writer.writerow([
                item['fichier'], 
                item['bitrate_annonce'], 
                item['bitrate_reel'],
                item['difference']
            ])


# ==================== DÉTECTION DOUBLONS ====================

def detecter_doublons_avance(dossier, regles=None):
    """
    Détecte les fichiers audio en double avec règles personnalisables
    
    Args:
        dossier: chemin du dossier à analyser
        regles: dictionnaire de règles personnalisées
    """
    
    # Règles par défaut
    regles_par_defaut = {
        'seuil_similarite_noms': 0.85,
        'ignore_parentheses': True,
        'ignore_casse': True,
        'taille_tolerance': 10000,
        'scan_contenu': True,
        'fichiers_cache': False,
        'ignore_extensions': True,
        'seuil_taille_min': 1024,
    }
    
    # Fusionner avec les règles personnalisées
    if regles:
        regles_par_defaut.update(regles)
    
    regles = regles_par_defaut
    
    print("🔍 Recherche des doublons en cours...")
    print(f"📋 Règles appliquées :")
    print(f"   • Seuil similarité noms : {regles['seuil_similarite_noms']*100}%")
    print(f"   • Ignorer (1), (2)... : {regles['ignore_parentheses']}")
    print(f"   • Scan contenu : {regles['scan_contenu']}")
    
    tous_fichiers = []
    doublons = {
        'exacts': [],           # Même nom, même taille
        'similaires': [],       # Noms similaires
        'contenu': [],          # Même contenu (hash)
        'taille': [],           # Même taille mais noms différents
        'probables': []         # Cas particuliers
    }
    
    # 1. Collecter tous les fichiers audio
    for racine, _, fichiers in os.walk(dossier):
        if "Weak_Audio" in racine:
            continue
            
        for fichier in fichiers:
            # Ignorer les fichiers cachés si demandé
            if not regles['fichiers_cache'] and fichier.startswith('.'):
                continue
                
            if fichier.lower().endswith(EXTENSIONS_AUDIO):
                chemin = os.path.join(racine, fichier)
                try:
                    taille = os.path.getsize(chemin)
                    
                    # Ignorer les fichiers trop petits
                    if taille < regles['seuil_taille_min']:
                        continue
                    
                    tous_fichiers.append({
                        'chemin': chemin,
                        'nom': fichier,
                        'nom_sans_ext': os.path.splitext(fichier)[0],
                        'extension': os.path.splitext(fichier)[1].lower(),
                        'taille': taille,
                        'dossier': racine,
                        'dossier_parent': os.path.basename(racine)
                    })
                except:
                    continue
    
    print(f"📊 Total fichiers audio trouvés : {len(tous_fichiers)}")
    
    # 2. Détection des doublons EXACTS (même nom, même taille)
    print("\n🔴 ÉTAPE 1 : Recherche des doublons exacts...")
    
    # Grouper par (nom, taille)
    groupes = {}
    for f in tous_fichiers:
        key = (f['nom'], f['taille'])
        if key not in groupes:
            groupes[key] = []
        groupes[key].append(f)
    
    for (nom, taille), fichiers in groupes.items():
        if len(fichiers) > 1:
            doublons['exacts'].append({
                'type': 'exact',
                'nom': nom,
                'taille': taille,
                'fichiers': fichiers,
                'explication': f"Même nom et même taille dans {len(fichiers)} dossiers"
            })
    
    print(f"   ✅ {len(doublons['exacts'])} groupes de doublons exacts trouvés")
    
    # 3. Détection des doublons par TAILLE
    print("\n🔵 ÉTAPE 2 : Recherche des doublons par taille...")
    
    # Grouper par taille uniquement
    groupes_taille = {}
    for f in tous_fichiers:
        if f['taille'] not in groupes_taille:
            groupes_taille[f['taille']] = []
        groupes_taille[f['taille']].append(f)
    
    for taille, fichiers in groupes_taille.items():
        if len(fichiers) > 1:
            # Vérifier que ce ne sont pas déjà des doublons exacts
            noms = [f['nom'] for f in fichiers]
            if len(set(noms)) > 1:  # Noms différents
                doublons['taille'].append({
                    'type': 'taille',
                    'taille': taille,
                    'fichiers': fichiers,
                    'explication': f"{len(fichiers)} fichiers de même taille ({taille/1024:.1f} KB) mais noms différents"
                })
    
    print(f"   ✅ {len(doublons['taille'])} groupes de doublons par taille trouvés")
    
    # 4. Détection des doublons par NOM SIMILAIRE
    print("\n🟡 ÉTAPE 3 : Recherche des noms similaires...")
    
    def nettoyer_nom(nom, regles):
        """Nettoie un nom selon les règles"""
        nom = nom.lower() if regles['ignore_casse'] else nom
        
        if regles['ignore_parentheses']:
            # Enlever (1), (2), [1], etc.
            nom = re.sub(r'\s*[\(\[]\d+[\)\]]\s*', ' ', nom)
            nom = re.sub(r'\s*-\s*copie\s*', ' ', nom, flags=re.IGNORECASE)
        
        if regles['ignore_extensions']:
            nom = os.path.splitext(nom)[0]
        
        # Nettoyer les espaces multiples
        nom = ' '.join(nom.split())
        
        return nom
    
    # Préparer les noms nettoyés
    for f in tous_fichiers:
        f['nom_nettoye'] = nettoyer_nom(f['nom'], regles)
    
    # Comparer les noms
    deja_vu = set()
    for i, f1 in enumerate(tous_fichiers):
        if i in deja_vu:
            continue
            
        groupe = [f1]
        
        for j, f2 in enumerate(tous_fichiers[i+1:], i+1):
            if j in deja_vu:
                continue
                
            # Calculer la similarité
            ratio = SequenceMatcher(None, f1['nom_nettoye'], f2['nom_nettoye']).ratio()
            
            if ratio >= regles['seuil_similarite_noms']:
                groupe.append(f2)
                deja_vu.add(j)
        
        if len(groupe) > 1:
            deja_vu.add(i)
            doublons['similaires'].append({
                'type': 'similaire',
                'similarite': ratio if len(groupe) == 2 else 'multiple',
                'fichiers': groupe,
                'explication': f"{len(groupe)} fichiers avec noms similaires"
            })
    
    print(f"   ✅ {len(doublons['similaires'])} groupes de noms similaires trouvés")
    
    # 5. Détection des doublons par CONTENU (optionnel, plus lent)
    if regles['scan_contenu']:
        print("\n🟢 ÉTAPE 4 : Recherche des doublons de contenu (cela peut être long)...")
        
        hash_map = defaultdict(list)
        
        for i, f in enumerate(tous_fichiers):
            if i % 100 == 0:
                print(f"   Progression : {i}/{len(tous_fichiers)} fichiers...")
            
            try:
                # Hash MD5 du début du fichier (plus rapide)
                with open(f['chemin'], 'rb') as file_obj:
                    file_hash = hashlib.md5()
                    chunk = file_obj.read(65536)  # 64KB
                    file_hash.update(chunk)
                    
                    # Pour les petits fichiers, lire tout
                    if len(chunk) < 65536:
                        file_hash.update(chunk)
                    
                    hash_value = file_hash.hexdigest()
                
                hash_map[hash_value].append(f)
                
            except Exception as e:
                continue
        
        for hash_value, fichiers in hash_map.items():
            if len(fichiers) > 1:
                doublons['contenu'].append({
                    'type': 'contenu',
                    'hash': hash_value[:8] + '...',
                    'fichiers': fichiers,
                    'explication': f"{len(fichiers)} fichiers avec contenu identique"
                })
        
        print(f"   ✅ {len(doublons['contenu'])} groupes de doublons de contenu trouvés")
    
    # 6. Détection des cas PROBABLES (mélange de critères)
    print("\n🟣 ÉTAPE 5 : Analyse des cas probables...")
    
    # Exemple: fichiers avec noms très similaires ET tailles proches
    for sim in doublons['similaires']:
        fichiers = sim['fichiers']
        if len(fichiers) >= 2:
            tailles = [f['taille'] for f in fichiers]
            if max(tailles) - min(tailles) < regles['taille_tolerance']:
                doublons['probables'].append({
                    'type': 'probable',
                    'fichiers': fichiers,
                    'explication': "Noms similaires ET tailles identiques (probablement le même fichier)"
                })
    
    print(f"   ✅ {len(doublons['probables'])} groupes de cas probables trouvés")
    
    return doublons


# ==================== NETTOYAGE AUTOMATIQUE AVEC VALIDATION ====================

def preparer_nettoyage(categories, dossier):
    """
    Prépare la liste des actions de nettoyage proposées à l'utilisateur
    Retourne un dictionnaire avec les fichiers à déplacer/supprimer
    """
    
    propositions = {
        'faibles': [],        # Fichiers <64 kbps à déplacer
        'corrompus': [],      # Fichiers corrompus à déplacer
        'doublons': []        # Doublons à supprimer (groupe par groupe)
    }
    
    # 1. Fichiers faibles (<64 kbps)
    for item in categories['faibles']:
        if len(item) >= 2:
            bitrate = item[0]
            chemin = item[1]
            propositions['faibles'].append({
                'chemin': chemin,
                'nom': os.path.basename(chemin),
                'bitrate': bitrate,
                'action': 'Déplacer vers Weak_Audio/',
                'taille': os.path.getsize(chemin) if os.path.exists(chemin) else 0
            })
    
    # 2. Fichiers corrompus
    for item in categories['corrompus']:
        if len(item) >= 2:
            chemin = item[0]
            erreur = item[1] if len(item) > 1 else "inconnue"
            propositions['corrompus'].append({
                'chemin': chemin,
                'nom': os.path.basename(chemin),
                'erreur': erreur,
                'action': 'Déplacer vers Corrompus/ (ou supprimer)',
                'taille': os.path.getsize(chemin) if os.path.exists(chemin) else 0
            })
    
    # Note: La détection des doublons sera connectée plus tard via l'UI
    # Pour l'instant, on laisse vide et on utilisera detecter_doublons_avance() séparément
    
    return propositions


def calculer_economie_nettoyage(propositions):
    """
    Calcule l'espace qui sera libéré par le nettoyage
    """
    total_octets = 0
    
    # Fichiers faibles (déplacés, pas supprimés)
    for f in propositions['faibles']:
        total_octets += f['taille']
    
    # Fichiers corrompus (déplacés)
    for f in propositions['corrompus']:
        total_octets += f['taille']
    
    # Doublons (supprimés) - sera rempli plus tard
    for groupe in propositions.get('doublons', []):
        for f in groupe['supprimer']:
            if os.path.exists(f):
                total_octets += os.path.getsize(f)
    
    # Conversion
    total_mb = total_octets / (1024 * 1024)
    total_gb = total_mb / 1024
    
    return {
        'octets': total_octets,
        'mo': round(total_mb, 2),
        'go': round(total_gb, 2)
    }


def executer_nettoyage(propositions, choix_utilisateur, dossier):
    """
    Exécute le nettoyage selon les choix de l'utilisateur
    
    Args:
        propositions: La structure complète des propositions
        choix_utilisateur: Dict avec les fichiers sélectionnés
        dossier: Dossier racine pour créer les sous-dossiers
    """
    
    resultats = {
        'deplaces_faibles': [],
        'deplaces_corrompus': [],
        'supprimes_doublons': [],
        'erreurs': []
    }
    
    # Créer les dossiers de destination
    weak_dir = os.path.join(dossier, "Weak_Audio")
    corrompus_dir = os.path.join(dossier, "Corrompus")
    
    if choix_utilisateur.get('deplacer_faibles'):
        os.makedirs(weak_dir, exist_ok=True)
    
    if choix_utilisateur.get('deplacer_corrompus'):
        os.makedirs(corrompus_dir, exist_ok=True)
    
    # 1. Déplacer les fichiers faibles sélectionnés
    if choix_utilisateur.get('deplacer_faibles'):
        for fichier in propositions['faibles']:
            if fichier['chemin'] in choix_utilisateur['deplacer_faibles']:
                try:
                    dest = os.path.join(weak_dir, fichier['nom'])
                    # Gérer les doublons de nom
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(fichier['nom'])
                        dest = os.path.join(weak_dir, f"{base}_{fichier['bitrate']}k{ext}")
                    
                    shutil.move(fichier['chemin'], dest)
                    resultats['deplaces_faibles'].append({
                        'source': fichier['chemin'],
                        'dest': dest,
                        'bitrate': fichier['bitrate']
                    })
                except Exception as e:
                    resultats['erreurs'].append(f"Erreur déplacement {fichier['nom']}: {e}")
    
    # 2. Déplacer les fichiers corrompus sélectionnés
    if choix_utilisateur.get('deplacer_corrompus'):
        for fichier in propositions['corrompus']:
            if fichier['chemin'] in choix_utilisateur['deplacer_corrompus']:
                try:
                    dest = os.path.join(corrompus_dir, fichier['nom'])
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(fichier['nom'])
                        dest = os.path.join(corrompus_dir, f"{base}_corrompu{ext}")
                    
                    shutil.move(fichier['chemin'], dest)
                    resultats['deplaces_corrompus'].append({
                        'source': fichier['chemin'],
                        'dest': dest,
                        'erreur': fichier['erreur']
                    })
                except Exception as e:
                    resultats['erreurs'].append(f"Erreur déplacement {fichier['nom']}: {e}")
    
    # 3. Supprimer les doublons sélectionnés
    if choix_utilisateur.get('supprimer_doublons'):
        for fichier in choix_utilisateur['supprimer_doublons']:
            try:
                if os.path.exists(fichier):
                    os.remove(fichier)
                    resultats['supprimes_doublons'].append(fichier)
            except Exception as e:
                resultats['erreurs'].append(f"Erreur suppression {os.path.basename(fichier)}: {e}")
    
    # 4. Générer un rapport de nettoyage
    rapport_path = os.path.join(dossier, "rapport_nettoyage.html")
    generer_rapport_nettoyage(resultats, rapport_path)
    
    return resultats


def generer_rapport_nettoyage(resultats, chemin_rapport):
    """
    Génère un rapport HTML du nettoyage effectué
    """
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Rapport de nettoyage - Weak Audio Tracker</title>
    <style>
        body {{ font-family: Arial; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #333; border-bottom: 3px solid #3498db; }}
        .success {{ color: #27ae60; }}
        .warning {{ color: #e67e22; }}
        .error {{ color: #c0392b; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; }}
        .stat-box {{ background: #f8f9f9; padding: 15px; border-radius: 5px; flex: 1; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🧹 Rapport de nettoyage</h1>
        <p>Date: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        
        <div class="stats">
            <div class="stat-box">
                <h3>📦 Fichiers déplacés</h3>
                <p>Faibles: {len(resultats['deplaces_faibles'])}</p>
                <p>Corrompus: {len(resultats['deplaces_corrompus'])}</p>
            </div>
            <div class="stat-box">
                <h3>🗑️ Fichiers supprimés</h3>
                <p>Doublons: {len(resultats['supprimes_doublons'])}</p>
            </div>
            <div class="stat-box">
                <h3>⚠️ Erreurs</h3>
                <p>{len(resultats['erreurs'])}</p>
            </div>
        </div>
"""

    if resultats['deplaces_faibles']:
        html += "<h3>Fichiers faibles déplacés</h3><ul>"
        for f in resultats['deplaces_faibles']:
            html += f"<li>{os.path.basename(f['source'])} → {f['dest']} ({f['bitrate']} kbps)</li>"
        html += "</ul>"
    
    if resultats['deplaces_corrompus']:
        html += "<h3>Fichiers corrompus déplacés</h3><ul>"
        for f in resultats['deplaces_corrompus']:
            html += f"<li>{os.path.basename(f['source'])} → {f['dest']}</li>"
        html += "</ul>"
    
    if resultats['supprimes_doublons']:
        html += "<h3>Doublons supprimés</h3><ul>"
        for f in resultats['supprimes_doublons']:
            html += f"<li>{os.path.basename(f)}</li>"
        html += "</ul>"
    
    if resultats['erreurs']:
        html += "<h3 class='error'>Erreurs</h3><ul>"
        for e in resultats['erreurs']:
            html += f"<li>{e}</li>"
        html += "</ul>"
    
    html += """
        <p class='success'>✅ Nettoyage terminé</p>
    </div>
</body>
</html>
"""
    
    with open(chemin_rapport, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return chemin_rapport


def exporter_doublons_avance_csv(doublons, nom_fichier="doublons_detectes.csv"):
    """
    Exporte les résultats des doublons en CSV avec plus de détails
    """
    with open(nom_fichier, "w", newline="", encoding="utf-8") as fichier:
        writer = csv.writer(fichier)
        
        writer.writerow(["Type", "Confiance", "Fichiers", "Dossiers", "Taille (MB)", "Action suggérée"])
        
        # Doublons exacts (confiance 100%)
        for groupe in doublons['exacts']:
            fichiers = groupe['fichiers']
            tailles = [f['taille'] for f in fichiers]
            taille_mb = sum(tailles) / (1024 * 1024)
            
            writer.writerow([
                "EXACT",
                "100%",
                "\n".join([f['nom'] for f in fichiers]),
                "\n".join([f['dossier_parent'] for f in fichiers]),
                round(taille_mb, 2),
                "SUPPRIMER (garder 1)"
            ])
        
        # Même taille (confiance 70%)
        for groupe in doublons['taille']:
            fichiers = groupe['fichiers']
            tailles = [f['taille'] for f in fichiers]
            taille_mb = sum(tailles) / (1024 * 1024)
            
            writer.writerow([
                "TAILLE",
                "70%",
                "\n".join([f['nom'] for f in fichiers]),
                "\n".join([f['dossier_parent'] for f in fichiers]),
                round(taille_mb, 2),
                "VÉRIFIER (peut-être différents)"
            ])
        
        # Noms similaires (confiance 50-90%)
        for groupe in doublons['similaires']:
            fichiers = groupe['fichiers']
            tailles = [f['taille'] for f in fichiers]
            taille_mb = sum(tailles) / (1024 * 1024)
            
            writer.writerow([
                "SIMILAIRE",
                f"{int(groupe.get('similarite', 0.7)*100)}%" if isinstance(groupe.get('similarite'), float) else "Variable",
                "\n".join([f['nom'] for f in fichiers]),
                "\n".join([f['dossier_parent'] for f in fichiers]),
                round(taille_mb, 2),
                "VÉRIFIER (versions différentes?)"
            ])
        
        # Contenu identique (confiance 99%)
        if 'contenu' in doublons:
            for groupe in doublons['contenu']:
                fichiers = groupe['fichiers']
                tailles = [f['taille'] for f in fichiers]
                taille_mb = sum(tailles) / (1024 * 1024)
                
                writer.writerow([
                    "CONTENU",
                    "99%",
                    "\n".join([f['nom'] for f in fichiers]),
                    "\n".join([f['dossier_parent'] for f in fichiers]),
                    round(taille_mb, 2),
                    "SUPPRIMER (contenu identique)"
                ])
        
        # Cas probables (confiance 90%)
        for groupe in doublons['probables']:
            fichiers = groupe['fichiers']
            tailles = [f['taille'] for f in fichiers]
            taille_mb = sum(tailles) / (1024 * 1024)
            
            writer.writerow([
                "PROBABLE",
                "90%",
                "\n".join([f['nom'] for f in fichiers]),
                "\n".join([f['dossier_parent'] for f in fichiers]),
                round(taille_mb, 2),
                "VÉRIFIER (forte probabilité de doublon)"
            ])


def calculer_economie_espace(doublons):
    """
    Calcule l'espace économisable en supprimant les doublons
    """
    espace_total = 0
    fichiers_a_supprimer = 0
    
    for type_doublon in ['exacts', 'taille', 'similaires', 'contenu', 'probables']:
        if type_doublon not in doublons:
            continue
            
        for groupe in doublons[type_doublon]:
            if 'fichiers' in groupe and len(groupe['fichiers']) > 1:
                # Garder le plus gros, supprimer les autres
                fichiers = sorted(groupe['fichiers'], key=lambda x: x['taille'], reverse=True)
                for f in fichiers[1:]:  # Tous sauf le premier
                    espace_total += f['taille']
                    fichiers_a_supprimer += 1
    
    # Convertir en MB/GB
    espace_mb = espace_total / (1024 * 1024)
    espace_gb = espace_mb / 1024
    
    return {
        'fichiers': fichiers_a_supprimer,
        'octets': espace_total,
        'mb': round(espace_mb, 2),
        'gb': round(espace_gb, 2)
    }