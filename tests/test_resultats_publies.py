"""Étapes 7 à 11 : cohérence des résultats publiés (ne demande ni les résumés ni les PDF)."""
import json
import unittest
from collections import Counter

from tests.helpers import ROOT, load, rows

sc = load("screening")
OUT = ROOT / "output"


class TestResultats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dec = rows(OUT / "07_decisions_titre_resume.csv")
        cls.master = rows(OUT / "11_tableau_maitre.csv")
        cls.p = json.loads((OUT / "11_prisma.json").read_text(encoding="utf-8"))
        cls.acc = json.loads((OUT / "08_accord.json").read_text(encoding="utf-8"))
        cls.dis = rows(OUT / "08_desaccords.csv")
        cls.lab5 = rows(ROOT / "data" / "dataset_lab5_public.csv")

    def test_toutes_les_references_du_lab5_ont_une_decision(self):
        self.assertEqual({r["ID_unique"] for r in self.dec}, {r["ID_unique"] for r in self.lab5})
        self.assertEqual(len(self.master), 144)

    def test_chaque_exclusion_a_un_seul_code_valide(self):
        for r in self.dec:
            if r["A_decision"] == "Exclu":
                self.assertIn(r["A_motif"], sc.ORDER, r["ID_unique"])

    def test_arithmetique_prisma(self):
        p = self.p
        self.assertEqual(p["identifiees"]["total"] - p["doublons_retires"], p["references_triees"])
        self.assertEqual(p["references_triees"] - p["exclues_titre_resume"], p["rapports_recherches"])
        self.assertEqual(p["rapports_recherches"] - p["rapports_non_recuperes"] - p["rapports_en_attente"], p["rapports_evalues"])
        self.assertEqual(p["rapports_evalues"] - p["exclus_texte_integral"], p["rapports_inclus"])
        self.assertEqual(sum(p["exclues_titre_resume_par_motif"].values()), p["exclues_titre_resume"])
        self.assertEqual(sum(p["exclus_texte_integral_par_motif"].values()), p["exclus_texte_integral"])

    def test_chiffres_de_la_slr(self):
        p = self.p
        self.assertEqual((p["references_triees"], p["exclues_titre_resume"], p["rapports_non_recuperes"],
                          p["rapports_evalues"], p["exclus_texte_integral"], p["rapports_inclus"], p["etudes_incluses"]),
                         (144, 90, 15, 38, 15, 23, 22))

    def test_accord_et_kappa_recalcules(self):
        d = [r for r in self.dec if r["B_decision"]]
        a, b = [r["A_decision"] for r in d], [r["B_decision"] for r in d]
        self.assertEqual((len(d), sum(x == y for x, y in zip(a, b))), (143, 124))
        self.assertAlmostEqual(sc.cohen_kappa(a, b), self.acc["kappa"], places=3)
        self.assertAlmostEqual(self.acc["kappa"], 0.695, places=3)
        if "kappa_sklearn" in self.acc:
            self.assertEqual(self.acc["kappa"], self.acc["kappa_sklearn"])

    def test_chaque_desaccord_est_resolu(self):
        self.assertEqual(len(self.dis), 19)
        for r in self.dis:
            self.assertNotEqual(r["A_decision"], r["B_decision"])
            self.assertTrue(r["Decision_finale_SLR"], r["ID_unique"])

    def test_statuts_prisma(self):
        c = Counter(r["Statut_PRISMA"] for r in self.master)
        self.assertEqual(c["Inclus"], 23)
        self.assertEqual(c["Texte intégral non récupéré"], 15)
        self.assertEqual(c["En attente du texte intégral"], 1)

    def test_aucun_resume_dans_les_fichiers_publies(self):
        for f in OUT.glob("*.csv"):
            self.assertNotIn("Resume", rows(f)[0].keys() if rows(f) else [], f.name)


if __name__ == "__main__":
    unittest.main()
