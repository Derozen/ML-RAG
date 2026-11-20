# Lot candidat V2 — couverture diversifiée et annotation traçable

> **Décision actuelle :** les 294 grades proposés ont été acceptés globalement
> par l’utilisateur, sans modification. Les champs humains de la grille consolidée
> sont renseignés et la trace est conservée dans
> [user_approval.json](assistant_review/completed_proposal/user_approval.json).
> Le lot est remis comme évaluation complémentaire à scores provisoires ;
> [la décision documentée](../../docs/STATUT_HOLDOUT.md) distingue cet accord
> de la vérification sémantique des questions. Les anciennes descriptions ci-dessous
> et la grille située à la racine décrivent les étapes historiques de préparation.

> **Mise à jour :** une évaluation provisoire sur les qrels proposés est lancée
> dans `results/candidate_provisional/`. Les mentions « non scoré » ci-dessous
> décrivent l’historique de préparation. Les champs humains restent vides :
> cette mesure ne donne pas au lot le statut de test final indépendant validé.
> Aucun réglage ne doit être justifié comme indépendant après consultation de ces scores.

> **Point d'entrée actuel :** [dossier consolidé des 294 propositions](assistant_review/completed_proposal/RAPPORT.md).
> Les grades proposés sont maintenant complets dans sa grille `human_review.csv`.
> Les champs humains restent à renseigner ; les qrels ne sont pas approuvés pour
> un test final. Le texte ci-dessous et `validation_report.json` décrivent la
> version initiale, conservée pour l'historique.

> **Complément de revue disponible :** [rapport éditorial, deuxième passe](assistant_review/round_2/RAPPORT.md).
> Il ajoute des preuves et des jugements motivés, et conserve explicitement une
> proposition de changement de grade. Les nombres et extraits ci-dessous décrivent
> la proposition initiale ; les comptes du complément sont dans son rapport.
> Aucune grille humaine n'a été remplie automatiquement. Le lot reste non scoré et
> en attente de validation indépendante.

STATUT : non scoré, annotations proposées contrôlées dans les sources, validation humaine indépendante encore requise. Aucun résultat de Recall/MRR/nDCG n’a été calculé pour ce lot.

Composition : {'factual': 4, 'explanatory': 6, 'comparative': 5, 'multi_evidence': 5}. Sources demandées : {'minutes': 6, 'statements': 6, 'mixed': 8}.

Le périmètre des documents fait partie de chaque question : une question demandant un Statement précis évalue la lecture de ce document, pas toute mention générique du même sujet. Les PDF de Statements incluent leurs notes de mise en œuvre. Les questions croisées exigent l’attribution correcte des informations. Plusieurs preuves ne signifient pas toujours plusieurs documents : le cas d’application 019 réutilise des règles dupliquées entre Minutes et Statement.

838 pages du corpus ont été examinées par un écran documentaire pour chaque question, soit 16760 couples. Cela n’équivaut pas à 16760 jugements humains. Les pages sans preuve approuvée restent NON JUGÉES. Le fichier human_review.csv expose toutes les pages du périmètre demandé, y compris celles à revoir.

53 qrels positifs proposés couvrent 38 facettes ; 11 jugements non pertinents explicitement motivés sont également conservés. Grade 2 : preuve explicite forte d’au moins une facette nécessaire ; grade 1 : soutien partiel ou corroboration contextuelle ; grade 0 : page examinée éditorialement mais ne répondant pas à la question ciblée. Une page n’a pas à répondre seule à toute une comparaison pour être fortement pertinente. Aucun grade zéro n’a été déduit de la seule absence de mots-clés.

Les extraits et les réponses attendues ont été relus éditorialement. La recherche de variantes repose ici sur les fragments de preuve et le périmètre documentaire ; elle peut manquer des paraphrases pertinentes. L’exhaustivité des qrels n’est donc pas revendiquée. Les métriques finales devront porter sur une version approuvée, avec cette limite documentée.

## Contrôle sémantique

Les 145 questions ont été examinées par rapport à l’information demandée. semantic_review.jsonl expose les cas liés, les voisins lexicaux et les différences de réponse ; semantic_pairs_145.csv contient les 2 900 couples à disposition du relecteur. Une similarité de chaînes n’est pas un test d’équivalence sémantique. Les questions 014, 019 et 020 demandent une vigilance particulière sur le recouvrement d’informations avec les anciens exemples. Une première proposition 017 sur achats/réinvestissements a été retirée par prudence et remplacée par une question d’attribution de votes distincts ; annotation_tools/rejected_questions.json en conserve la trace. L’indépendance statistique des sujets issus du même corpus n’est pas établie.

Les réponses attendues et les pages de référence sont séparées des questions dans question_gold.jsonl. Les futurs systèmes ne doivent recevoir que le champ question ; les qrels, extraits et réponses servent uniquement à l’évaluation et à la revue.

## Validation à effectuer

Lire les preuves ci-dessous, puis les autres pages du périmètre dans human_review.csv ; ajouter les pages pertinentes manquantes, indiquer les grades 0/1/2 après lecture et signer les jugements. Pour chaque question, approuver ou rejeter son équivalence avec les questions liées et les voisins proposés. Si une question réutilise substantiellement une ancienne réponse, la remplacer avant tout score. Les cases sont laissées vides pour une vraie seconde lecture, pas préremplies comme une approbation.

Après adjudication, versionner les questions et qrels, vérifier le gel puis évaluer une seule fois. Les variantes issues d’une même famille documentaire doivent rester dans le même lot. Ne pas ajuster le pipeline à partir de ces nouveaux résultats. Le lot de 145 questions reste inchangé et exploratoire.

## HOLDOUT_V2_001 — factual / minutes

Using the June 2026 Minutes, give the twelve-month growth rates of the private-sector employment cost index through March and average hourly earnings through May. Were the two reported rates equal?

Réponse attendue : Both were 3.4 percent, although the reported twelve-month periods ended in different months.

Documents demandés : fomcminutes20260617.pdf

Revue sémantique : The old items ask about payroll versus labor-force growth, hiring shortages, or participation/immigration and wages. This item asks for two particular labor-cost measures and their reference periods; it is not answered by those old questions.

Anciennes questions liées : FOMC_089, FOMC_102, FOMC_136

### [fomcminutes20260617.pdf#p4](../raw/minutes/fomcminutes20260617.pdf#page=4) — grade proposé 2

Facette : employment_costs

> The unemployment rate was 4.3 percent in May and had changed little, on balance, since the middle of the previous year. Nonfarm payroll employment rose at a solid pace in the three months through May. The 12-month change in the employment cost index for private-sector workers was 3.4 percent through March, the same as its year-earlier pace. Average hourly earnings increased 3.4 percent over the 12 months ending in May, 0.5 percentage point lower than a year earlier.

Facette : hourly_earnings

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_002 — factual / minutes

According to the January 2024 Minutes, what was the December 2023 unemployment rate, and how did it compare with the third-quarter average?

Réponse attendue : 3.7 percent, the same as the third-quarter average.

Documents demandés : fomcminutes20240131.pdf

Revue sémantique : FOMC_055 concerns the September payroll/unemployment contrast in November 2023; FOMC_058 concerns inflation, and FOMC_060 vacancies/turnover in March 2024. None asks for this December unemployment statistic and its comparison. Same general labor topic is not equivalent requested information.

Anciennes questions liées : FOMC_055, FOMC_058, FOMC_060

### [fomcminutes20240131.pdf#p4](../raw/minutes/fomcminutes20240131.pdf#page=4) — grade proposé 2

Facette : unemployment_comparison

> Labor demand and supply continued to gradually move into better alignment. The average monthly pace of nonfarm payroll employment gains in the fourth quarter was slower than in the third quarter. The unemployment rate remained at 3.7 percent in December, the same as its third-quarter average. However, the labor force participation rate moved down, as did the employment-to-population ratio. The African American unemployment rate declined, and the rate for Hispanics rose; both rates were higher than those for Asians and for whites. The private-sector job openings rate was little changed in November and December, and the quits rate edged

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_003 — factual / statements

In the voting section of the July 30, 2025 Statement, who was explicitly listed as absent and not voting?

Réponse attendue : Adriana D. Kugler.

Documents demandés : monetary20250730a1.pdf

Revue sémantique : The old dissent item concerns Bullard's preferred rate move, and FOMC_077 employment risks. Absence from the July 2025 vote is a distinct institutional fact, not a rephrasing of either.

Anciennes questions liées : FOMC_036, FOMC_077

### [monetary20250730a1.pdf#p2](../raw/statements/monetary20250730a1.pdf#page=2) — grade proposé 2

Facette : absent_member

> Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Michael S. Barr; Susan M. Collins; Lisa D. Cook; Austan D. Goolsbee; Philip N. Jefferson; Alberto G. Musalem; and Jeffrey R. Schmid. Voting against this action were Michelle W. Bowman and Christopher J. Waller, who preferred to lower the target range for the federal funds rate by 1/4 percentage point at this meeting. Absent and not voting was Adriana D. Kugler.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_004 — factual / statements

