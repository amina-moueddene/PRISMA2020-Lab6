#!/usr/bin/env python3
"""Lab 6 - Screening des titres, résumés et textes intégraux (PRISMA 2020).

Revue : Machine learning and remote sensing for disease and stress detection in olive.

Entrées
  data/dataset_lab5_public.csv            sortie du Lab 5 (144 références, sans résumés)
  local/dataset_lab5_avec_resumes.csv     même fichier avec résumés (non publié ; facultatif)
  config/criteres.json                    critères E1 à E8 du protocole
  data/Screening_ledger_olive_PRISMA2020.csv   décisions humaines de la SLR (titre/résumé, re-tri à l'aveugle, texte intégral)
  data/decisions_complementaires.csv      décisions pour les références absentes du tableau de la SLR

Étapes (numérotées comme le lab)
  3  chargement du dataset dédupliqué
  4  critères d'inclusion et d'exclusion          (config/criteres.json)
  5  grille vide de screening                      -> output/05_grille_screening_titres.xlsx
  6  pré-screening automatique par mots-clés       -> output/06_grille_preremplie.xlsx, 06_eval_script_vs_humain.csv
  7  décisions humaines et motifs                  -> output/07_decisions_titre_resume.csv
  8  double screening, accord et kappa             -> output/08_desaccords.csv, 08_log_resolutions.txt, 08_accord.json
  9  liste pour la récupération des textes         -> output/09_liste_textes_integraux.csv
  10 décisions sur texte intégral                  -> output/10_decisions_texte_integral.csv  (aide PDF : scripts/fulltext_screening.py)
  11 tableau maître et chiffres PRISMA             -> output/11_tableau_maitre.csv, 11_prisma.json, 11_diagramme_prisma.png

Usage : python scripts/screening.py
"""
import json
import re
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "criteres.json"
PUBLIC = ROOT / "data" / "dataset_lab5_public.csv"
LOCAL = ROOT / "local" / "dataset_lab5_avec_resumes.csv"
LEDGER = ROOT / "data" / "Screening_ledger_olive_PRISMA2020.csv"
EXTRA = ROOT / "data" / "decisions_complementaires.csv"
OUT = ROOT / "output"

ORDER = ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8"]


