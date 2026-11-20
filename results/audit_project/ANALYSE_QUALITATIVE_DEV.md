# Analyse qualitative de trois cas de développement

Sélection intentionnelle de trois cas illustratifs parmi les 85 questions dev, après consultation des scores. Cette sélection ne mesure pas la fréquence des erreurs et n’est pas un test indépendant. Revue éditoriale par l’assistant, citations contrôlées dans les PDF physiques. Aucun score n’est recalculé.

## FOMC_004

As the recovery regained momentum in early 2021, how did the FOMC characterize economic activity and employment?

| Indicateur | RRF | RRF + ColBERT |
|---|---:|---:|
| nDCG pages@6 | 0.000000 | 0.000000 |
| Couverture des pages du contexte | 0.000 | 0.000 |
| Rang du chunk examiné | 1 | 1 |
| Rang de sa page parmi les pages uniques | 1 | 1 |

Passage : `MIN_2021-03-17_C0024` ; page : `fomcminutes20210317.pdf#p8` ; paragraphes : MIN_2021-03-17_P0099.

> Following a moderation in the pace of the recovery, indicators of economic activity and employment had turned up recently, although the sectors most adversely affected by the pandemic remained weak.

**Interprétation :** Référence silver alternative manquante : le passage de mars 2021 contient explicitement l'amélioration de l'activité et de l'emploi demandée, mais le seul qrel désigne la page 1 du Statement. Un score de couverture nul ne démontre donc pas l'absence de preuve dans le contexte.

Page présente dans les qrels historiques : non. Les corrections suggérées restent séparées et ne modifient ni les qrels figés ni les anciens scores.

## FOMC_035

What made a rate increase seem appropriate soon at the January 2022 meeting?

| Indicateur | RRF | RRF + ColBERT |
|---|---:|---:|
| nDCG pages@6 | 0.605260 | 0.000000 |
| Couverture des pages du contexte | 1.000 | 0.000 |
| Rang du chunk examiné | 3 | 1 |
| Rang de sa page parmi les pages uniques | 4 | 1 |

Passage : `MIN_2022-01-26_C0048` ; page : `fomcminutes20220126.pdf#p17` ; paragraphes : MIN_2022-01-26_P0226.

> In discussing why beginning to remove policy accommodation could soon be warranted, participants noted that inflation continued to run well above 2 percent and generally judged the risks to the outlook for inflation as tilted to the upside. Participants also assessed that the labor market was strong, having made substantial, broad-based progress over the past year.

**Interprétation :** La baisse de métrique après ColBERT s'accompagne pourtant de la promotion au rang 1 d'un passage de la bonne réunion donnant inflation élevée et marché du travail solide. Les pages silver 18 des Minutes et 1 du Statement disparaissent du contexte ; la page 17 également pertinente n'est pas annotée. On constate une perte de couverture silver, pas une preuve suffisante d'une perte de capacité à répondre. Plusieurs autres passages retenus concernent d'autres réunions : ces distracteurs temporels restent un risque réel.

Page présente dans les qrels historiques : non. Les corrections suggérées restent séparées et ne modifient ni les qrels figés ni les anciens scores.

## FOMC_064

What did business contacts report about firms’ ability to raise prices in July 2024?

| Indicateur | RRF | RRF + ColBERT |
|---|---:|---:|
| nDCG pages@6 | 0.000000 | 1.000000 |
| Couverture des pages du contexte | 1.000 | 1.000 |
| Rang du chunk examiné | 4 | 1 |
| Rang de sa page parmi les pages uniques | 7 | 1 |

Passage : `MIN_2024-07-31_C0013` ; page : `fomcminutes20240731.pdf#p7` ; paragraphes : MIN_2024-07-31_P0040.

> Some participants noted that the recent data corroborated reports from their business contacts that firms’ pricing power was waning, as consumers appeared to be more sensitive to price increases.

**Interprétation :** Le même passage contenant la preuve passe du rang 4 au rang 1. Sa page est déjà présente dans les six chunks avant reranking, mais arrive au rang 7 des pages uniques à cause des chunks multipages précédents. Le nDCG pages@6 passe donc de 0 à 1 alors que la couverture de toutes les pages du contexte reste 1. C'est une amélioration de priorité et de classement, pas l'acquisition d'une preuve auparavant absente.

Page présente dans les qrels historiques : oui. Les corrections suggérées restent séparées et ne modifient ni les qrels figés ni les anciens scores.