In the January 27, 2021 release's implementation notes, which Federal Reserve body approved the primary credit rate, and what level did it approve?

Réponse attendue : The Board of Governors unanimously approved the existing primary credit rate of 0.25 percent. This is the primary credit rate, not the federal funds target range.

Documents demandés : monetary20210127a1.pdf

Revue sémantique : FOMC_001 asks the federal funds target range; FOMC_008/009 reserve and reverse-repo rates. Here both the instrument (primary credit) and approving body differ. These facts cannot be replaced by the old target-range answer.

Anciennes questions liées : FOMC_001, FOMC_008, FOMC_009

### [monetary20210127a1.pdf#p4](../raw/statements/monetary20210127a1.pdf#page=4) — grade proposé 2

Facette : body_and_rate

> • In a related action, the Board of Governors of the Federal Reserve System voted unanimously to approve the establishment of the primary credit rate at the existing level of 0.25 percent.

> This information will be updated as appropriate to reflect decisions of the Federal Open Market Committee or the Board of Governors regarding details of the Federal Reserve’s operational tools and approach used to implement monetary policy.

### [monetary20210127a1.pdf#p3](../raw/statements/monetary20210127a1.pdf#page=3) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : This page mentions the Board but its rate is interest on reserves, not the requested primary credit rate.

> • The Board of Governors of the Federal Reserve System voted unanimously to maintain the interest rate paid on required and excess reserve balances at 0.10 percent, effective January 28, 2021.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_005 — explanatory / minutes

In the June 2022 Minutes' discussion of the appropriate policy stance, what conditions led almost all participants to support a 75-basis-point increase, and what concern about inflation expectations reinforced their commitment?

Réponse attendue : A very tight labor market, inflation well above 2 percent and a worsening near-term inflation outlook supported 75 basis points. Elevated inflation pressures and deterioration in some inflation-expectation measures reinforced the commitment to returning inflation to 2 percent.

Documents demandés : fomcminutes20220615.pdf

Revue sémantique : Related monetary-tightening topics exist. FOMC_035 is about starting rate increases in January; FOMC_036 Bullard's March dissent; FOMC_108 cumulative lags; FOMC_117 the cross-period role of anchored long-run expectations. The June 75-bp decision and deterioration in some expectation measures are distinct required evidence. Relation is acknowledged, not treated as proof of statistical independence.

Anciennes questions liées : FOMC_035, FOMC_036, FOMC_108, FOMC_117

### [fomcminutes20220615.pdf#p9](../raw/minutes/fomcminutes20220615.pdf#page=9) — grade proposé 2

Facette : stance_rationale

> In their consideration of the appropriate stance of monetary policy, participants concurred that the labor market was very tight, inflation was well above the Committee’s 2 percent inflation objective, and the near-term inflation outlook had deteriorated since the time of the May meeting. Against this backdrop, almost all participants agreed that it was appropriate to raise the target range for the federal funds rate 75 basis points at this meeting. One participant favored a 50 basis point increase in the target range at this meeting instead of 75 basis points. All participants judged that it was appropriate to continue the process of reducing the size of the Federal Reserve’s balance sheet, as described in the Plans for Reducing the Size of the Federal Reserve’s Balance Sheet that the Committee issued in May. In light of elevated inflation pressures and signs of deterioration in some measures of inflation expectations, all participants reaffirmed their strong commitment to returning inflation to the Committee’s 2 percent objective. Participants observed that a return of inflation to the 2 percent objective was necessary for creating conditions conducive to a sustainably strong labor market over time.

> In discussing potential policy actions at upcoming meetings, participants continued to anticipate that ongoing increases in the target range for the federal funds rate would be appropriate to achieve the Committee’s objectives. In particular, participants judged that an increase of 50 or 75 basis points would likely be appropriate at

Facette : expectations

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_006 — explanatory / minutes

According to the October 2025 Minutes, why could the government shutdown temporarily lower measured GDP growth and later produce a corresponding rebound?

Réponse attendue : While the shutdown continued it reduced government production and purchases; reopening and their return to normal levels were expected to boost growth correspondingly. This temporary effect is distinct from changes in underlying private demand.

Documents demandés : fomcminutes20251029.pdf

Revue sémantique : The old GDP-reading question attributes distortion to net exports; FOMC_133 contrasts GDP and private demand; FOMC_093 concerns October 2026 information gathering. The mechanism here is the direct, reversible loss of government production in the 2025 shutdown.

Anciennes questions liées : FOMC_075, FOMC_093, FOMC_133

### [fomcminutes20251029.pdf#p7](../raw/minutes/fomcminutes20251029.pdf#page=7) — grade proposé 2

Facette : shutdown_and_reopening

> than GDP over the first half but had also slowed relative to its 2024 rate of increase. PDFP growth appeared to have continued at a solid pace in the third quarter, though the government shutdown had reduced the amount of data that was available to gauge third-quarter economic activity. Available data suggested that net exports positively contributed to GDP growth in the third quarter. After falling sharply in the second quarter and then rising somewhat in July, real imports of goods appeared to have resumed falling in August. U.S. real goods exports appeared to have declined moderately in August after having increased modestly in the first half of the year. The government shutdown was expected to reduce GDP growth for as long as it continued, with a corresponding boost to growth once the government reopened and government production and purchases returned to normal levels.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_007 — explanatory / statements

What operational purpose did the June 2021 implementation notes give for authorizing dollar-roll and coupon-swap transactions?

Réponse attendue : To facilitate settlement of the Federal Reserve's agency MBS transactions.

Documents demandés : monetary20210616a1.pdf

Revue sémantique : The old questions ask purchase volumes, milestones or their wind-down. This question concerns the purpose of settlement operations, not the monthly purchase amount.

Anciennes questions liées : FOMC_002, FOMC_028, FOMC_095

### [monetary20210616a1.pdf#p4](../raw/statements/monetary20210616a1.pdf#page=4) — grade proposé 2

Facette : settlement_purpose

> o Engage in dollar roll and coupon swap transactions as necessary to facilitate settlement of the Federal Reserve's agency MBS transactions.”

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_008 — explanatory / statements

Beyond the regular monthly Treasury and agency MBS purchases, what contingency authority did the July 2021 implementation notes give the Desk, and for what market-functioning purpose?

Réponse attendue : The Desk could increase Treasury and agency MBS holdings by additional amounts and buy agency CMBS as needed to sustain smooth functioning of those markets.

Documents demandés : monetary20210728a1.pdf

Revue sémantique : Regular purchase volumes and repo backstop arrangements are old topics, but this item asks the separate contingent securities-purchase authority and its market-functioning condition. It does not ask the regular amounts or names of repo facilities.

Anciennes questions liées : FOMC_002, FOMC_014, FOMC_028

### [monetary20210728a1.pdf#p3](../raw/statements/monetary20210728a1.pdf#page=3) — grade proposé 2

Facette : contingent_purchases

> “Effective July 29, 2021, the Federal Open Market Committee directs the Desk to: o Undertake open market operations as necessary to maintain the federal funds rate in a target range of 0 to 1/4 percent. o Increase the System Open Market Account holdings of Treasury securities by $80 billion per month and of agency mortgage-backed securities (MBS) by $40 billion per month. o Increase holdings of Treasury securities and agency MBS by additional amounts and purchase agency commercial mortgage-backed securities (CMBS) as needed to sustain smooth functioning of markets for these securities. o Conduct overnight repurchase agreement operations with a minimum bid rate of 0.25 percent and with an aggregate operation limit of $500 billion; the aggregate operation limit can be temporarily increased at the discretion of the Chair. o Conduct overnight reverse repurchase agreement operations at an offering rate of 0.05 percent and with a per-counterparty limit of $80 billion per day; the per-counterparty limit can be temporarily increased at the discretion of the Chair. o Roll over at auction all principal payments from the Federal Reserve's holdings of Treasury securities and reinvest all principal payments from the Federal Reserve's holdings of agency debt and agency MBS in agency MBS.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_009 — explanatory / mixed

Use the June 2022 Statement and Minutes to distinguish Esther George's preferred rate increase from the adopted increase, then explain her concerns about the larger move alongside balance-sheet runoff.

Réponse attendue : The adopted increase was 75 bp; George preferred 50 bp. The Minutes explain her concern about policy uncertainty during the start of runoff, unsettled households/businesses and adverse effects on small banks' ability to meet community credit needs.

Documents demandés : monetary20220615a1.pdf, fomcminutes20220615.pdf

Revue sémantique : FOMC_036 is Bullard's March preference for a larger increase; this question requires George's smaller June move and her distinct policy-uncertainty/small-bank reasoning. FOMC_040 concerns household spending resources, not this dissent. Replacing names/dates alone would not suffice; the opposing direction and explanation are the new information.

Anciennes questions liées : FOMC_036, FOMC_040

### [fomcminutes20220615.pdf#p9](../raw/minutes/fomcminutes20220615.pdf#page=9) — grade proposé 2

Facette : adopted_move

