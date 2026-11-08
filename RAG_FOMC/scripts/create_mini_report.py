"""Create the phase-one report from frozen results using the installed PDF engine."""
import csv
from pathlib import Path
import pymupdf as fitz

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/mini_rapport_recuperation_FOMC.pdf'
NAVY=(.09,.18,.29); BLUE=(.13,.36,.58); GRAY=(.32,.37,.42)
doc=fitz.open()

def text(page,rect,value,size=10.5,bold=False,color=NAVY):
    value=value.replace('\u2019',"'").replace('\u2018',"'")
    remaining=page.insert_textbox(fitz.Rect(rect),value,fontsize=size,
                                 fontname='hebo' if bold else 'helv',color=color,lineheight=1.35)
    if remaining<0: raise ValueError(f'Text overflow: {value[:65]}')

def page(number,title,subtitle):
    p=doc.new_page(width=595,height=842)
    p.draw_rect(fitz.Rect(0,0,595,10),fill=BLUE,color=BLUE)
    text(p,(40,27,555,45),'RAG FOMC  /  RAPPORT DE FIN DE PREMIÈRE ÉTAPE',9,True,BLUE)
    text(p,(40,62,555,109),title,24,True)
    text(p,(40,113,555,148),subtitle,10.5,color=GRAY)
    p.draw_line((40,790),(555,790),color=(.8,.84,.87))
    text(p,(40,801,505,827),'6 novembre 2026 | Préparation et comparaison de la récupération',8,color=GRAY)
    text(p,(520,801,555,827),f'{number} / 3',8,color=GRAY)
    return p

def block(p,y,title,body,height=82):
    text(p,(40,y,555,y+23),title,12,True,BLUE)
    text(p,(40,y+27,555,y+height),body,10.5)

p=page(1,'Quelle stratégie retenir ?','Conclusion fondée sur le lot test : 145 questions répondables, 20 passages récupérés.')
p.draw_rect(fitz.Rect(40,158,555,236),fill=(.92,.96,.98),color=(.92,.96,.98))
text(p,(53,169,542,192),'BM25 : meilleur choix pour couvrir les preuves attendues.',13,True)
text(p,(53,199,542,231),'L’hybride RRF classe mieux la première preuve en moyenne. Le meilleur choix dépend donc du critère, pas du seul nom de la méthode.',10.5)
with (ROOT/'results/comparison_200_v1/test/summary.csv').open(encoding='utf-8-sig') as f:
    rows={r['method']:r for r in csv.DictReader(f) if r['type']=='ALL'}
xs=[40,186,314,414,555]
headers=['Stratégie','Rappel @20','MRR @20','Preuves complètes']
p.draw_rect(fitz.Rect(40,253,555,286),fill=NAVY,color=NAVY)
for j,h in enumerate(headers): text(p,(xs[j]+8,262,xs[j+1]-4,282),h,9,True,(1,1,1))
for i,(method,label) in enumerate([('bm25','BM25'),('dense','Dense E5'),('hybrid_rrf','Hybride RRF')]):
    r=rows[method]; y=286+i*33
    p.draw_rect(fitz.Rect(40,y,555,y+33),fill=(.96,.97,.98) if i%2==0 else (1,1,1),color=(.87,.89,.91))
    values=[label,f"{float(r['recall']):.1%}".replace('.',','),f"{float(r['mrr']):.3f}".replace('.',','),f"{float(r['all_evidence']):.1%}".replace('.',',')]
    for j,v in enumerate(values): text(p,(xs[j]+8,y+9,xs[j+1]-4,y+31),v,10,bold=i==0)
text(p,(40,398,555,458),'BM25 retrouve tous les groupes de preuves pour 116/145 questions, contre 107/145 pour RRF et 82/145 pour E5. Les moyennes par famille de reformulations conservent la même tendance.',10.5)
p.insert_image(fitz.Rect(38,465,557,679),filename=str(ROOT/'results/comparison_200_v1/test/plots/01_scores_globaux.png'))
text(p,(40,692,555,770),'Lire les indicateurs : le rappel mesure la proportion des chunks annotés retrouvés ; le MRR récompense une première preuve bien placée ; « preuves complètes » exige de retrouver au moins un chunk pour chaque groupe de preuves. Tous ces scores augmentent avec la qualité de récupération.',10)

