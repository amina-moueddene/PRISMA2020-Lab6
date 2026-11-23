# LAB 6 : Screening des titres, résumés et textes intégraux
**Application à ma SLR : ML et télédétection pour la détection des maladies et du stress de l'olivier**

> Point de départ : le dataset dédupliqué du Lab 5 (**143 références uniques**, issues de Scopus et Web of Science). Les codes d'exclusion sont ceux de ma SLR (E1 à E8), pas ceux du lab.

## 1. Introduction et environnement

Le dataset de départ est le fichier dédupliqué du Lab 5 (colonnes `ID`, `Titre`, `Résumé`, `Auteurs`, `Année`, `Source`). Python (pandas) sert à charger les données, calculer l'accord entre décisions et compter les flux PRISMA. Le screening lui-même a été fait par lecture des titres, résumés et textes intégraux (voir section 5).

```python
import pandas as pd
df = pd.read_csv("dataset_final_screening.csv", encoding="utf-8")
print(len(df))   # 143
df["Titre"] = df["Titre"].fillna("")
df["Résumé"] = df["Résumé"].fillna("")
df_original = df.copy()
```

## 2. Critères d'inclusion et d'exclusion

Huit paires de critères. Une étude doit remplir **tous** les critères d'inclusion, mais n'a pas besoin de répondre à toutes les questions de recherche. Chaque référence exclue reçoit **un seul code**, celui du **premier critère non rempli** dans l'ordre ci-dessous.

| Critère | Inclusion | Exclusion (code) |
|---|---|---|
| Période | Publié 2013–2026 | Publié avant 2013 (E1) |
| Population | Oliviers ou oliveraies (*Olea europaea* L.) | Autre culture comme sujet principal ; huile d'olive, chaîne alimentaire, pollen (E2) |
| Cible | Maladie, pathogène, stress hydrique ou autre stress physiologique | Cartographie, rendement, vigueur, irrigation ou classification de cultivars sans détection de maladie ou de stress (E3) |
| Capteur | Télédétection UAV, aérienne ou satellite (RGB, multispectral, thermique, hyperspectral, LiDAR) | Laboratoire, feuille ou mesures au sol uniquement (E4) |
| Méthode | Machine learning, deep learning ou autre méthode d'IA | Indices de végétation ou statistiques sans modèle d'apprentissage (E5) |
| Contribution | Étude primaire avec données empiriques et évaluation | Revue, synthèse, éditorial, opinion (E6) |
| Type de document | Article de revue ou communication de conférence complète, relu par des pairs | Livre, chapitre, front matter, préprint, thèse, résumé seul (E7) |
| Langue | Anglais ou français | Autres langues (E8) |

## 3. Grille de screening

Une ligne par référence. Colonnes de la grille :

| ID | Titre | Décision proposée (IA) | Code d'exclusion | Justification (1 ligne) | Décision de la relectrice | Décision finale |
|---|---|---|---|---|---|---|

Décisions possibles : `Inclure`, `Exclure`, `Incertain`. Les références `Inclure` et `Incertain` passent au texte intégral. Toutes les décisions, codes et motifs sont consignés dans le **Supplementary Material S1** (143 lignes).

```python
grille = pd.DataFrame({
    "ID": df["ID"], "Titre": df["Titre"],
    "Décision_IA": "", "Code": "", "Justification": "",
    "Décision_relectrice": "", "Décision_finale": ""
})
grille.to_excel("grille_screening_titres.xlsx", index=False)
```

## 4. Screening des titres et résumés

Procédure réellement appliquée :

1. **Proposition par un assistant IA générative.** Pour chaque référence, l'assistant applique les critères ci-dessus et propose une décision, un code d'exclusion et une justification d'une ligne.
2. **Vérification par la relectrice.** Chaque proposition est comparée au titre, au résumé et, si besoin, au texte intégral ; la relectrice accepte ou corrige. **Sa décision est finale.**
3. **Re-screening en aveugle.** Pour mesurer l'influence des propositions de l'IA, la relectrice a re-screené les 143 références au niveau titre et résumé, sans voir les propositions ni ses décisions précédentes. Les références ont été mélangées et identifiées par des codes.

Aucun filtre par mots-clés automatisé n'a servi à décider : les décisions viennent de la lecture. Cette procédure ne remplace pas un second évaluateur humain (limite assumée, voir section 7).

**Résultat du screening titres/résumés :**

| Issue | Nombre |
|---|---|
| Références évaluées | 143 |
| Exclues | **90** |
| Envoyées en texte intégral (Inclure + Incertain) | **53** |

## 5. Motifs d'exclusion au titre/résumé

| Code | Motif | Nombre |
|---|---|---|
| E2 | Autre culture ou hors sujet | 36 |
| E3 | Pas de cible maladie ou stress | 17 |
| E7 | Livre, chapitre ou front matter | 14 |
| E4 | Pas de capteur aérien ou satellite | 12 |
| E6 | Revue ou éditorial (littérature secondaire) | 11 |
| **Total** | | **90** |