> In their consideration of the appropriate stance of monetary policy, participants concurred that the labor market was very tight, inflation was well above the Committee’s 2 percent inflation objective, and the near-term inflation outlook had deteriorated since the time of the May meeting. Against this backdrop, almost all participants agreed that it was appropriate to raise the target range for the federal funds rate 75 basis points at this meeting. One participant favored a 50 basis point increase in the target range at this meeting instead of 75 basis points. All participants judged that it was appropriate to continue the process of reducing the size of the Federal Reserve’s balance sheet, as described in the Plans for Reducing the Size of the Federal Reserve’s Balance Sheet that the Committee issued in May. In light of elevated inflation pressures and signs of deterioration in some measures of inflation expectations, all participants reaffirmed their strong commitment to returning inflation to the Committee’s 2 percent objective. Participants observed that a return of inflation to the 2 percent objective was necessary for creating conditions conducive to a sustainably strong labor market over time.

> In discussing potential policy actions at upcoming meetings, participants continued to anticipate that ongoing increases in the target range for the federal funds rate would be appropriate to achieve the Committee’s objectives. In particular, participants judged that an increase of 50 or 75 basis points would likely be appropriate at

### [monetary20220615a1.pdf#p2](../raw/statements/monetary20220615a1.pdf#page=2) — grade proposé 2

Facette : preferred_move

> Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Michelle W. Bowman; Lael Brainard; James Bullard; Lisa D. Cook; Patrick Harker; Philip N. Jefferson; Loretta J. Mester; and Christopher J. Waller. Voting against this action was Esther L. George, who preferred at this meeting to raise the target range for the federal funds rate by 0.5 percentage point to 1-1/4 percent to 1-1/2 percent. Patrick Harker voted as an alternate member at this meeting.

### [fomcminutes20220615.pdf#p11](../raw/minutes/fomcminutes20220615.pdf#page=11) — grade proposé 2

Facette : reason

> President George dissented because she judged that a large increase in the target range for the federal funds rate would add to uncertainty about policy concurrent with the beginning of balance sheet runoff in ways that could unsettle households and businesses and could also adversely affect the ability of small banks to meet the credit needs of their communities.

### [fomcminutes20220615.pdf#p1](../raw/minutes/fomcminutes20220615.pdf#page=1) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Attendance roster names George but does not state her vote or reason.

> Jerome H. Powell, Chair John C. Williams, Vice Chair Michelle W. Bowman Lael Brainard James Bullard Lisa D. Cook Esther L. George Philip N. Jefferson Loretta J. Mester Christopher J. Waller

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_010 — explanatory / mixed

Using the March 2025 Statement and Minutes, did Waller's dissent concern the federal funds target or the pace of securities runoff, and what reserve evidence and alternative response did he cite?

Réponse attendue : He supported leaving the funds target unchanged but opposed slowing runoff. He cited reserves above $3 trillion and no indication of proximity to ample reserves from indicators or outreach; he preferred relying on existing tools and planning for short-run strains.

Documents demandés : monetary20250319a1.pdf, fomcminutes20250319.pdf

Revue sémantique : FOMC_072 asks how the adopted decision treated Treasury and agency runoff; FOMC_139 asks why participants discussed slowing runoff in March 2024. Here the requested position is the dissent against slowing in March 2025 and Waller's evidence/alternative. Same policy field, different argument and attributed speaker.

Anciennes questions liées : FOMC_072, FOMC_139, FOMC_071

### [monetary20250319a1.pdf#p2](../raw/statements/monetary20250319a1.pdf#page=2) — grade proposé 2

Facette : what_he_opposed

> could impede the attainment of the Committee’s goals. The Committee’s assessments will take into account a wide range of information, including readings on labor market conditions, inflation pressures and inflation expectations, and financial and international developments. Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Michael S. Barr; Michelle W. Bowman; Susan M. Collins; Lisa D. Cook; Austan D. Goolsbee; Philip N. Jefferson; Adriana D. Kugler; Alberto G. Musalem; and Jeffrey R. Schmid. Voting against this action was Christopher J. Waller, who supported no change for the federal funds target range but preferred to continue the current pace of decline in securities holdings.

### [fomcminutes20250319.pdf#p15](../raw/minutes/fomcminutes20250319.pdf#page=15) — grade proposé 2

Facette : reserve_evidence_and_alternative

> Governor Waller preferred no change in the federal funds target range and continuing the pace of decline in securities holdings in place at the time of the vote. This view was based on reserve balances being over $3 trillion as well as no evidence from money market indicators or his outreach conversations that the banking system is getting close to an ample level of reserves. In addition, rather than changing the pace of balance sheet reduction, he thought the Federal Reserve should rely on its existing tools and develop a plan for how to respond to short-run strains if they emerge.

### [fomcminutes20250319.pdf#p12](../raw/minutes/fomcminutes20250319.pdf#page=12) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Provides reserve-management context and existing tools, but does not attribute all the arguments specifically to Waller.

> Participants assessed that balance sheet reduction had gone well thus far. All participants judged it appropriate to continue the process of reducing the Federal Reserve’s securities holdings. Almost all participants supported a slowing of the pace of runoff at this meeting. Most participants noted the importance of clearly communicating that slowing the runoff pace had no implications for the stance of monetary policy, would not affect the long-term path of the balance sheet, was a natural progression of the slowing decided at the May 2024 meeting, and was in line with the Committee’s principles and plans for balance sheet reduction announced in 2022. Some participants noted that a slower pace of runoff would also help guard against reserve scarcity emerging with little advance notice during a period of potentially rapid increase in the TGA. Several participants did not see a compelling case for slowing the pace of runoff at this meeting. A number of participants commented that the Committee’s existing tools could also be used to help address potential disruptions to the market for reserves. Some participants highlighted the importance of the Federal Reserve’s ceiling tools and encouraged the ongoing efforts of the Desk to improve the efficacy of the standing repo facility. Several participants observed that the Federal Reserve’s traditional tool of open market operations could also be used should signs of reserve scarcity unexpectedly emerge. Many participants expressed interest in continued discussion of technical aspects of balance sheet policy and tools after the framework review is completed.

### [fomcminutes20250319.pdf#p13](../raw/minutes/fomcminutes20250319.pdf#page=13) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Corroborates unchanged funds target versus slowing runoff, without the full named dissent and reserve evidence.

> In support of its goals, the Committee agreed to maintain the target range for the federal funds rate at 4¼ to 4½ percent. Members agreed that in considering the extent and timing of additional adjustments to the target range for the federal funds rate, the Committee would carefully assess incoming data, the evolving outlook, and the balance of risks. Almost all members agreed to reducing the Committee’s securities holdings at a slower pace, with the monthly redemption cap on Treasury securities reduced from $25 billion to $5 billion and the monthly redemption cap on agency debt and agency mortgage-backed securities maintained at $35 billion. One member agreed with the Committee’s decision to maintain the target range for the federal funds rate at 4¼ to 4½ percent but voted against the overall decision because he preferred to continue the pace of decline in securities holdings in place at the time of the vote. All members agreed that the postmeeting statement should affirm their strong commitment both to supporting maximum employment and to returning inflation to the Committee’s 2 percent objective.

### [fomcminutes20250319.pdf#p16](../raw/minutes/fomcminutes20250319.pdf#page=16) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Staff and membership roster, not Waller's position or justification.

> Philip N. Jefferson Adriana D. Kugler Alberto G. Musalem Jeffrey R. Schmid Christopher J. Waller Beth M. Hammack, Patrick Harker, Neel Kashkari, and Lorie K. Logan, Alternate Members of the Committee Thomas I. Barkin, Raphael W. Bostic, and Mary C. Daly, Presidents of the Federal Reserve Banks of Richmond, Atlanta, and San Francisco, respectively Joshua Gallin, Secretary Matthew M. Luecke, Deputy Secretary Brian J. Bonis, Assistant Secretary Michelle A. Smith, Assistant Secretary Mark E. Van Der Weide, General Counsel Richard Ostrander, Deputy General Counsel Trevor A. Reeve, Economist Stacey Tevlin, Economist Beth Anne Wilson,2 Economist Shaghil Ahmed, James A. Clouse, Eric M. Engen, Anna Paulson, and William Wascher, Associate Economists Roberto Perli, Manager, System Open Market Account Julie Ann Remache, Deputy Manager, System Open Market Account Stephanie R. Aaronson, Senior Associate Director, Division of Research and Statistics, Board Jose Acosta, Senior System Engineer II, Division of Information Technology, Board Alyssa Arute,3 Assistant Director, Division of Reserve Bank Operations and Payment Systems, Board Alessandro Barbarino, Special Adviser to the Board, Division of Board Members, Board David Bowman, Senior Associate Director, Division of Monetary Affairs, Board Brent Bundick,4 Vice President, Federal Reserve Bank of Kansas City Christian Cabanilla,3 Policy and Market Analysis Advisor, Federal Reserve Bank of New York Isabel Cairó,4 Group Manager, Division of Monetary Affairs, Board Michele Cavallo, Special Adviser to the Board, Division of Board Members, Board Daniel Cooper, Vice President, Federal Reserve Bank of Boston Stephanie E. Curcuru, Deputy Director, Division of International Finance, Board Keshav Dogra, Research Advisor, Federal Reserve Bank of New York Burcu Duygan-Bump, Associate Director, Division of Research and Statistics, Board Eric C. Engstrom, Associate Director, Division of Monetary Affairs, Board

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_011 — comparative / minutes

