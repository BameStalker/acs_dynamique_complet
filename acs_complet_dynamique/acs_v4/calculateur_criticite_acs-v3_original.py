import os
import sys
import json
import unicodedata
import pandas as pd

def normalize_string(s: str) -> str:
    """Supprime les accents, le BOM UTF-8 et met en minuscules pour faciliter les correspondances."""
    if not isinstance(s, str):
        s = str(s)
    s = s.lstrip('\ufeff')
    s_norm = unicodedata.normalize('NFD', s)
    s_no_accent = ''.join(c for c in s_norm if unicodedata.category(c) != 'Mn')
    return s_no_accent.lower()

class AssetCriticalityCalculator:
    """
    Calculateur de criticité des actifs informatiques (v3).
    Permet le chargement d'inventaire depuis des fichiers CSV ou Excel (.xlsx).
    Intègre la classification automatique C-I-A-T et la comparaison avec Kotenko et al.
    """

    DEFAULT_CIA_PROFILES = {
        "active_directory": {
            "keywords": ["ad", "active directory", "domaine", "dc", "identity", "identite"],
            "scores": {"C": 10, "I": 10, "A": 9, "T": 9},
            "description": "Contrôleur de domaine & gestion d'identités"
        },
        "pki": {
            "keywords": ["pki", "ca", "certification", "certificat", "cle"],
            "scores": {"C": 10, "I": 10, "A": 6, "T": 3},
            "description": "Autorité de certification & gestion des clés"
        },
        "backup": {
            "keywords": ["backup", "sauvegarde", "san", "storage", "archivage"],
            "scores": {"C": 10, "I": 9, "A": 5, "T": 4},
            "description": "Système de sauvegarde & stockage de données"
        },
        "database": {
            "keywords": ["db", "database", "base de donnees", "sql", "oracle", "postgres"],
            "scores": {"C": 8, "I": 9, "A": 8, "T": 6},
            "description": "Serveur de base de données de production"
        },
        "web_public": {
            "keywords": ["web", "frontend", "public", "http", "portal", "portail"],
            "scores": {"C": 3, "I": 6, "A": 8, "T": 7},
            "description": "Serveur web exposé ou portail public"
        },
        "network_core": {
            "keywords": ["switch", "commutateur", "router", "routeur", "coeur", "core", "network", "reseau"],
            "scores": {"C": 5, "I": 8, "A": 10, "T": 10},
            "description": "Équipement de cœur de réseau & routage"
        },
        "firewall": {
            "keywords": ["firewall", "pare-feu", "parefeu", "gateway", "passerelle", "vpn"],
            "scores": {"C": 6, "I": 9, "A": 10, "T": 9},
            "description": "Équipement de sécurité périphérique"
        },
        "workstation": {
            "keywords": ["workstation", "poste", "user", "utilisateur", "client", "laptop"],
            "scores": {"C": 2, "I": 3, "A": 3, "T": 2},
            "description": "Poste de travail utilisateur"
        }
    }

    COLUMN_MAPPINGS = {
        "nom": ["nom", "nom_actif", "nom_de_l_actif", "asset_name", "name", "hostname", "equipement"],
        "type": ["type", "type_actif", "role", "asset_type", "category", "categorie"],
        "evenements_count": ["evenements_count", "evenements", "logs", "events", "events_count", "frequence", "count"],
        "confidentialite": ["confidentialite", "c", "confidentiality"],
        "integrite": ["integrite", "i", "integrity"],
        "disponibilite": ["disponibilite", "a", "availability"],
        "topologie": ["topologie", "t", "topology", "connectivite"]
    }

    def __init__(self, weights=None):
        self.weights = weights or {
            'w_C': 0.35,  # Confidentialité
            'w_I': 0.25,  # Intégrité
            'w_A': 0.20,  # Disponibilité
            'w_T': 0.20   # Topologie / Connectivité réseau
        }
        self._validate_weights()

    def _validate_weights(self):
        total = sum(self.weights.values())
        if not abs(total - 1.0) < 1e-5:
            raise ValueError(f"La somme des poids doit être égale à 1.0 (actuellement {total})")

    def classify_cia_by_type(self, asset_type: str) -> dict:
        type_norm = normalize_string(asset_type)
        for category, config in self.DEFAULT_CIA_PROFILES.items():
            for kw in config["keywords"]:
                kw_norm = normalize_string(kw)
                if kw_norm in type_norm:
                    res = config["scores"].copy()
                    res["profile_matched"] = config["description"]
                    return res
        return {
            "C": 5, "I": 5, "A": 5, "T": 5,
            "profile_matched": "Profil standard par défaut"
        }

    def auto_enrich_asset(self, asset: dict) -> dict:
        asset_copy = asset.copy()
        auto_scores = self.classify_cia_by_type(asset_copy.get("type", ""))

        is_manual = ("confidentialite" in asset_copy and "integrite" in asset_copy and 
                     "disponibilite" in asset_copy and pd.notna(asset_copy.get("confidentialite")))

        if not is_manual:
            asset_copy["confidentialite"] = float(auto_scores["C"])
            asset_copy["integrite"] = float(auto_scores["I"])
            asset_copy["disponibilite"] = float(auto_scores["A"])
            asset_copy["topologie"] = float(asset_copy.get("topologie") if pd.notna(asset_copy.get("topologie")) else auto_scores["T"])
            asset_copy["profil_source"] = f"Auto ({auto_scores['profile_matched']})"
        else:
            asset_copy["confidentialite"] = float(asset_copy["confidentialite"])
            asset_copy["integrite"] = float(asset_copy["integrite"])
            asset_copy["disponibilite"] = float(asset_copy["disponibilite"])
            asset_copy["topologie"] = float(asset_copy.get("topologie") if pd.notna(asset_copy.get("topologie")) else auto_scores["T"])
            asset_copy["profil_source"] = "Saisie Manuelle"

        return asset_copy

    def calculate_acs(self, c: float, i: float, a: float, t: float) -> float:
        score = (
            self.weights['w_C'] * c +
            self.weights['w_I'] * i +
            self.weights['w_A'] * a +
            self.weights['w_T'] * t
        )
        return round(score, 2)

    def calculate_kotenko_cr(self, assets_data: list) -> list:
        sorted_assets = sorted(assets_data, key=lambda x: x['evenements_count'])
        n_total_events = sum(x['evenements_count'] for x in assets_data)
        
        freq_levels = sorted(list(set(x['evenements_count'] for x in sorted_assets)))
        total_levels = len(freq_levels)

        for asset in assets_data:
            event_count = asset['evenements_count']
            level_rank = freq_levels.index(event_count) + 1
            asset['kotenko_mu'] = round(event_count / n_total_events, 4) if n_total_events > 0 else 0
            asset['kotenko_level'] = level_rank
            asset['kotenko_cr'] = round(level_rank / total_levels, 2)

        return assets_data

    def _map_dataframe_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Harmonise les noms de colonnes du DataFrame selon le dictionnaire de correspondance."""
        df_clean = df.copy()
        
        mapped_cols = {}
        for col in df_clean.columns:
            col_norm = normalize_string(str(col)).strip().replace(' ', '_')
            found = False
            for target_col, synonyms in self.COLUMN_MAPPINGS.items():
                for synonym in synonyms:
                    syn_norm = normalize_string(synonym).strip().replace(' ', '_')
                    if col_norm == syn_norm:
                        mapped_cols[col] = target_col
                        found = True
                        break
                if found:
                    break
        
        df_mapped = df_clean.rename(columns=mapped_cols)
        
        if "nom" not in df_mapped.columns:
            raise ValueError(f"Le fichier doit contenir au moins une colonne identifiant le nom de l'actif. Colonnes détectées: {list(df_mapped.columns)}")
        if "type" not in df_mapped.columns:
            df_mapped["type"] = "Inconnu"
        if "evenements_count" not in df_mapped.columns:
            df_mapped["evenements_count"] = 1000

        df_mapped["evenements_count"] = pd.to_numeric(df_mapped["evenements_count"], errors="coerce").fillna(1000).astype(int)
        
        return df_mapped

    def process_inventory(self, assets: list) -> pd.DataFrame:
        enriched_assets = [self.auto_enrich_asset(a) for a in assets]
        enriched_assets = self.calculate_kotenko_cr(enriched_assets)

        results = []
        for a in enriched_assets:
            acs_score = self.calculate_acs(
                c=a['confidentialite'],
                i=a['integrite'],
                a=a['disponibilite'],
                t=a['topologie']
            )
            
            if acs_score >= 8.0:
                niveau = "Critique (Très Élevé)"
            elif acs_score >= 6.0:
                niveau = "Élevé"
            elif acs_score >= 4.0:
                niveau = "Moyen"
            else:
                niveau = "Faible"

            results.append({
                "Nom de l'actif": a['nom'],
                "Type / Rôle": a['type'],
                "Événements (Logs)": a['evenements_count'],
                "Kotenko µ": a['kotenko_mu'],
                "Kotenko Cr": a['kotenko_cr'],
                "C": int(a['confidentialite']),
                "I": int(a['integrite']),
                "A": int(a['disponibilite']),
                "T": int(a['topologie']),
                "Score ACS (/10)": acs_score,
                "Niveau de Criticité ACS": niveau,
                "Écart (ACS - Cr*10)": round(acs_score - (a['kotenko_cr'] * 10), 2),
                "Origine Profil C-I-A": a['profil_source']
            })

        df = pd.DataFrame(results)
        return df.sort_values(by="Score ACS (/10)", ascending=False)

    def load_from_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df_mapped = self._map_dataframe_columns(df)
        assets_list = df_mapped.to_dict(orient="records")
        return self.process_inventory(assets_list)

    def load_from_file(self, file_path: str) -> pd.DataFrame:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Fichier non trouvé : {file_path}")
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.csv', '.txt']:
            try:
                df = pd.read_csv(file_path, sep=None, engine='python')
            except Exception:
                df = pd.read_csv(file_path, sep=';')
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Format de fichier non supporté : {ext}. Utilisez .csv ou .xlsx")

        return self.load_from_dataframe(df)

    @staticmethod
    def generate_sample_csv(output_path: str = "inventaire_exemple.csv"):
        sample_data = pd.DataFrame([
            {"nom": "dc-ad-principal", "type": "Contrôleur de Domaine (AD)", "evenements_count": 85000, "confidentialite": 10, "integrite": 10, "disponibilite": 9, "topologie": 9},
            {"nom": "fw-perimeter-01", "type": "Pare-feu Périphérique / VPN", "evenements_count": 210000},
            {"nom": "db-prod-sql", "type": "Serveur de Base de Données SQL", "evenements_count": 68000},
            {"nom": "srv-pki-ca", "type": "Autorité de Certification (PKI)", "evenements_count": 45},
            {"nom": "core-switch-01", "type": "Commutateur Cœur de Réseau", "evenements_count": 45000},
            {"nom": "db-backup-san", "type": "Base de Sauvegarde / SAN", "evenements_count": 120},
            {"nom": "srv-web-frontend", "type": "Serveur Web Public", "evenements_count": 125000},
            {"nom": "workstation-user-42", "type": "Poste de Travail Utilisateur", "evenements_count": 12000}
        ])
        sample_data.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"Fichier d'exemple généré avec succès : {output_path}")

if __name__ == "__main__":
    calc = AssetCriticalityCalculator()

    if len(sys.argv) > 1:
        target_file = sys.argv[1]
        print(f"=== CHARGEMENT DE L'INVENTAIRE DEPUIS : {target_file} ===")
        df_results = calc.load_from_file(target_file)
    else:
        csv_sample = "inventaire_exemple.csv"
        calc.generate_sample_csv(csv_sample)
        print(f"=== CHARGEMENT ET CALCUL DEPUIS {csv_sample} ===")
        df_results = calc.load_from_file(csv_sample)

    print("\n=== RÉSULTATS COMPARATIFS DE CRITICITÉ DES ACTIFS ===")
    print(df_results[["Nom de l'actif", "Type / Rôle", "C", "I", "A", "T", "Kotenko Cr", "Score ACS (/10)", "Niveau de Criticité ACS", "Origine Profil C-I-A"]].to_string(index=False))