## 6. Double screening et indice d'accord

Le « double » screening est ici l'accord entre les **décisions assistées par l'IA** et le **re-screening en aveugle** de la même relectrice. Ce n'est pas un accord entre deux évaluateurs humains.

```python
from sklearn.metrics import cohen_kappa_score

accord = (merged["Décision_IA_assistée"] == merged["Décision_aveugle"]).sum()
print(f"Accord simple : {accord/len(merged)*100:.1f}% ({accord}/{len(merged)})")
kappa = cohen_kappa_score(merged["Décision_IA_assistée"], merged["Décision_aveugle"])
print(f"Cohen's kappa : {kappa:.2f}")
```

| Indicateur | Valeur |
|---|---|
| Accord simple | **124 / 143 = 86,7 %** |
| Cohen's κ | **0,70** (accord substantiel, échelle de Landis et Koch) |
| Désaccords | 19 |

Analyse des 19 désaccords :
- Dans **18** cas, le re-screening en aveugle a exclu une référence qui avait avancé au texte intégral : 14 ont été exclues au texte intégral, 2 n'ont pas pu être retrouvées, 2 ont été incluses après lecture du texte intégral.
- Le dernier cas, inclus par le re-screening en aveugle, concernait des amandiers ; il a été exclu (E2).
- Au total, le re-screening en aveugle a retenu **21 des 23 rapports** finalement inclus (91 %).
- Les désaccords ont été réexaminés (sur texte intégral quand il était disponible). **Cela n'a pas changé l'ensemble des études incluses.**

## 7. Limite : un seul évaluateur

Le protocole prévoyait deux évaluateurs indépendants et un arbitre en cas de désaccord. Cela n'a pas été possible : le screening, l'extraction et l'évaluation de la qualité ont été faits par **une seule personne**, qui a vérifié chaque proposition de l'IA. C'est un écart au protocole, déclaré dans les limites. Pendant le premier screening, la relectrice voyait les propositions de l'IA et a pu être influencée ; le re-screening en aveugle mesure la cohérence de ses décisions, pas l'accord entre deux humains.

## 8. Références envoyées pour récupération du texte intégral

53 rapports recherchés (Inclure + Incertain). Textes obtenus par accès institutionnel ou dépôts ouverts.

| Issue | Nombre |
|---|---|
| Rapports recherchés | 53 |
| Rapports **non retrouvés** | **15** (11 classés « Inclure » et 4 « Incertain » au premier stade) |
| Rapports évalués en texte intégral | **38** |

Les 15 rapports non retrouvés sont listés dans le **Supplementary Material S2** avec leur décision du premier stade. Onze étaient des communications de conférence, souvent de groupes déjà présents dans le corpus : ce type de publication est donc probablement sous-représenté. Les rapports non retrouvés ne reçoivent pas de code d'exclusion : ils sont comptés à part dans le flux PRISMA.

## 9. Screening du texte intégral

Les 38 textes intégraux ont été lus par la relectrice. Chaque exclusion reçoit un code unique (premier critère non rempli). Résultat : **15 exclusions** (5 pour E3, 5 pour E4, 5 pour E5) et **23 rapports inclus**, correspondant à **22 études**.

Une des 22 études est décrite dans deux communications de conférence du même groupe (mêmes parcelles, même méthode) : les deux rapports sont **liés et comptés comme une seule étude**. Les 22 études comprennent **19 articles de revue et 3 communications de conférence**.

## 10. Motifs d'exclusion au texte intégral

| Étude exclue | Code | Raison |
|---|---|---|
| Beyaz et Ozkaya | E4 | Caméra thermique portable au sol ; pas d'imagerie aérienne ou satellite |
| Alrashdi et Abozeid | E4 | Classification de photos de feuilles ; pas d'imagerie aérienne de l'arbre |
| Bruno et al. | E4 | Jeu public d'images de feuilles acquises au smartphone |
| Estrada et al. | E4 | Spectres de feuilles en laboratoire, cinq stades de déshydratation |
| Abu-Hammour et al. | E4 | Images publiques de feuilles combinées à des données environnementales ; pas d'imagerie aérienne |
| Panagiotopoulou et al. | E5 | Deep learning utilisé seulement pour la super-résolution ; stress déduit d'un indice (CRI2), sans modèle d'apprentissage ni données de référence |
| Telesca et al. (2024) | E5 | Analyse de Fisher–Shannon de l'évapotranspiration MODIS avec seuils ROC ; pas de modèle d'apprentissage |
| Telesca et Lasaponara | E5 | Métriques de complexité avec seuils ROC ; pas de modèle d'apprentissage |
| Quille-Mamani et al. | E5 | Classes de stress hydrique à partir de seuils fixes de CWSI et NDVI ; pas de modèle d'apprentissage |
| Navrozidis et al. (2020) | E5 | Indices de végétation seulement ; le classifieur SVM est annoncé mais ni entraîné ni évalué |
| Cilli et al. | E3 | Classification de l'occupation du sol (oliveraies et vignes) ; pas de cible maladie ou stress |
| Alfonso et al. | E3 | Comparaison d'indices UAV et satellite ; pas de détection de maladie ou de stress |
| Vasilakos et Verykios | E3 | Détection d'arbres brûlés ; ni maladie ni stress hydrique |
| Kalo et al. | E3 | Détection de fuites et obstructions d'irrigation ; référence = dysfonctionnements observés, sans mesure de stress de la plante |
| Majikumna et al. | E3 | Olivier contre autre occupation du sol pour quantifier la perte de surface ; pas de variable de stress ou de maladie |