Compare staff projections of total PCE inflation for 2023 and 2024 in the May and July 2022 Minutes. By how much did each projected annual rate change?

Réponse attendue : For 2023: 2.5 percent in May to 2.2 percent in July, down 0.3 pp. For 2024: 2.1 to 1.9 percent, down 0.2 pp. These are forecasts, not realized inflation.

Documents demandés : fomcminutes20220504.pdf, fomcminutes20220727.pdf

Revue sémantique : Old items concern May 2023 headline-versus-core explanations, realized December 2023 rates, or supply persistence in 2021. This item compares revisions of explicitly future total-PCE forecasts across May/July 2022; it is not an old realized-rate or policy-stance question.

Anciennes questions liées : FOMC_050, FOMC_058, FOMC_029

### [fomcminutes20220504.pdf#p6](../raw/minutes/fomcminutes20220504.pdf#page=6) — grade proposé 2

Facette : may_forecast

> The staff’s projection for PCE price inflation was revised up slightly in the second half of 2022 and in 2023 in response to the slow resolution of supply constraints seen over the first part of 2022, a higher projected path for import prices, and a judgment that wage increases would put more upward pressure on services prices than previously assumed. All told, total PCE price inflation was expected to be 4.3 percent in 2022. PCE price inflation was then expected to step down to 2.5 percent in 2023 and to 2.1 percent in 2024 as supply–demand im- balances in the economy were reduced by slowing aggregate demand and an anticipated easing of supply constraints.

### [fomcminutes20220727.pdf#p6](../raw/minutes/fomcminutes20220727.pdf#page=6) — grade proposé 2

Facette : july_forecast

> Total PCE price inflation was expected to be 4.8 percent in 2022, and core inflation was expected to be 4.0 percent. Core PCE price inflation was expected to step down to 2.6 percent in 2023 and to 2.0 percent in 2024; the projected deceleration in core prices was attributable to the anticipated resolution of supply–demand imbalances, a labor market that was expected to become less tight over the projection period, and a projected decline in import price inflation. Total PCE inflation was expected to decline to 2.2 percent in 2023 and to 1.9 percent in 2024, reflecting the anticipated slowing in core inflation and a projected rapid deceleration in consumer food and energy prices in coming quarters.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_012 — comparative / statements

Compare the dissenting preferences reported in the September and December 2024 Statements: who dissented in each, and did each prefer a smaller cut or no cut?

Réponse attendue : September: Michelle Bowman preferred a 25-bp cut rather than 50 bp. December: Beth Hammack preferred maintaining 4.5–4.75 percent rather than cutting. A smaller cut and no cut are different preferences.

Documents demandés : monetary20240918a1.pdf, monetary20241218a1.pdf

Revue sémantique : The old items concern adopted cuts, confidence for them, or their macro rationale. The requested answers here are named dissenters and their alternatives. The adopted action appears as context, not as the information being retested.

Anciennes questions liées : FOMC_066, FOMC_068, FOMC_142

### [monetary20240918a1.pdf#p2](../raw/statements/monetary20240918a1.pdf#page=2) — grade proposé 2

Facette : september_dissent

> could impede the attainment of the Committee’s goals. The Committee’s assessments will take into account a wide range of information, including readings on labor market conditions, inflation pressures and inflation expectations, and financial and international developments. Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Thomas I. Barkin; Michael S. Barr; Raphael W. Bostic; Lisa D. Cook; Mary C. Daly; Beth M. Hammack; Philip N. Jefferson; Adriana D. Kugler; and Christopher J. Waller. Voting against this action was Michelle W. Bowman, who preferred to lower the target range for the federal funds rate by 1/4 percentage point at this meeting.

### [monetary20241218a1.pdf#p2](../raw/statements/monetary20241218a1.pdf#page=2) — grade proposé 2

Facette : december_dissent

> into account a wide range of information, including readings on labor market conditions, inflation pressures and inflation expectations, and financial and international developments. Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Thomas I. Barkin; Michael S. Barr; Raphael W. Bostic; Michelle W. Bowman; Lisa D. Cook; Mary C. Daly; Philip N. Jefferson; Adriana D. Kugler; and Christopher J. Waller. Voting against the action was Beth M. Hammack, who preferred to maintain the target range for the federal funds rate at 4-1/2 to 4-3/4 percent.

### [monetary20241218a1.pdf#p1](../raw/statements/monetary20241218a1.pdf#page=1) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : The adopted cut provides the baseline for distinguishing Hammack's preference for no cut, but does not identify her dissent.

> Recent indicators suggest that economic activity has continued to expand at a solid pace. Since earlier in the year, labor market conditions have generally eased, and the unemployment rate has moved up but remains low. Inflation has made progress toward the Committee’s 2 percent objective but remains somewhat elevated. The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer run. The Committee judges that the risks to achieving its employment and inflation goals are roughly in balance. The economic outlook is uncertain, and the Committee is attentive to the risks to both sides of its dual mandate. In support of its goals, the Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 4-1/4 to 4-1/2 percent. In considering the extent and timing of additional adjustments to the target range for the federal funds rate, the Committee will carefully assess incoming data, the evolving outlook, and the balance of risks. The Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage‑backed securities. The Committee is strongly committed to supporting maximum employment and returning inflation to its 2 percent objective. In assessing the appropriate stance of monetary policy, the Committee will continue to monitor the implications of incoming information for the economic outlook. The Committee would be prepared to adjust the stance of monetary policy as appropriate if risks emerge that could impede the attainment of the Committee’s goals. The Committee’s assessments will take

### [monetary20241218a1.pdf#p4](../raw/statements/monetary20241218a1.pdf#page=4) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Quarter-point primary-credit reduction is not a Committee dissenter's preference about the funds target.

> In a related action, the Board of Governors of the Federal Reserve System voted unanimously to approve a 1/4 percentage point decrease in the primary credit rate to 4.5 percent, effective December 19, 2024. In taking this action, the Board approved requests to establish that rate submitted by the Boards of Directors of the Federal Reserve Banks of Boston, New York, Philadelphia, Cleveland, Richmond, Atlanta, Chicago, and San Francisco.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_013 — comparative / statements

Compare the primary credit rates approved in the March and May 2022 implementation notes, including each effective date. What was the difference between the approved levels?

Réponse attendue : 0.5 percent effective March 17, 2022; 1 percent effective May 5, 2022. The approved levels differed by 0.5 percentage point.

Documents demandés : monetary20220316a1.pdf, monetary20220504a1.pdf

Revue sémantique : The old questions involve the funds target, interest on reserves, or repo rates/limits. The primary credit facility and effective dates are different requested instruments/information. This is not merely moving an old funds-target question to a new date.

Anciennes questions liées : FOMC_036, FOMC_008, FOMC_138

### [monetary20220316a1.pdf#p3](../raw/statements/monetary20220316a1.pdf#page=3) — grade proposé 2

Facette : march_primary_credit

> • The Board of Governors of the Federal Reserve System voted unanimously to raise the interest rate paid on reserve balances to 0.4 percent, effective March 17, 2022.

> “Effective March 17, 2022, the Federal Open Market Committee directs the Desk to: o Undertake open market operations as necessary to maintain the federal funds rate in a target range of 1/4 to 1/2 percent. o Conduct overnight repurchase agreement operations with a minimum bid rate of 0.5 percent and with an aggregate operation limit of $500 billion; the aggregate operation limit can be temporarily increased at the discretion of the Chair. o Conduct overnight reverse repurchase agreement operations at an offering rate of 0.3 percent and with a per-counterparty limit of $160 billion per day; the per-counterparty limit can be temporarily increased at the discretion of the Chair. o Roll over at auction all principal payments from the Federal Reserve's holdings of Treasury securities and reinvest all principal payments from the Federal Reserve's holdings of agency debt and agency mortgage-backed securities (MBS) in agency MBS. o Allow modest deviations from stated amounts for reinvestments, if needed for operational reasons. o Engage in dollar roll and coupon swap transactions as necessary to facilitate settlement of the Federal Reserve's agency MBS transactions.”

> • In a related action, the Board of Governors of the Federal Reserve System voted unanimously to approve a 1/4 percentage point increase in the primary credit rate to 0.5 percent, effective March 17, 2022. In taking this action, the Board approved requests to establish that rate submitted by the Boards of Directors of the Federal Reserve Banks of Boston, Philadelphia, Cleveland, Richmond, Atlanta, Chicago, St. Louis, Minneapolis, Kansas City, and San Francisco.

### [monetary20220504a1.pdf#p4](../raw/statements/monetary20220504a1.pdf#page=4) — grade proposé 2

Facette : may_primary_credit

