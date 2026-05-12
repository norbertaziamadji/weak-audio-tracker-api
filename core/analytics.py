"""
Module de télémétrie anonyme pour Weak Audio Tracker
"""

import json
import os
import platform
import uuid
import datetime
import traceback

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class Analytics:
    """Gestionnaire de collecte de données anonymes"""

    def __init__(self, root_dir, consent_file="settings.json"):
        self.root_dir = root_dir
        self.data_dir = os.path.join(root_dir, "data")
        self.sessions_dir = os.path.join(self.data_dir, "analytics")
        self.config_path = os.path.join(self.data_dir, consent_file)

        os.makedirs(self.sessions_dir, exist_ok=True)
        self.load_config()
        self.start_session()

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except:
                self.config = self._default_config()
        else:
            self.config = self._default_config()

    def _default_config(self):
        return {
            "telemetry_consent": None,
            "version": "1.0",
            "last_prompt": None
        }

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)

    def has_consent(self):
        return self.config.get("telemetry_consent") is True

    def set_consent(self, accepted):
        self.config["telemetry_consent"] = accepted
        self.config["last_prompt"] = datetime.datetime.now().isoformat()
        self.save_config()
        if accepted:
            self.log_event("analytics_consent", {"accepted": True})

    def start_session(self):
        self.session_id = str(uuid.uuid4())
        self.session_data = {
            "session_id": self.session_id,
            "version": "1.0.0",
            "start_time": datetime.datetime.now().isoformat(),
            "system": self.get_system_info(),
            "events": [],
            "errors": []
        }

    def get_system_info(self):
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count()
        }
        if HAS_PSUTIL:
            info["ram_mb"] = int(psutil.virtual_memory().total / (1024 * 1024))
        return info

    def log_event(self, event_type, data=None):
        if not self.has_consent():
            return
        event = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": event_type,
            "data": data or {}
        }
        self.session_data["events"].append(event)

    def log_error(self, error):
        if not self.has_consent():
            return
        tb = traceback.extract_tb(error.__traceback__)[-1]
        error_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": type(error).__name__,
            "file": os.path.basename(tb.filename),
            "line": tb.lineno,
            "message": str(error)[:200]
        }
        self.session_data["errors"].append(error_data)
        self.log_event("error", error_data)

    def end_session(self, save=True):
        self.session_data["end_time"] = datetime.datetime.now().isoformat()
        if save and self.has_consent():
            self.save_session()
        return self.session_data

    def save_session(self):
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        session_dir = os.path.join(self.sessions_dir, date_str)
        os.makedirs(session_dir, exist_ok=True)
        filepath = os.path.join(session_dir, f"{self.session_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.session_data, f, indent=2)

    # Méthodes pratiques
    def log_analysis_start(self, folder, options):
        self.log_event("analysis_start", {
            "folder": os.path.basename(folder),
            "options": options
        })

    def log_analysis_complete(self, stats, duration_sec):
        self.log_event("analysis_complete", {
            "files": stats.get('total_trouves', 0),
            "repaired": stats.get('total_reparations', 0),
            "duration_sec": duration_sec,
            "bons": len(stats.get('bons', [])),
            "moyens": len(stats.get('moyens', [])),
            "faibles": len(stats.get('faibles', []))
        })

    def log_cleanup(self, results):
        self.log_event("cleanup", {
            "faibles": len(results.get('deplaces_faibles', [])),
            "corrompus": len(results.get('deplaces_corrompus', [])),
            "doublons": len(results.get('supprimes_doublons', []))
        })

    def log_feature_usage(self, feature):
        self.log_event("feature_usage", {"feature": feature})