# ------------------------------------------------------------------ outils
def norm_title(t):
    t = "".join(c for c in unicodedata.normalize("NFKD", str(t).lower()) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


def norm_doi(d):
    d = str(d).strip().lower()
    return re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", d).rstrip(".;, ")


def has(text, words):
    """Vrai si l'un des mots ou expressions est présent (limites de mot pour les termes courts)."""
    t = f" {text} "
    for w in words:
        if len(w.strip()) <= 4:
            if re.search(rf"(?<![a-z]){re.escape(w.strip())}(?![a-z])", t):
                return True
        elif w in t:
            return True
    return False


def cohen_kappa(a, b):
    """Kappa de Cohen pour deux listes de décisions de même longueur (implémentation directe)."""
    if len(a) != len(b) or not a:
        raise ValueError("listes de même longueur, non vides")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def percent_agreement(a, b):
    return 100 * sum(x == y for x, y in zip(a, b)) / len(a)


# ------------------------------------------------------------------ étape 3
def load_dataset():
    df = pd.read_csv(PUBLIC, encoding="utf-8-sig", dtype=str).fillna("")
    with_abstracts = LOCAL.exists()
    if with_abstracts:
        loc = pd.read_csv(LOCAL, encoding="utf-8-sig", dtype=str).fillna("")
        df = df.merge(loc[["ID_unique", "Resume", "Mots_cles"]], on="ID_unique", how="left").fillna("")
    else:
        df["Resume"], df["Mots_cles"] = "", ""
    return df, with_abstracts


# ------------------------------------------------------------------ étape 6
def auto_screen(row, cfg):
    """Pré-screening par mots-clés. Renvoie (réponses par critère, décision, motif, signaux de doute)."""
    crit = {c["code"]: c for c in cfg["criteres"]}
    title = norm_title(row["Titre"])
    text = norm_title(" ".join([row["Titre"], row.get("Resume", ""), row.get("Mots_cles", "")]))
    dtype = str(row.get("Type_document", "")).strip().lower()
    lang = str(row.get("Langue", "")).strip().lower()
    year = int(row["Annee"]) if str(row.get("Annee", "")).isdigit() else None
    ans, doubts = {}, []

    ans["E1"] = year is None or cfg["periode"]["debut"] <= year <= cfg["periode"]["fin"]
    ans["E2"] = has(text, crit["E2"]["mots_requis"])
    if ans["E2"] and has(title, crit["E2"]["mots_hors_sujet"]):
        doubts.append("titre orienté huile/aliment/pollen")
    ans["E3"] = has(text, crit["E3"]["mots_requis"])
    if ans["E3"] and not has(text, [w for w in crit["E3"]["mots_requis"] if w not in crit["E3"]["mots_faibles"]]):
        doubts.append("cible seulement générique (stress, santé)")
    ans["E4"] = has(text, crit["E4"]["mots_requis"])
    if ans["E4"] and has(text, crit["E4"]["mots_doute"]):
        doubts.append("indices de mesures au sol ou sur feuilles")
    ans["E5"] = has(text, crit["E5"]["mots_requis"])
    if ans["E5"] and not has(text, [w for w in crit["E5"]["mots_requis"] if w not in crit["E5"]["mots_faibles"]]):
        doubts.append("méthode seulement « classification »")
    ans["E6"] = dtype not in crit["E6"]["types_exclus"] and not has(title, [norm_title(w) for w in crit["E6"]["mots_exclus_titre"]])
    ans["E7"] = dtype not in crit["E7"]["types_exclus"]
    ans["E8"] = lang == "" or any(l in lang for l in cfg["langues"])

    failed = [c for c in ORDER if not ans[c]]
    if failed:
        return ans, "Exclure", failed[0], doubts
    if doubts:
        return ans, "Incertain", "", doubts
    return ans, "Inclure", "", doubts


# ------------------------------------------------------------------ rattachement au tableau de la SLR
def match_ledger(df, led):
    led = led.copy()
    led["d"] = led["doi"].map(norm_doi)
    led["t"] = led["title"].map(norm_title)
    free, match = set(led.index), {}
    for crit in ("doi", "titre", "flou"):
        for r in df.itertuples():
            if r.ID_unique in match:
                continue
            d, t = norm_doi(r.DOI), norm_title(r.Titre)
            for j in sorted(free):
                lj = led.loc[j]
                same_year = str(lj["year"]) == str(r.Annee)
                ok = ((crit == "doi" and d and d == lj["d"])
                      or (crit == "titre" and t == lj["t"] and same_year)
                      or (crit == "flou" and same_year and SequenceMatcher(None, t, lj["t"]).ratio() >= 0.95))
                if ok:
                    match[r.ID_unique] = (j, crit)
                    free.discard(j)
                    break
    return match, led


def first_stage(stage):
    """Décision de premier niveau (titre/résumé) déduite de l'étape où la décision finale a été prise."""
    return "Retenu" if stage in ("Full text", "Title/abstract (full text not retrieved)") else "Exclu"


def code_of(final):
    m = re.search(r"\((E\d)\)", final)
    return m.group(1) if m else ""


# ------------------------------------------------------------------ programme principal
def main():
    OUT.mkdir(exist_ok=True)
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    df, with_abstracts = load_dataset()
    log = [f"Références chargées (Lab 5) : {len(df)} ; résumés disponibles : {'oui' if with_abstracts else 'non (titres seuls)'}"]

    # 5. grille vide
    q = {c["code"]: f"{c['code']} {c['nom']} ?" for c in cfg["criteres"]}
    grid_cols = ["ID_unique", "Titre", "Annee", "Type_document"] + list(q.values()) + ["Décision", "Motif", "Évaluateur", "Date", "Commentaire"]
    grid = pd.DataFrame({c: df[c] if c in df else "" for c in grid_cols})
    grid.to_excel(OUT / "05_grille_screening_titres.xlsx", index=False)

    # 6. pré-screening automatique
    auto = df.apply(lambda r: auto_screen(r, cfg), axis=1)
    pre = grid.copy()
    for code, col in q.items():
        pre[col] = [("Oui" if a[0][code] else "Non") for a in auto]
    pre["Décision"] = [a[1] for a in auto]
    pre["Motif"] = [a[2] for a in auto]
    pre["Évaluateur"] = "script (pré-remplissage)"
    pre["Commentaire"] = ["; ".join(a[3]) for a in auto]
    pre.to_excel(OUT / "06_grille_preremplie.xlsx", index=False)
    df["Auto_decision"], df["Auto_motif"] = pre["Décision"], pre["Motif"]

    # 7. décisions humaines (tableau de tri de la SLR + décisions complémentaires)
    led = pd.read_csv(LEDGER, encoding="utf-8-sig", dtype=str).fillna("")
    match, led = match_ledger(df, led)
    extra = pd.read_csv(EXTRA, encoding="utf-8-sig", dtype=str).fillna("").set_index("ID_unique") if EXTRA.exists() else pd.DataFrame()
    rows = []
    for r in df.itertuples():
        if r.ID_unique in match:
            l = led.loc[match[r.ID_unique][0]]
            fs = first_stage(l["decision_stage"])
            rows.append(dict(ID_unique=r.ID_unique, Record_SLR=l["record"], Appariement=match[r.ID_unique][1],
                             A_decision=fs, A_motif="" if fs == "Retenu" else code_of(l["final_decision"]),
                             A_evaluateur="Évaluatrice (propositions de l'assistant IA vérifiées)",
                             B_decision="Retenu" if l["blind_re_screening_decision"] in ("Include", "Uncertain") else "Exclu",
                             B_motif=l["blind_re_screening_code"], B_evaluateur="Même évaluatrice, re-tri à l'aveugle (ordre aléatoire)",
                             B_raison_desaccord=l["blind_re_screening_reason_disagreements"],
                             Etape_finale=l["decision_stage"], Decision_finale_SLR=l["final_decision"], Raison=l["reason"]))
        elif r.ID_unique in extra.index:
            e = extra.loc[r.ID_unique]
            rows.append(dict(ID_unique=r.ID_unique, Record_SLR="", Appariement="décision complémentaire",
                             A_decision=e["Decision_titre_resume"], A_motif=e["Motif"], A_evaluateur=e["Evaluateur"],
                             B_decision="", B_motif="", B_evaluateur="", B_raison_desaccord="",
                             Etape_finale=e["Etape"], Decision_finale_SLR=e["Decision_texte_integral"], Raison=e["Justification"]))
        else:
            sys.exit(f"Aucune décision pour {r.ID_unique} : ajouter une ligne dans {EXTRA.name}")
    dec = pd.DataFrame(rows)
    dec.merge(df[["ID_unique", "Titre", "Annee", "Type_document", "Auto_decision", "Auto_motif"]], on="ID_unique") \
        .to_csv(OUT / "07_decisions_titre_resume.csv", index=False, encoding="utf-8-sig")
    excl_ta = dec[dec["A_decision"] == "Exclu"]["A_motif"].value_counts().reindex(ORDER).dropna().astype(int)
    log += [f"Titre/résumé : {int((dec['A_decision'] == 'Retenu').sum())} retenues, {int((dec['A_decision'] == 'Exclu').sum())} exclues "
            f"({', '.join(f'{k} {v}' for k, v in excl_ta.items())})"]

    # évaluation du script par rapport à la décision humaine (premier niveau)
    ev = df[["ID_unique", "Auto_decision"]].merge(dec[["ID_unique", "A_decision", "Decision_finale_SLR"]], on="ID_unique")
    ev["Auto_retenu"] = ev["Auto_decision"].map(lambda x: "Retenu" if x in ("Inclure", "Incertain") else "Exclu")
    inc = ev[ev["Decision_finale_SLR"] == "Included"]
    script_eval = {
        "matrice": {f"script {a} / humain {h}": int(n) for (a, h), n in Counter(zip(ev["Auto_decision"], ev["A_decision"])).items()},
        "accord_pct": round(percent_agreement(list(ev["Auto_retenu"]), list(ev["A_decision"])), 1),
        "kappa": round(cohen_kappa(list(ev["Auto_retenu"]), list(ev["A_decision"])), 3),
        "inclus_finals_retenus_par_script": f"{int((inc['Auto_retenu'] == 'Retenu').sum())}/{len(inc)}",
        "inclus_finals_exclus_par_script": list(inc[inc["Auto_retenu"] == "Exclu"]["ID_unique"]),
        "references_a_lire_si_on_suit_le_script": int((ev["Auto_retenu"] == "Retenu").sum()),
        "avec_resumes": with_abstracts,
    }
    ev.to_csv(OUT / "06_eval_script_vs_humain.csv", index=False, encoding="utf-8-sig")

    # 8. double screening
    dbl = dec[dec["B_decision"] != ""]
    a, b = list(dbl["A_decision"]), list(dbl["B_decision"])
    acc = {"n": len(a), "accords": sum(x == y for x, y in zip(a, b)), "accord_pct": round(percent_agreement(a, b), 1),
           "kappa": round(cohen_kappa(a, b), 3),
           "tableau": {f"A {x} / B {y}": n for (x, y), n in sorted(Counter(zip(a, b)).items())},
           "script_vs_A": script_eval}
    try:
        from sklearn.metrics import cohen_kappa_score
        acc["kappa_sklearn"] = round(float(cohen_kappa_score(a, b)), 3)
    except ImportError:
        pass
    (OUT / "08_accord.json").write_text(json.dumps(acc, ensure_ascii=False, indent=1), encoding="utf-8")
    dis = dbl[dbl["A_decision"] != dbl["B_decision"]].merge(df[["ID_unique", "Titre"]], on="ID_unique")
    dis = dis[["ID_unique", "Record_SLR", "Titre", "A_decision", "B_decision", "B_motif", "B_raison_desaccord",
               "Etape_finale", "Decision_finale_SLR", "Raison"]]
    dis.to_csv(OUT / "08_desaccords.csv", index=False, encoding="utf-8-sig")
    with (OUT / "08_log_resolutions.txt").open("w", encoding="utf-8") as f:
        f.write("Journal de résolution des désaccords (titre/résumé)\n")
        f.write("A = décision assistée par IA et vérifiée par l'évaluatrice ; B = re-tri à l'aveugle par la même évaluatrice.\n")
        f.write("Règle : tout désaccord est réexaminé, sur le texte intégral quand il est disponible ; la décision finale est celle de cet examen.\n\n")
        for r in dis.itertuples():
            f.write(f"{r.ID_unique} (SLR #{r.Record_SLR}) {r.Titre[:90]}\n  A : {r.A_decision} | B : {r.B_decision} {r.B_motif}\n"
                    f"  Motif du désaccord : {r.B_raison_desaccord or '-'}\n  Décision finale : {r.Decision_finale_SLR} ({r.Etape_finale})"
                    f"{' - ' + r.Raison if r.Raison else ''}\n\n")
    log += [f"Double screening : accord {acc['accords']}/{acc['n']} ({acc['accord_pct']} %), kappa {acc['kappa']} ; désaccords : {len(dis)}"]

    # 9. liste des textes intégraux à récupérer
    ft = dec[dec["A_decision"].isin(["Retenu", "Inclure", "Incertain"])].merge(df[["ID_unique", "Titre", "Annee", "DOI", "Type_document"]], on="ID_unique")
    ft["Lien"] = ft["DOI"].map(lambda d: f"https://doi.org/{d}" if d else "")
    ft["Statut_recuperation"] = ft["Etape_finale"].map(lambda s: "Non récupéré" if "not retrieved" in s else ("Récupéré" if s == "Full text" else "À récupérer"))
    ft[["ID_unique", "Record_SLR", "Titre", "Annee", "Type_document", "DOI", "Lien", "Statut_recuperation"]] \
        .to_csv(OUT / "09_liste_textes_integraux.csv", index=False, encoding="utf-8-sig")

    # 10. décisions sur texte intégral
    fti = ft[ft["Statut_recuperation"] == "Récupéré"].copy()
    fti["Decision_texte"] = fti["Decision_finale_SLR"].map(lambda x: "Inclure" if x == "Included" else "Exclure")
    fti["Motif_texte"] = fti["Decision_finale_SLR"].map(code_of)
    fti[["ID_unique", "Record_SLR", "Titre", "Decision_texte", "Motif_texte", "Raison"]] \
        .to_csv(OUT / "10_decisions_texte_integral.csv", index=False, encoding="utf-8-sig")

    # 11. tableau maître et PRISMA
    master = dec.merge(df[["ID_unique", "Titre", "Annee", "DOI", "Bases"]], on="ID_unique")
    master["Statut_PRISMA"] = master.apply(lambda r: (
        f"Exclu titre/résumé ({r.A_motif})" if r.A_decision == "Exclu" else
        "Texte intégral non récupéré" if "not retrieved" in r.Etape_finale else
        "Inclus" if r.Decision_finale_SLR == "Included" else
        f"Exclu texte intégral ({code_of(r.Decision_finale_SLR)})" if code_of(r.Decision_finale_SLR) else
        "En attente du texte intégral"), axis=1)
    master.to_csv(OUT / "11_tableau_maitre.csv", index=False, encoding="utf-8-sig")
    st = master["Statut_PRISMA"]
    p = {
        "identifiees": {"Scopus": 118, "Web of Science": 97, "total": 215},
        "doublons_retires": 215 - len(df),
        "references_triees": len(df),
        "exclues_titre_resume": int(st.str.startswith("Exclu titre").sum()),
        "exclues_titre_resume_par_motif": {k: int(v) for k, v in Counter(master.loc[st.str.startswith("Exclu titre"), "A_motif"]).items()},
        "rapports_recherches": int((master["A_decision"] != "Exclu").sum()),
        "rapports_non_recuperes": int((st == "Texte intégral non récupéré").sum()),
        "rapports_en_attente": int((st == "En attente du texte intégral").sum()),
        "rapports_evalues": int(st.isin(["Inclus"]).sum() + st.str.startswith("Exclu texte").sum()),
        "exclus_texte_integral": int(st.str.startswith("Exclu texte").sum()),
        "exclus_texte_integral_par_motif": {k: int(v) for k, v in Counter(st[st.str.startswith("Exclu texte")].str.extract(r"\((E\d)\)")[0]).items()},
        "rapports_inclus": int((st == "Inclus").sum()),
        "etudes_incluses": int((st == "Inclus").sum()) - 1,  # un étude décrite dans deux rapports (Kallel 2022 / Makhloufi 2022)
    }
    (OUT / "11_prisma.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    draw_prisma(p, OUT / "11_diagramme_prisma.png")
    log += [f"PRISMA : {json.dumps(p, ensure_ascii=False)}",
            f"Script vs humain : {json.dumps(script_eval, ensure_ascii=False)}"]
    (OUT / "00_journal.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


def draw_prisma(p, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 8.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def box(x, y, w, h, txt, fc="#f4f6f8"):
        ax.add_patch(plt.Rectangle((x, y), w, h, fc=fc, ec="#333", lw=1))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=8.5, wrap=True)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=1))

    m = p["exclues_titre_resume_par_motif"]
    f = p["exclus_texte_integral_par_motif"]
    left = [
        (8.6, f"Enregistrements identifiés\nScopus {p['identifiees']['Scopus']} ; Web of Science {p['identifiees']['Web of Science']}\n(n = {p['identifiees']['total']})"),
        (6.6, f"Enregistrements triés\n(titre et résumé)\n(n = {p['references_triees']})"),
        (4.6, f"Rapports recherchés\n(n = {p['rapports_recherches']})"),
        (2.6, f"Rapports évalués\n(texte intégral)\n(n = {p['rapports_evalues']})"),
        (0.4, f"Études incluses : {p['etudes_incluses']}\nRapports inclus : {p['rapports_inclus']}"),
    ]
    right = [
        (8.6, f"Doublons retirés\n(n = {p['doublons_retires']})"),
        (6.6, "Exclus (n = {})\n".format(p["exclues_titre_resume"]) + " ; ".join(f"{k} {m[k]}" for k in ORDER if k in m)),
        (4.6, f"Non récupérés (n = {p['rapports_non_recuperes']})" + (f"\nEn attente (n = {p['rapports_en_attente']})" if p["rapports_en_attente"] else "")),
        (2.6, "Exclus (n = {})\n".format(p["exclus_texte_integral"]) + " ; ".join(f"{k} {f[k]}" for k in ORDER if k in f)),
    ]
    for y, t in left:
        box(0.5, y, 4.2, 1.2, t, "#e8f0fb" if y < 1 else "#f4f6f8")
    for y, t in right:
        box(5.6, y, 4.0, 1.2, t)
        arrow(4.7, y + 0.6, 5.6, y + 0.6)
    for (y1, _), (y2, _) in zip(left, left[1:]):
        arrow(2.6, y1, 2.6, y2 + 1.2)
    ax.set_title("Diagramme PRISMA 2020 (recalculé, Labs 5 et 6)", fontsize=10)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