> In a related action, the Board of Governors of the Federal Reserve System voted unanimously to approve a 1/2 percentage point increase in the primary credit rate to 1 percent, effective May 5, 2022. In taking this action, the Board approved requests to establish that rate submitted by the Boards of Directors of the Federal Reserve Banks of Boston, New York, Philadelphia, Cleveland, Richmond, Atlanta, Chicago, St. Louis, Minneapolis, Kansas City, Dallas, and San Francisco.

### [monetary20220504a1.pdf#p3](../raw/statements/monetary20220504a1.pdf#page=3) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Effective-date match is a distractor: this page states reserve interest and funds/repo instructions, not the requested primary-credit approval.

> • The Board of Governors of the Federal Reserve System voted unanimously to raise the interest rate paid on reserve balances to 0.9 percent, effective May 5, 2022.

> “Effective May 5, 2022, the Federal Open Market Committee directs the Desk to: o Undertake open market operations as necessary to maintain the federal funds rate in a target range of 3/4 to 1 percent. o Conduct overnight repurchase agreement operations with a minimum bid rate of 1.0 percent and with an aggregate operation limit of $500 billion; the aggregate operation limit can be temporarily increased at the discretion of the Chair. o Conduct overnight reverse repurchase agreement operations at an offering rate of 0.8 percent and with a per-counterparty limit of $160 billion per day; the per-counterparty limit can be temporarily increased at the discretion of the Chair. o Roll over at auction the amount of principal payments from the Federal Reserve's holdings of Treasury securities maturing in the calendar month of June that exceeds a monthly cap of $30 billion. Redeem Treasury coupon securities up to this monthly cap and Treasury bills to the extent that coupon principal payments are less than the monthly cap. o Reinvest into agency mortgage-backed securities (MBS) the amount of principal payments from the Federal Reserve's holdings of agency debt and agency MBS received in the calendar month of June that exceeds a monthly cap of $17.5 billion. o Allow modest deviations from stated amounts for reinvestments, if needed for operational reasons. o Engage in dollar roll and coupon swap transactions as necessary to facilitate settlement of the Federal Reserve's agency MBS transactions.”

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_014 — comparative / mixed

Compare March and September 2023 using each meeting's Statement and staff review in the Minutes: how did the public description of activity and the staff's GDP assessment change? Keep the public wording separate from the staff assessment.

Réponse attendue : March Statement: modest growth in spending/production; March staff review: modest first-quarter GDP expansion. September Statement: activity expanding at a solid pace; September staff review: GDP rising solidly in the third quarter. Public descriptions and staff quarter-specific assessments should be attributed separately.

Documents demandés : monetary20230322a1.pdf, fomcminutes20230322.pdf, monetary20230920a1.pdf, fomcminutes20230920.pdf

Revue sémantique : FOMC_057 asks the subsequent slowdown in December 2023; FOMC_124 concerns hold-versus-cut policies; FOMC_141 macro considerations for September/December holds. Here four separately attributed descriptions and two quarter-specific staff assessments are required. The September growth fact is related background, so residual thematic dependence is disclosed.

Anciennes questions liées : FOMC_057, FOMC_124, FOMC_141

### [monetary20230322a1.pdf#p1](../raw/statements/monetary20230322a1.pdf#page=1) — grade proposé 2

Facette : march_public

> Recent indicators point to modest growth in spending and production. Job gains have picked up in recent months and are running at a robust pace; the unemployment rate has remained low. Inflation remains elevated. The U.S. banking system is sound and resilient. Recent developments are likely to result in tighter credit conditions for households and businesses and to weigh on economic activity, hiring, and inflation. The extent of these effects is uncertain. The Committee remains highly attentive to inflation risks. The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer run. In support of these goals, the Committee decided to raise the target range for the federal funds rate to 4-3/4 to 5 percent. The Committee will closely monitor incoming information and assess the implications for monetary policy. The Committee anticipates that some additional policy firming may be appropriate in order to attain a stance of monetary policy that is sufficiently restrictive to return inflation to 2 percent over time. In determining the extent of future increases in the target range, the Committee will take into account the cumulative tightening of monetary policy, the lags with which monetary policy affects economic activity and inflation, and economic and financial developments. In addition, the Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage-backed securities, as described in its previously announced plans. The Committee is strongly committed to returning inflation to its 2 percent objective.

### [fomcminutes20230322.pdf#p3](../raw/minutes/fomcminutes20230322.pdf#page=3) — grade proposé 2

Facette : march_staff

> The information available at the time of the March 21– 22 meeting indicated that labor market conditions remained tight in January and February, with robust job gains and the unemployment rate near a historical low. Consumer price inflation—as measured by the 12-month percent change in the price index for personal consumption expenditures (PCE)—was still elevated in January. Real gross domestic product (GDP) appeared to be expanding at a modest pace in the first quarter. Although financial market data had shown reactions to developments in the banking sector late in the intermeeting period, there were essentially no economic data available that covered this period.

### [monetary20230920a1.pdf#p1](../raw/statements/monetary20230920a1.pdf#page=1) — grade proposé 2

Facette : september_public

> Recent indicators suggest that economic activity has been expanding at a solid pace. Job gains have slowed in recent months but remain strong, and the unemployment rate has remained low. Inflation remains elevated. The U.S. banking system is sound and resilient. Tighter credit conditions for households and businesses are likely to weigh on economic activity, hiring, and inflation. The extent of these effects remains uncertain. The Committee remains highly attentive to inflation risks. The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer run. In support of these goals, the Committee decided to maintain the target range for the federal funds rate at 5-1/4 to 5-1/2 percent. The Committee will continue to assess additional information and its implications for monetary policy. In determining the extent of additional policy firming that may be appropriate to return inflation to 2 percent over time, the Committee will take into account the cumulative tightening of monetary policy, the lags with which monetary policy affects economic activity and inflation, and economic and financial developments. In addition, the Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage-backed securities, as described in its previously announced plans. The Committee is strongly committed to returning inflation to its 2 percent objective. In assessing the appropriate stance of monetary policy, the Committee will continue to monitor the implications of incoming information for the economic outlook. The Committee

### [fomcminutes20230920.pdf#p3](../raw/minutes/fomcminutes20230920.pdf#page=3) — grade proposé 2

Facette : september_staff

> The data available at the time of the September 19–20 meeting suggested that real gross domestic product (GDP) was rising at a solid pace in the third quarter. The labor market continued to be tight, with the unemployment rate low and job gains slowing but remaining strong. Consumer price inflation was still elevated.

### [fomcminutes20230322.pdf#p6](../raw/minutes/fomcminutes20230322.pdf#page=6) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Participants' assessment corroborates the modest-growth description; it is not the requested quarter-specific staff passage or literal public release.

> In their discussion of current economic conditions, participants noted that recent indicators pointed to modest growth in spending and production. At the same time, though, participants noted that job gains had picked up in recent months and were running at a robust pace; the unemployment rate had remained low. Inflation remained elevated. Participants agreed that the U.S. banking system remained sound and resilient. They commented that recent developments in the banking sector were likely to result in tighter credit conditions for households and businesses and to weigh on economic activity, hiring, and inflation. Participants agreed that the extent of these effects was uncertain. Against this

### [fomcminutes20230322.pdf#p9](../raw/minutes/fomcminutes20230322.pdf#page=9) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Members' modest-growth assessment is corroborating evidence, with a different attribution from the public and staff passages.

> In their discussion of monetary policy for this meeting, members agreed that recent indicators pointed to mod- est growth in spending and production. They also concurred that job gains had picked up in recent months and were running at a robust pace, that the unemployment rate had remained low, and that inflation remains elevated. Members concurred that the U.S. banking system is sound and resilient. They also agreed that recent developments were likely to result in tighter credit conditions for households and businesses and to weigh on economic activity, hiring, and inflation, but that the extent of these effects was uncertain. Members also concurred that they remained highly attentive to inflation risks.

### [fomcminutes20230322.pdf#p10](../raw/minutes/fomcminutes20230322.pdf#page=10) — grade proposé 2

Facette : editorial_corroboration_or_distractor

Motif du jugement : Minutes reproduce the public Statement's modest spending/production wording, providing an additional direct source.

> “Recent indicators point to modest growth in spending and production. Job gains have picked up in recent months and are running at a robust pace; the unemployment rate has remained low. Inflation remains elevated.

### [fomcminutes20230920.pdf#p9](../raw/minutes/fomcminutes20230920.pdf#page=9) — grade proposé 2

Facette : editorial_corroboration_or_distractor

Motif du jugement : Minutes reproduce the public Statement's solid-pace wording.

> “Recent indicators suggest that economic activity has been expanding at a solid pace. Job gains have slowed in recent months but remain strong, and the unemployment rate has remained low. Inflation remains elevated.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_015 — comparative / mixed

In January 2026, how did the rate cuts expected by market measures and Desk survey respondents differ from the action and forward-looking language actually announced in the Statement? Do not treat survey expectations as an FOMC commitment.

Réponse attendue : Markets indicated one to two 25-bp cuts in 2026; the Desk survey median modal path indicated two. The Committee actually maintained 3.5–3.75 percent and said further adjustments would depend on incoming data, the outlook and risk balance. The survey path is not an announced commitment to those cuts.

