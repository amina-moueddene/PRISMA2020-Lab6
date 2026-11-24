"""Étapes 4 à 6 et 8 : critères, pré-screening automatique, accord et kappa."""
import json
import unittest

from tests.helpers import ROOT, load

sc = load("screening")
CFG = json.loads((ROOT / "config" / "criteres.json").read_text(encoding="utf-8"))


def ref(titre, resume="", annee="2022", type_doc="Article", langue="English"):
    return {"Titre": titre, "Resume": resume, "Mots_cles": "", "Annee": annee, "Type_document": type_doc, "Langue": langue}


BASE = "Xylella detection in olive orchards from UAV hyperspectral images with a random forest"


class TestCriteres(unittest.TestCase):
    def test_huit_criteres_dans_l_ordre(self):
        self.assertEqual([c["code"] for c in CFG["criteres"]], sc.ORDER)

    def test_inclusion(self):
        self.assertEqual(sc.auto_screen(ref(BASE), CFG)[1:3], ("Inclure", ""))

    def test_premier_critere_non_rempli(self):
        cas = {
            "E1": ref(BASE, annee="2010"),
            "E2": ref("Citrus greening detection from UAV images with a random forest"),
            "E3": ref("Counting olive trees from UAV images with YOLO"),
            "E4": ref("Olive leaf disease classification with a CNN"),
            "E5": ref("Olive drought mapping from Sentinel-2 NDVI trends"),
            "E6": ref(BASE + ": a review"),
            "E7": ref(BASE, type_doc="Book chapter"),
            "E8": ref(BASE, langue="Spanish"),
        }
        for code, r in cas.items():
            with self.subTest(code):
                self.assertEqual(sc.auto_screen(r, CFG)[1:3], ("Exclure", code))

    def test_un_seul_code_le_premier(self):
        # pas d'olivier (E2) ET revue (E6) ET chapitre (E7) : seul E2 est attribué
        r = ref("Citrus disease detection from UAV with machine learning: a review", type_doc="Book chapter")
        self.assertEqual(sc.auto_screen(r, CFG)[2], "E2")

    def test_incertain_si_signaux_de_doute(self):
        r = ref("Olive water stress from UAV thermal imagery", "Leaf water potential was measured in the laboratory; a classification is proposed.")
        ans, dec, motif, doubts = sc.auto_screen(r, CFG)
        self.assertEqual(dec, "Incertain")
        self.assertTrue(any("feuilles" in d for d in doubts))

    def test_mots_courts_avec_limites_de_mot(self):
        self.assertTrue(sc.has("an ai model", [" ai "]))
        self.assertFalse(sc.has("rain and drain", ["ai"]))
        self.assertTrue(sc.has("svm classifier", ["svm"]))
        self.assertFalse(sc.has("svms2x", ["svm"]))


class TestAccord(unittest.TestCase):
    def test_pourcentage(self):
        self.assertEqual(sc.percent_agreement(list("AABB"), list("ABBB")), 75.0)

    def test_kappa_exemple_classique(self):
        # 50 références : 20 oui/oui, 5 oui/non, 10 non/oui, 15 non/non -> kappa = 0,40
        a = ["oui"] * 25 + ["non"] * 25
        b = ["oui"] * 20 + ["non"] * 5 + ["oui"] * 10 + ["non"] * 15
        self.assertAlmostEqual(sc.cohen_kappa(a, b), 0.40, places=3)

    def test_kappa_parfait_et_hasard(self):
        self.assertEqual(sc.cohen_kappa(list("ABAB"), list("ABAB")), 1.0)
        self.assertAlmostEqual(sc.cohen_kappa(list("AABB"), list("ABAB")), 0.0)

    def test_kappa_identique_a_scikit_learn(self):
        try:
            from sklearn.metrics import cohen_kappa_score
        except ImportError:
            self.skipTest("scikit-learn absent")
        a = list("IIEEEUIEEI")
        b = list("IEEEUUIEII")
        self.assertAlmostEqual(sc.cohen_kappa(a, b), cohen_kappa_score(a, b), places=10)

    def test_listes_de_longueurs_differentes(self):
        with self.assertRaises(ValueError):
            sc.cohen_kappa(["a"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