## 11. Diagramme PRISMA 2020

```
Identification
  Enregistrements identifiés dans les bases (n = 215)
     Scopus (n = 118) ; Web of Science Core Collection (n = 97)
  Doublons supprimés avant screening (n = 72 : 70 par DOI, 2 par titre normalisé)
        ↓
Screening
  Enregistrements évalués sur titre et résumé (n = 143)
  Enregistrements exclus (n = 90)
     E2 autre culture ou hors sujet (n = 36)
     E3 pas de cible maladie/stress (n = 17)
     E7 livre, chapitre ou front matter (n = 14)
     E4 pas de capteur aérien ou satellite (n = 12)
     E6 revue ou éditorial (n = 11)
        ↓
  Rapports recherchés (n = 53)
  Rapports non retrouvés (n = 15 : 11 « inclure », 4 « incertain »)
        ↓
  Rapports évalués en texte intégral (n = 38)
  Rapports exclus (n = 15)
     E3 (n = 5) ; E4 (n = 5) ; E5 (n = 5)
        ↓
Inclusion
  Études incluses (n = 22)
  Rapports des études incluses (n = 23 : 19 articles de revue, 3 communications de conférence, deux rapports pour une même étude)
```

Vérification arithmétique : 215 − 72 = 143 ; 143 − 90 = 53 ; 53 − 15 = 38 ; 38 − 15 = 23 rapports ; 23 rapports = 22 études.

```python
prisma = {"identifiés": 215, "doublons": 72, "évalués_titre_résumé": 143,
          "exclus_titre_résumé": 90, "recherchés": 53, "non_retrouvés": 15,
          "évalués_texte_intégral": 38, "exclus_texte_intégral": 15,
          "rapports_inclus": 23, "études_incluses": 22}
assert 215 - 72 == 143 and 143 - 90 == 53 and 53 - 15 == 38 and 38 - 15 == 23
```

## 12. Questions de vérification

**Q1. Quel code pour une étude qui ne porte pas sur l'olivier mais utilise une IA ?**
**E2** (autre culture comme sujet principal). L'exemple réel est celui d'une référence sur les amandiers, exclue avec E2. Dans le lab (sujet Android), la réponse attendue est E1, car les codes y sont différents.

**Q2. Comment calcule-t-on l'accord simple ?**
Nombre d'accords ÷ nombre total de références × 100. Dans ma SLR : 124 / 143 × 100 = **86,7 %** (κ = 0,70).

**Q3. Que faire si un texte intégral est inaccessible ?**
Dans le lab, le motif attribué est E7. Dans ma SLR, E7 désigne le type de document ; les 15 rapports non retrouvés **ne reçoivent pas de code d'exclusion** : ils sont listés à part dans S2 avec leur décision du premier stade et comptés dans le flux PRISMA.

**Défi 1 : appliquer le script à 10 références simulées (`exemple_simule.csv`).**
Non réalisé : le fichier simulé n'est pas disponible et ma SLR n'utilise pas de script de filtrage par mots-clés. À la place, la procédure réelle (section 4) a été appliquée aux 143 références.

**Défi 2 : référence classée « Inclure » par A et « Exclure » (E2) par B.**
Justification de la décision finale : vérifier dans le titre, le résumé puis le texte intégral si l'olivier est bien le **sujet principal** (critère de population). Si l'olivier n'est qu'une culture parmi d'autres, ou si c'est un autre arbre, la référence est exclue avec E2 ; sinon elle est conservée. Exemple de ma SLR : la référence sur les amandiers, incluse par le re-screening en aveugle, a été exclue après vérification (E2). Rôle d'un troisième évaluateur : trancher si A et B restent en désaccord après discussion. Dans ma SLR, il n'y en a pas eu (voir section 7).

## 13. Résumé

143 références uniques ont été évaluées sur titre et résumé (90 exclues, 53 recherchées), 15 rapports n'ont pas pu être retrouvés, 38 textes intégraux ont été évalués (15 exclus), pour **22 études incluses (23 rapports)**. L'accord entre les décisions assistées par l'IA et le re-screening en aveugle est de 86,7 % (κ = 0,70). Chaque décision est tracée (S1, S2), et la limite d'un seul évaluateur est déclarée. Prochaine étape : l'extraction des données et l'évaluation de la qualité.