Documents demandés : fomcminutes20260128.pdf, monetary20260128a1.pdf

Revue sémantique : FOMC_082/083 ask labor and inflation expectations, not policy-rate survey paths; FOMC_145 compares 2024 market-implied shifts; FOMC_124 contrasts policy statements. Distinguishing respondents' expectations from an actual Committee action is the new attribution task, not a request for the old expectation shift.

Anciennes questions liées : FOMC_082, FOMC_083, FOMC_145, FOMC_124

### [fomcminutes20260128.pdf#p4](../raw/minutes/fomcminutes20260128.pdf#page=4) — grade proposé 2

Facette : expectations

> The manager turned first to an overview of broad market developments during the intermeeting period. Respondents to the Open Market Desk Survey of Market Expectations (Desk survey) continued to see the economy as resilient and again marked up their forecasts for real gross domestic product (GDP) growth in 2026, while their expectations for headline personal consumption expenditures (PCE) inflation and the unemployment rate were little changed. Market- and survey- based policy rate expectations were likewise little changed. Market-based measures of policy rate expectations indicated one to two 25 basis point rate cuts this year, and the median modal path of the federal funds rate, as given in the Desk survey, continued to indicate expectations of two 25 basis point rate cuts this year.

### [monetary20260128a1.pdf#p1](../raw/statements/monetary20260128a1.pdf#page=1) — grade proposé 2

Facette : announced_action

> Available indicators suggest that economic activity has been expanding at a solid pace. Job gains have remained low, and the unemployment rate has shown some signs of stabilization. Inflation remains somewhat elevated. The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer run. Uncertainty about the economic outlook remains elevated. The Committee is attentive to the risks to both sides of its dual mandate. In support of its goals, the Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent. In considering the extent and timing of additional adjustments to the target range for the federal funds rate, the Committee will carefully assess incoming data, the evolving outlook, and the balance of risks. The Committee is strongly committed to supporting maximum employment and returning inflation to its 2 percent objective. In assessing the appropriate stance of monetary policy, the Committee will continue to monitor the implications of incoming information for the economic outlook. The Committee would be prepared to adjust the stance of monetary policy as appropriate if risks emerge that could impede the attainment of the Committee’s goals. The Committee’s assessments will take into account a wide range of information, including readings on labor market conditions, inflation pressures and inflation expectations, and financial and international developments.

### [fomcminutes20260128.pdf#p13](../raw/minutes/fomcminutes20260128.pdf#page=13) — grade proposé 2

Facette : editorial_corroboration_or_distractor

Motif du jugement : Members' policy action and data-dependent adjustment language directly corroborate the announced decision.

> In support of its goals, almost all members decided to maintain the target range for the federal funds rate at 3½ to 3¾ percent. Two members voted against that decision and preferred to lower the target range by ¼ percentage point. Members agreed that in considering the extent and timing of additional adjustments to the target range for the federal funds rate, the Committee would carefully assess incoming data, the evolving outlook, and the balance of risks. Members agreed that

### [fomcminutes20260128.pdf#p14](../raw/minutes/fomcminutes20260128.pdf#page=14) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Implementation instructions corroborate the maintained range, but not the survey comparison or full forward-looking language.

>  Undertake open market operations as necessary to maintain the federal funds rate in a target range of 3½ to 3¾ percent.

### [fomcminutes20260128.pdf#p15](../raw/minutes/fomcminutes20260128.pdf#page=15) — grade proposé 2

Facette : editorial_corroboration_or_distractor

Motif du jugement : Minutes quote the public decision and its conditional future-adjustment language.

> In support of its goals, the Committee decided to maintain the target range for the federal funds rate at 3½ to 3¾ percent. In considering the extent and timing of additional adjustments to the target range for the federal funds rate, the Committee will carefully assess incoming data, the evolving outlook, and the balance of risks. The Committee is strongly committed to supporting maximum employment and returning inflation to its 2 percent objective.

### [monetary20260128a1.pdf#p3](../raw/statements/monetary20260128a1.pdf#page=3) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Desk directive independently corroborates the maintained target; it supplies only part of the requested comparison.

> "Effective January 29, 2026, the Federal Open Market Committee directs the Desk to: o Undertake open market operations as necessary to maintain the federal funds rate in a target range of 3-1/2 to 3-3/4 percent. o Conduct standing overnight repurchase agreement operations at a rate of 3.75 percent. o Conduct standing overnight reverse repurchase agreement operations at an offering rate of 3.5 percent and with a per-counterparty limit of $160 billion per day. o Increase the System Open Market Account holdings of securities through purchases of Treasury bills and, if needed, other Treasury securities with remaining maturities of 3 years or less to maintain an ample level of reserves. o Roll over at auction all principal payments from the Federal Reserve’s holdings of Treasury securities. Reinvest all principal payments from the Federal Reserve's holdings of agency securities into Treasury bills."

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_016 — multi_evidence / minutes

Using the July 2022 Minutes, report total and core PCE inflation observed over the twelve months ending in May, and total and core PCE inflation forecast for 2022 as a whole. Explain why those two pairs must not be treated as measurements for the same reference period.

Réponse attendue : Observed May twelve-month rates: total 6.3 percent, core 4.7 percent. Staff forecasts for 2022 as a whole: total 4.8 percent, core 4.0 percent. The first pair is backward-looking realized data through May; the second is a full-year projection, not the same observation window.

Documents demandés : fomcminutes20220727.pdf

Revue sémantique : The old questions ask why headline was forecast below core in May 2023 or the spread in December 2023 realized rates. This asks for two separate reference periods and the observed-versus-projected distinction, rather than the old rate spread or energy-price explanation.

Anciennes questions liées : FOMC_050, FOMC_058

### [fomcminutes20220727.pdf#p4](../raw/minutes/fomcminutes20220727.pdf#page=4) — grade proposé 2

Facette : observed_rates

> Consumer price inflation remained elevated. Total PCE price inflation was 6.3 percent over the 12 months ending in May, and core PCE price inflation, which excludes changes in consumer energy prices and many consumer food prices, was 4.7 percent over the same period. The trimmed mean measure of 12-month PCE price inflation constructed by the Federal Reserve Bank of Dallas was 4.0 percent in May, 2.1 percentage points higher than its year-earlier rate of increase. In June, the 12-month change in the consumer price index (CPI) was 9.1 percent, while core CPI inflation was 5.9 percent over the same period. Survey-based measures of short-run inflation expectations remained elevated; by contrast, some measures of longer-term inflation expectations moved lower in recent weeks.

### [fomcminutes20220727.pdf#p6](../raw/minutes/fomcminutes20220727.pdf#page=6) — grade proposé 2

Facette : forecast_rates

> Total PCE price inflation was expected to be 4.8 percent in 2022, and core inflation was expected to be 4.0 percent. Core PCE price inflation was expected to step down to 2.6 percent in 2023 and to 2.0 percent in 2024; the projected deceleration in core prices was attributable to the anticipated resolution of supply–demand imbalances, a labor market that was expected to become less tight over the projection period, and a projected decline in import price inflation. Total PCE inflation was expected to decline to 2.2 percent in 2023 and to 1.9 percent in 2024, reflecting the anticipated slowing in core inflation and a projected rapid deceleration in consumer food and energy prices in coming quarters.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_017 — multi_evidence / mixed

Did Stephen Miran abstain from the September 2025 monetary-policy vote? Distinguish the Minutes' vote on ratifying the Desk's domestic transactions from the policy roll call in the Statement, using evidence for both resolutions.

Réponse attendue : No. The Minutes say he abstained when the Committee ratified the Desk's domestic transactions. The Statement records him as voting against the monetary-policy action. Abstaining on the transaction-ratification resolution is not abstaining on the policy resolution.

Documents demandés : fomcminutes20250917.pdf, monetary20250917a1.pdf

Revue sémantique : No old question asks whether an abstention on Desk-transaction ratification is a different resolution from the monetary-policy vote. FOMC_036 asks Bullard's preferred rate move; FOMC_078 jobs/inflation trends. The new task is resolution-specific vote attribution, not a new date for the old rate-preference question. It is related within this holdout to item 018 but asks a different fact: abstention versus opposition, rather than preferred cuts and reasoning; both belong to the same future test partition.

Anciennes questions liées : FOMC_036, FOMC_078

### [fomcminutes20250917.pdf#p4](../raw/minutes/fomcminutes20250917.pdf#page=4) — grade proposé 2

Facette : desk_transaction_vote

> All but one member of the Committee voted to ratify the Desk’s domestic transactions over the intermeeting period. Governor Stephen Miran, who had been sworn in as a member of the Board that morning, abstained from voting. There were no intervention operations in foreign currencies for the System’s account during the intermeeting period.

### [monetary20250917a1.pdf#p2](../raw/statements/monetary20250917a1.pdf#page=2) — grade proposé 2

Facette : policy_vote

