# graphiques.py
# Module de visualisation des statistiques audio
# CORRIGÉ : Utilisation du CSS externe

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class GraphiquesAudio:
    
    def __init__(self):
        plt.style.use('seaborn-v0_8-darkgrid')
        self.couleurs = {
            'bons': '#2ecc71',
            'moyens': '#f39c12',
            'faibles': '#e74c3c',
            'reparés': '#3498db',
            'corrompus': '#95a5a6',
            'non_audio': '#7f8c8d'
        }
    
    def graphique_camembert(self, categories, stats, total_fichiers_os):
        labels, valeurs, couleurs = [], [], []
        
        if categories['bons']:
            labels.append('Bonne qualité (≥128 kbps)')
            valeurs.append(len(categories['bons']))
            couleurs.append(self.couleurs['bons'])
        
        if categories['moyens']:
            labels.append('Qualité moyenne (64-127 kbps)')
            valeurs.append(len(categories['moyens']))
            couleurs.append(self.couleurs['moyens'])
        
        if categories['faibles']:
            labels.append('Faible qualité (<64 kbps)')
            valeurs.append(len(categories['faibles']))
            couleurs.append(self.couleurs['faibles'])
        
        if categories['reparés']:
            labels.append('Fichiers réparés')
            valeurs.append(len(categories['reparés']))
            couleurs.append(self.couleurs['reparés'])
        
        if categories['corrompus']:
            labels.append('Fichiers corrompus')
            valeurs.append(len(categories['corrompus']))
            couleurs.append(self.couleurs['corrompus'])
        
        non_audio = total_fichiers_os - stats['total_trouves']
        if non_audio > 0:
            labels.append('Fichiers non-audio')
            valeurs.append(non_audio)
            couleurs.append(self.couleurs['non_audio'])
        
        fig, ax = plt.subplots(figsize=(8, 6))
        wedges, texts, autotexts = ax.pie(
            valeurs, labels=labels, colors=couleurs,
            autopct='%1.1f%%', startangle=90,
            textprops={'fontsize': 10}, pctdistance=0.85
        )
        
        for text in texts:
            text.set_fontsize(9)
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(9)
        
        centre = plt.Circle((0, 0), 0.70, fc='white', linewidth=0)
        ax.add_artist(centre)
        ax.set_title('Répartition de la bibliothèque audio', fontsize=14, fontweight='bold')
        ax.axis('equal')
        return fig
    
    def graphique_barres(self, categories):
        bitrates = {}
        for cat in ['bons', 'moyens', 'faibles']:
            for fichier in categories[cat]:
                if len(fichier) >= 2:
                    br = fichier[0]
                    bitrates[br] = bitrates.get(br, 0) + 1
        
        fig, ax = plt.subplots(figsize=(12, 6))
        bars = ax.bar([str(b) for b in sorted(bitrates.keys())],
                      [bitrates[b] for b in sorted(bitrates.keys())],
                      color='#3498db', edgecolor='black', linewidth=0.5)
        
        for bar in bars:
            h = bar.get_height()
            if h > 5:
                ax.text(bar.get_x() + bar.get_width()/2, h,
                       f'{int(h)}', ha='center', va='bottom', fontsize=8)
        
        ax.set_xlabel('Bitrate (kbps)', fontsize=11)
        ax.set_ylabel('Nombre de fichiers', fontsize=11)
        ax.set_title('Distribution des bitrates', fontsize=14, fontweight='bold')
        ax.tick_params(axis='x', rotation=45, labelsize=9)
        ax.grid(True, axis='y', alpha=0.3)
        plt.tight_layout()
        return fig
    
    def sauvegarder_rapport_html(self, categories, stats, total_fichiers_os, dossier):
        fig1 = self.graphique_camembert(categories, stats, total_fichiers_os)
        fig2 = self.graphique_barres(categories)
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        reports_dir = os.path.join(dossier, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        chemin_camembert = os.path.join(reports_dir, f"camembert_{timestamp}.png")
        chemin_barres = os.path.join(reports_dir, f"barres_{timestamp}.png")
        
        fig1.savefig(chemin_camembert, dpi=100, bbox_inches='tight')
        fig2.savefig(chemin_barres, dpi=100, bbox_inches='tight')
        plt.close(fig1)
        plt.close(fig2)
        
        non_audio = total_fichiers_os - stats['total_trouves']
        
        # Lire le CSS externe
        css_path = os.path.join(ROOT_DIR, "assets", "styles", "rapport_style.css")
        if os.path.exists(css_path):
            with open(css_path, 'r', encoding='utf-8') as f:
                css_content = f.read()
        else:
            css_content = """
                body { font-family: Arial; margin:20px; background:#f5f5f5; }
                .container { max-width:1200px; margin:0 auto; background:white; padding:20px; border-radius:8px; }
                h1 { color:#333; border-bottom:3px solid #3498db; padding-bottom:10px; }
                .stats { display:flex; flex-wrap:wrap; gap:20px; margin:20px 0; }
                .stat-box { background:#f8f9f9; padding:15px; border-radius:5px; flex:1 1 200px; border-left:4px solid #3498db; }
                .stat-box.green { border-left-color:#2ecc71; }
                .stat-box.orange { border-left-color:#f39c12; }
                .stat-box.red { border-left-color:#e74c3c; }
                .stat-box.blue { border-left-color:#3498db; }
                .stat-box.gray { border-left-color:#95a5a6; }
                .stat-value { font-size:24px; font-weight:bold; color:#333; }
                .stat-label { font-size:14px; color:#7f8c8d; }
                .graphiques { display:flex; flex-wrap:wrap; gap:20px; margin:30px 0; }
                .graphique { flex:1 1 500px; text-align:center; }
                .graphique img { max-width:100%; border:1px solid #ddd; border-radius:4px; padding:5px; }
                table { width:100%; border-collapse:collapse; margin:20px 0; }
                th, td { padding:10px; text-align:left; border-bottom:1px solid #ddd; }
                th { background:#3498db; color:white; }
                .footer { text-align:center; margin-top:30px; color:#7f8c8d; font-size:12px; }
            """
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Rapport d'analyse audio</title>
    <style>
        {css_content}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Rapport d'analyse audio</h1>
        <p>Date: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <p>Dossier: {dossier}</p>
        
        <div class="stats">
            <div class="stat-box green">
                <div class="stat-value">{len(categories['bons'])}</div>
                <div class="stat-label">Bonne qualité</div>
            </div>
            <div class="stat-box orange">
                <div class="stat-value">{len(categories['moyens'])}</div>
                <div class="stat-label">Qualité moyenne</div>
            </div>
            <div class="stat-box red">
                <div class="stat-value">{len(categories['faibles'])}</div>
                <div class="stat-label">Faible qualité</div>
            </div>'''
        
        if categories['reparés']:
            html += f'<div class="stat-box blue"><div class="stat-value">{len(categories["reparés"])}</div><div class="stat-label">Fichiers réparés</div></div>'
        if non_audio > 0:
            html += f'<div class="stat-box gray"><div class="stat-value">{non_audio}</div><div class="stat-label">Fichiers non-audio</div></div>'
        
        html += f'''
        </div>
        
        <div class="graphiques">
            <div class="graphique">
                <h3>Répartition de la bibliothèque</h3>
                <img src="{os.path.basename(chemin_camembert)}" alt="Camembert">
            </div>
            <div class="graphique">
                <h3>Distribution des bitrates</h3>
                <img src="{os.path.basename(chemin_barres)}" alt="Barres">
            </div>
        </div>
        
        <h2>Fichiers de faible qualité</h2>
        <table>
            <thead>
                <tr>
                    <th>Bitrate</th>
                    <th>Fichier</th>
                </tr>
            </thead>
            <tbody>'''
        
        for f in categories['faibles'][:20]:
            if len(f) >= 2:
                html += f'<tr><td>{f[0]} kbps</td><td>{os.path.basename(f[1])}</td></tr>'
        if len(categories['faibles']) > 20:
            html += f'<tr><td colspan="2" style="text-align:center;">... et {len(categories["faibles"])-20} autres fichiers</td></tr>'
        
        html += '''
            </tbody>
        </table>
        
        <div class="footer">
            Rapport généré par Weak Audio Tracker v1.0
        </div>
    </div>
</body>
</html>'''
        
        chemin_html = os.path.join(reports_dir, f"rapport_{timestamp}.html")
        with open(chemin_html, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return chemin_html