p=page(2,'Ce qui a été réalisé','Des rapports fournis à un index commun, traçable et reproductible.')
steps=[
('1. Intégrer et sélectionner les données','Import du ZIP ML-RAG-master : 93 PDF conservés (46 comptes rendus et 47 communiqués). Le corpus expérimental utilise 40 comptes rendus FOMC, soit huit réunions par an de 2021 à 2025. Le manifeste relie dates, fichiers et empreintes SHA-256.'),
('2. Extraire et nettoyer le texte','Extraction de 6 080 paragraphes sur 563 pages PDF. Chaque paragraphe conserve document, section, date, page et URL source. Normalisation Unicode NFC et des espaces ; conservation des chiffres, fractions et négations. La tokenisation lexicale ne supprime pas les mots-outils.'),
('3. Découper en passages','Création de 1 454 chunks avec un maximum de 400 tokens de corps et un chevauchement visé de 60 tokens. Le tokenizer E5 contrôle la longueur ; les passages restent reliés à leurs paragraphes et pages afin de vérifier les citations.'),
('4. Vectoriser et construire les index','Utilisation de intfloat/e5-small-v2, version figée : 1 454 vecteurs de 384 dimensions, normalisés. Préfixes « passage: » pour les documents et « query: » pour les questions. En parallèle, index lexical pour BM25, sur exactement les mêmes chunks.'),
('5. Implémenter les trois récupérateurs','BM25 : correspondance lexicale, k1=1,5 et b=0,75. Dense : similarité cosinus exacte avec E5. Hybride RRF : fusion des 20 premiers candidats de chaque branche par leurs rangs, avec constante 60, puis conservation des 20 premiers.'),
('6. Préparer les questions et leurs preuves','200 questions : 80 factuelles, 40 reformulations, 40 explicatives, 30 comparatives et 10 sans réponse. Les 220 groupes de preuves ont été contrôlés dans les chunks et sur 116 pages originales. L’utilisateur a déclaré avoir vérifié le jeu avant les tests.')]
for i,(title,body) in enumerate(steps): block(p,158+i*102,title,body,96)

p=page(3,'Comment la conclusion est établie','Protocole, portée des résultats et état de la première étape.')
block(p,157,'7. Comparer sans changer le terrain de jeu',
      'Même corpus, mêmes chunks, mêmes questions et mêmes paramètres figés pour les trois méthodes. Répartition : 50 questions de développement et 150 de test. Les familles de reformulations et les documents utilisés comme preuves sont séparés entre les lots ; tout le corpus reste dans l’index.',105)
block(p,271,'8. Mesurer, contrôler et visualiser',
      'Trois répétitions, ordre des recherches mélangé et échauffement exclu des durées. Les classements sont restés stables. Scores aux seuils 1, 5, 10 et 20, moyennes par question et par famille, résultats par catégorie et graphiques PNG/SVG. Les 37 tests automatisés passent.',96)
block(p,378,'Ce que les résultats permettent de dire',
      'À 20 passages, BM25 est la référence pour couvrir les preuves sur ce jeu ; RRF est meilleur pour le rang de la première preuve. Les comparaisons entre réunions restent difficiles : preuves complètes pour 12/25 questions avec BM25, 10/25 avec RRF et 5/25 avec E5. Ces résultats ne prouvent pas une supériorité universelle.',100)
block(p,490,'Limites à conserver dans le mémoire',
      'Questions surtout centrées sur taux et chômage ; annotations non garanties exhaustives. Bootstrap exploratoire par famille (1 000 tirages), sans correction multiple ni dépendance entre réunions. Lots exécutés en parallèle : pas de conclusion de vitesse. Les 10 questions sans réponse sont inspectées séparément, sans score d’abstention.',105)
block(p,606,'Bilan et suite du projet',
      'La première étape demandée est achevée : préparation, indexation, récupération et comparaison. Le reranking appris, la génération des réponses, l’abstention et le déploiement restent à réaliser. Les résultats actuels servent de référence avant ces extensions.',86)
text(p,(40,710,555,778),'Traçabilité dans RAG_FOMC : résultats et protocole dans results/comparison_200_v1/ (summary.csv, paired_comparisons.csv, run.json, RAPPORT.md) ; questions dans evaluation/questions.jsonl ; code dans src/rag_fomc/ ; figures dans test/plots/. Aucun résultat n’a été inventé pour ce rapport.',8.8,color=GRAY)

OUT.parent.mkdir(parents=True,exist_ok=True)
doc.set_metadata({'title':'RAG FOMC - Mini-rapport de la première étape','subject':'Comparaison BM25, E5 et RRF','author':'Projet RAG FOMC'})
doc.save(OUT,garbage=4,deflate=True)
doc.close()
temp=ROOT/'tmp/pdfs/mini_rapport'; temp.mkdir(parents=True,exist_ok=True)
with fitz.open(OUT) as check:
    assert len(check)==3
    for i,p in enumerate(check):
        p.get_pixmap(matrix=fitz.Matrix(1.4,1.4)).save(temp/f'page_{i+1}.png')
        assert len(p.get_text())>1000
print(OUT)