> inflation pressures and inflation expectations, and financial and international developments. Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Michael S. Barr; Michelle W. Bowman; Susan M. Collins; Lisa D. Cook; Austan D. Goolsbee; Philip N. Jefferson; Alberto G. Musalem; Jeffrey R. Schmid; and Christopher J. Waller. Voting against this action was Stephen I. Miran, who preferred to lower the target range for the federal funds rate by 1/2 percentage point at this meeting.

### [fomcminutes20250917.pdf#p13](../raw/minutes/fomcminutes20250917.pdf#page=13) — grade proposé 2

Facette : editorial_corroboration_or_distractor

Motif du jugement : The named monetary-policy opposition is recorded in the Minutes as an additional direct source, distinct from the earlier abstention.

> Voting against this action: Stephen I. Miran.

### [fomcminutes20250917.pdf#p11](../raw/minutes/fomcminutes20250917.pdf#page=11) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : The policy action records one member voting against; the member is not named on this page.

> In support of the Committee’s goals and in light of the shift in the balance of risks, almost all members agreed to lower the target range for the federal funds rate ¼ percentage point to 4 to 4¼ percent. One member voted against that decision, preferring to lower the target range ½ percentage point at this meeting. Members agreed that, in considering additional adjustments to the target range for the federal funds rate, the Committee would carefully assess incoming data, the evolving outlook, and the balance of risks. All members agreed that the postmeeting statement should affirm their strong commitment both to supporting maximum employment and to returning inflation to the Committee’s 2 percent objective.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_018 — multi_evidence / mixed

Contrast the July and September 2025 policy votes using the Statements and September Minutes. Who wanted a quarter-point cut in July, who wanted a half-point cut in September, and what labor-market and underlying-inflation arguments supported the September dissenter's preference?

Réponse attendue : July: Bowman and Waller preferred a 25-bp cut. September: Stephen Miran preferred 50 bp, citing further labor-market softening and underlying inflation closer to 2 percent than the data suggested; he also argued the neutral rate had fallen.

Documents demandés : monetary20250730a1.pdf, monetary20250917a1.pdf, fomcminutes20250917.pdf

Revue sémantique : The old voting question is Bullard in March 2022. July/September 2025 old questions concern employment risks or jobs/inflation trends, not the named dissenting coalitions and Miran's attributed reasoning. Some economic background is shared; the requested actor-specific combination is new.

Anciennes questions liées : FOMC_036, FOMC_078, FOMC_077

### [monetary20250730a1.pdf#p2](../raw/statements/monetary20250730a1.pdf#page=2) — grade proposé 2

Facette : july_dissenters

> Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Michael S. Barr; Susan M. Collins; Lisa D. Cook; Austan D. Goolsbee; Philip N. Jefferson; Alberto G. Musalem; and Jeffrey R. Schmid. Voting against this action were Michelle W. Bowman and Christopher J. Waller, who preferred to lower the target range for the federal funds rate by 1/4 percentage point at this meeting. Absent and not voting was Adriana D. Kugler.

### [monetary20250917a1.pdf#p2](../raw/statements/monetary20250917a1.pdf#page=2) — grade proposé 2

Facette : september_preference

> inflation pressures and inflation expectations, and financial and international developments. Voting for the monetary policy action were Jerome H. Powell, Chair; John C. Williams, Vice Chair; Michael S. Barr; Michelle W. Bowman; Susan M. Collins; Lisa D. Cook; Austan D. Goolsbee; Philip N. Jefferson; Alberto G. Musalem; Jeffrey R. Schmid; and Christopher J. Waller. Voting against this action was Stephen I. Miran, who preferred to lower the target range for the federal funds rate by 1/2 percentage point at this meeting.

### [fomcminutes20250917.pdf#p13](../raw/minutes/fomcminutes20250917.pdf#page=13) — grade proposé 2

Facette : september_reasoning

> Governor Miran preferred to lower the target range for the federal funds rate by ½ percentage point at this meeting in light of further softening in the labor market over the first half of the year and underlying inflation that in his view was meaningfully closer to 2 percent than was apparent in the data. Governor Miran also expressed the view that additional policy easing was also appropriate to reflect that the neutral rate of interest had fallen due to factors such as increased tariff revenues that had raised net national savings and changes in immigration policy that had reduced population growth.

### [fomcminutes20250917.pdf#p10](../raw/minutes/fomcminutes20250917.pdf#page=10) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : General participants' risk discussion does not identify Miran's specific vote or attributed reasons.

> participants supported reducing the target range for the federal funds rate ¼ percentage point at this meeting. Participants generally noted that their judgments about this meeting’s appropriate policy action reflected a shift in the balance of risks. In particular, most participants observed that it was appropriate to move the target range for the federal funds rate toward a more neutral setting because they judged that downside risks to employment had increased over the intermeeting period and that upside risks to inflation had either diminished or not increased. A few participants stated there was merit in keeping the federal funds rate unchanged at this meeting or that they could have supported such a decision. These participants noted that progress toward the Committee’s 2 percent inflation objective had stalled this year as inflation readings increased and expressed concern that longer-term inflation expectations may rise if inflation does not return to its objective in a timely manner. One participant agreed with the need to move policy toward a more neutral stance but preferred a ½ percentage point reduction at this meeting. All participants judged it appropriate to continue the process of reducing the Federal Reserve’s securities holdings.

### [fomcminutes20250917.pdf#p11](../raw/minutes/fomcminutes20250917.pdf#page=11) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Records a member preferring a half-point cut, without naming him or giving his particular explanation.

> In support of the Committee’s goals and in light of the shift in the balance of risks, almost all members agreed to lower the target range for the federal funds rate ¼ percentage point to 4 to 4¼ percent. One member voted against that decision, preferring to lower the target range ½ percentage point at this meeting. Members agreed that, in considering additional adjustments to the target range for the federal funds rate, the Committee would carefully assess incoming data, the evolving outlook, and the balance of risks. All members agreed that the postmeeting statement should affirm their strong commitment both to supporting maximum employment and to returning inflation to the Committee’s 2 percent objective.

### [fomcminutes20250917.pdf#p12](../raw/minutes/fomcminutes20250917.pdf#page=12) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : The adopted quarter-point directive and public text do not identify the July dissenters or Miran's half-point preference and reasoning.

> • Undertake open market operations as necessary to maintain the federal funds rate in a target range of 4 to 4¼ percent.

### [fomcminutes20250917.pdf#p14](../raw/minutes/fomcminutes20250917.pdf#page=14) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Miran's name in a membership list does not support the vote or reasoning.

> Jerome H. Powell, Chair John C. Williams, Vice Chair Michael S. Barr Michelle W. Bowman Susan M. Collins Lisa D. Cook Austan D. Goolsbee Philip N. Jefferson Stephen I. Miran Alberto G. Musalem Jeffrey R. Schmid Christopher J. Waller

### [monetary20250917a1.pdf#p1](../raw/statements/monetary20250917a1.pdf#page=1) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Adopted quarter-point cut is not the half-point dissent preference or its actor-specific explanation.

> Recent indicators suggest that growth of economic activity moderated in the first half of the year. Job gains have slowed, and the unemployment rate has edged up but remains low. Inflation has moved up and remains somewhat elevated. The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer run. Uncertainty about the economic outlook remains elevated. The Committee is attentive to the risks to both sides of its dual mandate and judges that downside risks to employment have risen. In support of its goals and in light of the shift in the balance of risks, the Committee decided to lower the target range for the federal funds rate by 1/4 percentage point to 4 to 4-1/4 percent. In considering additional adjustments to the target range for the federal funds rate, the Committee will carefully assess incoming data, the evolving outlook, and the balance of risks. The Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage‑backed securities. The Committee is strongly committed to supporting maximum employment and returning inflation to its 2 percent objective. In assessing the appropriate stance of monetary policy, the Committee will continue to monitor the implications of incoming information for the economic outlook. The Committee would be prepared to adjust the stance of monetary policy as appropriate if risks emerge that could impede the attainment of the Committee’s goals. The Committee’s assessments will take into account a wide range of information, including readings on labor market conditions,

### [monetary20250917a1.pdf#p3](../raw/statements/monetary20250917a1.pdf#page=3) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Primary credit rate adjustment is a different action from the dissenting funds-target preference.

> In a related action, the Board of Governors of the Federal Reserve System voted to approve a 1/4 percentage point decrease in the primary credit rate to 4.25 percent, effective September 18, 2025. In taking this action, the Board approved requests to establish that rate submitted by the Boards of Directors of the Federal Reserve Banks of Boston, New York, Philadelphia, Richmond, Atlanta, Chicago, Minneapolis, Kansas City, Dallas, and San Francisco.

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_019 — multi_evidence / mixed

Apply the July 2024 implementation rules recorded in the Statement and Minutes to this hypothetical month: Treasury coupon principal is $20 billion and agency principal is $40 billion; enough Treasury bills mature. How much Treasury-bill principal fills the Treasury redemption cap, how much agency principal is reinvested, and in what securities?

