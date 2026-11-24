"""Défi 1 (10 références simulées) et étape 10 (extraction du texte des PDF)."""
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from tests.helpers import load

defi = load("defi_simule")
ft = load("fulltext_screening")


class TestDefi1(unittest.TestCase):
    def test_dix_references_conformes(self):
        df = defi.run()
        self.assertEqual(len(df), 10)
        self.assertTrue(df["Conforme"].all(), df[~df["Conforme"]][["ID_unique", "Attendu", "Obtenu"]])
        self.assertEqual(Counter(df["Decision"]), Counter({"Inclure": 1, "Exclure": 8, "Incertain": 1}))


class TestTexteIntegral(unittest.TestCase):
    def pdf(self, folder, name, text):
        doc = ft.fitz.open()
        page = doc.new_page()
        page.insert_textbox(page.rect, text)
        doc.save(Path(folder) / f"{name}.pdf")
        doc.close()

    def test_extraction_et_propositions(self):
        with tempfile.TemporaryDirectory() as t:
            self.pdf(t, "U001", "Olive trees were imaged by a UAV. A random forest classifier reached an accuracy of 0.90 on the test set.")
            self.pdf(t, "U002", "Leaf images taken with a smartphone in the laboratory were classified by a CNN with an accuracy of 0.95.")
            self.pdf(t, "U003", "Sentinel-2 images of olive groves; NDVI thresholds were used to map drought.")
            self.pdf(t, "U004", "This systematic review summarises studies. In this literature review we discuss UAV and satellite work.")
            got = {p.stem: ft.suggest(ft.extract_text(p))[1:] for p in sorted(Path(t).glob("*.pdf"))}
        self.assertEqual(got, {"U001": ("Inclure", ""), "U002": ("Exclure", "E4"), "U003": ("Exclure", "E5"), "U004": ("Exclure", "E6")})


if __name__ == "__main__":
    unittest.main()
