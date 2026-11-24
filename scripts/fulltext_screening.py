#!/usr/bin/env python3
"""Lab 6, étape 10 - Aide au screening des textes intégraux (PDF).

Lit les PDF de pdfs/<ID_unique>.pdf (ex. pdfs/U012.pdf), extrait le texte avec PyMuPDF et
recherche, pour chaque critère vérifiable sur le texte intégral, les indices présents :
  E4 capteur    : termes de plateforme aérienne/satellitaire vs termes de mesures au sol ou sur feuilles
  E5 méthode    : modèle appris + termes d'évaluation (accuracy, kappa, cross-validation, test set...)
  E6 contribution : marqueurs de revue de littérature
Le script PROPOSE une décision ; la décision finale est prise par l'évaluatrice et consignée
dans le tableau de tri (les PDF ne sont pas publiés : droits d'auteur).

Sortie : output/10_aide_texte_integral.csv
Usage  : python scripts/fulltext_screening.py [dossier_pdfs]
"""
import re
import sys
from pathlib import Path

import pandas as pd

try:
    import pymupdf as fitz
except ImportError:  # anciennes versions
    import fitz

ROOT = Path(__file__).resolve().parent.parent

AERIAL = ["uav", "drone", "unmanned aerial", "airborne", "aircraft", "satellite", "sentinel-2", "sentinel 2", "landsat",
          "planetscope", "modis", "worldview", "aerial imag", "flight altitude"]
GROUND = ["hand-held", "handheld", "leaf sample", "leaf images", "smartphone", "laboratory", "spectroradiometer",
          "leaf clip", "detached leaves", "pot experiment"]
MODEL = ["random forest", "support vector", "svm", "neural network", "cnn", "deep learning", "xgboost", "gradient boosting",
         "discriminant analysis", "gaussian process", "yolo", "k-nearest", "decision tree", "classifier"]
EVAL = ["accuracy", "kappa", "cross-validation", "cross validation", "test set", "f1", "precision", "recall", "rmse", "r2", "auc"]
REVIEW = ["systematic review", "literature review", "this review", "we review"]


def count(text, words):
    return sum(len(re.findall(rf"(?<![a-z]){re.escape(w)}", text)) for w in words)


def extract_text(pdf_path):
    with fitz.open(pdf_path) as doc:
        return "\n".join(page.get_text() for page in doc)


def suggest(text):
    t = text.lower()
    ev = {"aerien": count(t, AERIAL), "sol_feuille": count(t, GROUND), "modele": count(t, MODEL),
          "evaluation": count(t, EVAL), "revue": count(t, REVIEW)}
    if ev["revue"] >= 2 and ev["evaluation"] == 0:
        return ev, "Exclure", "E6"
    if ev["aerien"] == 0:
        return ev, "Exclure", "E4"
    if ev["modele"] == 0:
        return ev, "Exclure", "E5"
    if ev["sol_feuille"] > ev["aerien"] or ev["evaluation"] == 0:
        return ev, "Incertain", ""
    return ev, "Inclure", ""


def main(folder):
    rows = []
    for pdf in sorted(Path(folder).glob("*.pdf")):
        ev, dec, motif = suggest(extract_text(pdf))
        rows.append({"ID_unique": pdf.stem, **ev, "Proposition": dec, "Motif_propose": motif,
                     "Decision_finale": "", "Evaluateur": "", "Commentaire": ""})
    out = ROOT / "output" / "10_aide_texte_integral.csv"
    out.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows, columns=["ID_unique", "aerien", "sol_feuille", "modele", "evaluation", "revue", "Proposition",
                                "Motif_propose", "Decision_finale", "Evaluateur", "Commentaire"]).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"Texte extrait pour {len(rows)} document(s) -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "pdfs")