Réponse attendue : The $25bn Treasury cap leaves $5bn to be redeemed from Treasury bills after $20bn coupon principal. Agency principal exceeds the $35bn cap by $5bn, so $5bn is reinvested in Treasury securities to roughly match the maturity composition outstanding. The $20bn and $40bn amounts are hypothetical inputs, not reported realized flows.

Documents demandés : monetary20240731a1.pdf, fomcminutes20240731.pdf

Revue sémantique : The underlying cap is not new information: FOMC_061/115 already ask cap changes, and FOMC_138 repo implementation terms. This task is a new conditional application requiring the coupon/bill fallback and agency reinvestment destination, not another cap lookup. Treat as related, not strongly topic-independent; human validation is required. It requires multiple rules, not necessarily multiple documents because the directive is duplicated.

Anciennes questions liées : FOMC_061, FOMC_115, FOMC_138

### [fomcminutes20240731.pdf#p12](../raw/minutes/fomcminutes20240731.pdf#page=12) — grade proposé 2

Facette : treasury_bill_rule

> • Roll over at auction the amount of principal payments from the Federal Reserve’s holdings of Treasury securities maturing in each calendar month that exceeds a cap of $25 billion per month. Redeem Treasury coupon securities up to this monthly cap and Treasury bills to the extent that coupon principal payments are less than the monthly cap.

Facette : agency_reinvestment_rule

> • Reinvest the amount of principal payments from the Federal Reserve’s holdings of agency debt and agency mortgage-backed securities (MBS) received in each calendar month that exceeds a cap of $35 billion per month into Treasury securities to roughly match the maturity composition of Treasury securities outstanding.

### [monetary20240731a1.pdf#p3](../raw/statements/monetary20240731a1.pdf#page=3) — grade proposé 2

Facette : treasury_bill_rule

> "Effective August 1, 2024, the Federal Open Market Committee directs the Desk to: o Undertake open market operations as necessary to maintain the federal funds rate in a target range of 5-1/4 to 5-1/2 percent. o Conduct standing overnight repurchase agreement operations with a minimum bid rate of 5.5 percent and with an aggregate operation limit of $500 billion. o Conduct standing overnight reverse repurchase agreement operations at an offering rate of 5.3 percent and with a per-counterparty limit of $160 billion per day. o Roll over at auction the amount of principal payments from the Federal Reserve's holdings of Treasury securities maturing in each calendar month that exceeds a cap of $25 billion per month. Redeem Treasury coupon securities up to this monthly cap and Treasury bills to the extent that coupon principal payments are less than the monthly cap. o Reinvest the amount of principal payments from the Federal Reserve's holdings of agency debt and agency mortgage-backed securities (MBS) received in each calendar month that exceeds a cap of $35 billion per month into Treasury securities to roughly match the maturity composition of Treasury securities outstanding. o Allow modest deviations from stated amounts for reinvestments, if needed for operational reasons. o Engage in dollar roll and coupon swap transactions as necessary to facilitate settlement of the Federal Reserve's agency MBS transactions."

Facette : agency_reinvestment_rule

Seconde lecture humaine : **à compléter**.

## HOLDOUT_V2_020 — multi_evidence / mixed

Using the March 2023 Minutes and Statement, distinguish the staff's recession projection from the Committee's public description of banking conditions and their possible economic effects. Was the mild-recession projection explicitly attributed to staff rather than announced as the Statement's own forecast?

Réponse attendue : The Minutes attribute to staff a mild recession later in 2023 and recovery over the following two years. The Statement calls the banking system sound and resilient and says developments are likely to tighten credit and weigh on activity, hiring and inflation, with uncertain extent; it does not explicitly announce a mild-recession forecast. Staff and Committee public language should not be conflated.

Documents demandés : fomcminutes20230322.pdf, monetary20230322a1.pdf

Revue sémantique : The old questions ask credit-contraction channels, September banking descriptions or conditions for policy reconsideration. The novel requirement is attribution of a particular forecast to staff and distinguishing it from the public Statement. The credit-effects component overlaps thematically, so this is disclosed rather than counted as established semantic independence.

Anciennes questions liées : FOMC_049, FOMC_054, FOMC_110

### [fomcminutes20230322.pdf#p6](../raw/minutes/fomcminutes20230322.pdf#page=6) — grade proposé 2

Facette : staff_forecast

> For some time, the forecast for the U.S. economy prepared by the staff had featured subdued real GDP growth for this year and some softening in the labor market. Given their assessment of the potential economic effects of the recent banking-sector developments, the staff’s projection at the time of the March meeting included a mild recession starting later this year, with a recovery over the subsequent two years. Real GDP growth in 2024 was projected to remain below the staff’s estimate of potential output growth, and then GDP growth in 2025 was expected to be above that of potential. Resource utilization in both product and labor markets was forecast to be much less tight than in the January projection. The level of real output was projected to move below the staff’s estimate of potential output in early 2024, more than a year sooner than in the previous projection. Likewise, the unemployment rate was projected to rise above the staff’s estimate of its natural rate early next year.

### [monetary20230322a1.pdf#p1](../raw/statements/monetary20230322a1.pdf#page=1) — grade proposé 2

Facette : public_banking_language

> Recent indicators point to modest growth in spending and production. Job gains have picked up in recent months and are running at a robust pace; the unemployment rate has remained low. Inflation remains elevated. The U.S. banking system is sound and resilient. Recent developments are likely to result in tighter credit conditions for households and businesses and to weigh on economic activity, hiring, and inflation. The extent of these effects is uncertain. The Committee remains highly attentive to inflation risks. The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over the longer run. In support of these goals, the Committee decided to raise the target range for the federal funds rate to 4-3/4 to 5 percent. The Committee will closely monitor incoming information and assess the implications for monetary policy. The Committee anticipates that some additional policy firming may be appropriate in order to attain a stance of monetary policy that is sufficiently restrictive to return inflation to 2 percent over time. In determining the extent of future increases in the target range, the Committee will take into account the cumulative tightening of monetary policy, the lags with which monetary policy affects economic activity and inflation, and economic and financial developments. In addition, the Committee will continue reducing its holdings of Treasury securities and agency debt and agency mortgage-backed securities, as described in its previously announced plans. The Committee is strongly committed to returning inflation to its 2 percent objective.

### [fomcminutes20230322.pdf#p3](../raw/minutes/fomcminutes20230322.pdf#page=3) — grade proposé 0

Facette : editorial_corroboration_or_distractor

Motif du jugement : Barr's supervision/bank review is not the requested staff macro forecast or the Committee's public announcement.

> Credit Suisse. He also described actions taken by the Federal Reserve and other regulatory agencies in response. He noted that the U.S. banking system is sound and resilient. He also noted that he will be leading a re- view of the supervision and regulation of Silicon Valley Bank, and that the Federal Reserve System will apply what is learned from the review to strengthen its supervisory and regulatory practices as appropriate.

### [fomcminutes20230322.pdf#p8](../raw/minutes/fomcminutes20230322.pdf#page=8) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Participants' assessment supports tighter-credit and uncertain-effects context, but not the public/staff attribution itself.

> In their consideration of appropriate monetary policy actions at this meeting, participants concurred that inflation remained well above the Committee’s longer-run goal of 2 percent and that the recent data on inflation provided few signs that inflation pressures were abating at a pace sufficient to return inflation to 2 percent over time. Participants also noted that recent developments in the banking sector would likely result in tighter credit conditions for households and businesses and weigh on economic activity, hiring, and inflation, though the extent of these effects was highly uncertain. Against this backdrop, all participants agreed that it was appropriate to raise the target range for the federal funds rate 25 basis points to 4¾ to 5 percent. All participants also agreed that it was appropriate to continue the process of reducing the Federal Reserve’s securities holdings, as described in its previously announced Plans for Reducing the Size of the Federal Reserve’s Balance Sheet.

### [fomcminutes20230322.pdf#p9](../raw/minutes/fomcminutes20230322.pdf#page=9) — grade proposé 1

Facette : editorial_corroboration_or_distractor

Motif du jugement : Members' assessment corroborates the bank-resilience and credit-effects language.

> In their discussion of monetary policy for this meeting, members agreed that recent indicators pointed to mod- est growth in spending and production. They also concurred that job gains had picked up in recent months and were running at a robust pace, that the unemployment rate had remained low, and that inflation remains elevated. Members concurred that the U.S. banking system is sound and resilient. They also agreed that recent developments were likely to result in tighter credit conditions for households and businesses and to weigh on economic activity, hiring, and inflation, but that the extent of these effects was uncertain. Members also concurred that they remained highly attentive to inflation risks.

### [fomcminutes20230322.pdf#p10](../raw/minutes/fomcminutes20230322.pdf#page=10) — grade proposé 2

Facette : editorial_corroboration_or_distractor

Motif du jugement : Public Statement is directly reproduced in the Minutes, supplying another page supporting the public-language facet.

> The U.S. banking system is sound and resilient. Recent developments are likely to result in tighter credit conditions for households and businesses and to weigh on economic activity, hiring, and inflation. The extent of these effects is uncertain. The Committee remains highly attentive to inflation risks.

Seconde lecture humaine : **à compléter**.
