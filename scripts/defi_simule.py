#!/usr/bin/env python3
"""Lab 6, défi 1 - Applique le pré-screening automatique aux 10 références simulées de data/exemple_simule.csv.

Les références sont inventées pour couvrir chaque critère (une inclusion, un exemple par motif E1 à E8, un cas incertain).
Usage : python scripts/defi_simule.py   ->  output/12_defi_simule_resultats.csv
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screening  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def run(path=ROOT / "data" / "exemple_simule.csv"):
    cfg = json.loads(screening.CFG.read_text(encoding="utf-8"))
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    res = df.apply(lambda r: screening.auto_screen(r, cfg), axis=1)
    df["Decision"] = [r[1] for r in res]
    df["Motif"] = [r[2] for r in res]
    df["Signaux_de_doute"] = ["; ".join(r[3]) for r in res]
    df["Obtenu"] = (df["Decision"] + " " + df["Motif"]).str.strip()
    df["Conforme"] = df["Obtenu"] == df["Attendu"]
    return df


if __name__ == "__main__":
    df = run()
    out = ROOT / "output" / "12_defi_simule_resultats.csv"
    df[["ID_unique", "Titre", "Attendu", "Obtenu", "Conforme", "Signaux_de_doute"]].to_csv(out, index=False, encoding="utf-8-sig")
    c = Counter(df["Decision"])
    print(f"Inclure : {c['Inclure']} ; Exclure : {c['Exclure']} ; Incertain : {c['Incertain']}  "
          f"(conformes à l'attendu : {int(df['Conforme'].sum())}/{len(df)})")
    print(df[["ID_unique", "Attendu", "Obtenu"]].to_string(index=False))
