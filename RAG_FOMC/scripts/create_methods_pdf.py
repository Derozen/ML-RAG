"""Build a detailed methodology PDF with ReportLab (bundled authoring Python)."""
from pathlib import Path
import csv
import json
import math
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/methodologies_BM25_E5_RRF_FOMC.pdf'
FONT=Path('C:/Windows/Fonts')
for name,file in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Code','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial',boldItalic='Arial-Bold')
NAVY=colors.HexColor('#152e48'); BLUE=colors.HexColor('#245f96'); TEAL=colors.HexColor('#177e6c')
MUTED=colors.HexColor('#526374'); LIGHT=colors.HexColor('#edf4f9'); GRID=colors.HexColor('#d7e1e9')
WIDTH=A4[0]-88
styles={
 'title':ParagraphStyle('title',fontName='Arial-Bold',fontSize=24,leading=29,textColor=NAVY,spaceAfter=9),
 'sub':ParagraphStyle('sub',fontName='Arial',fontSize=10.4,leading=14.4,textColor=MUTED,spaceAfter=15),
 'h':ParagraphStyle('h',fontName='Arial-Bold',fontSize=12,leading=16,textColor=BLUE,spaceBefore=12,spaceAfter=6),
 'body':ParagraphStyle('body',fontName='Arial',fontSize=10.4,leading=14.8,textColor=NAVY,spaceAfter=8),
 'small':ParagraphStyle('small',fontName='Arial',fontSize=8.8,leading=12,textColor=MUTED,spaceAfter=6),
 'cell':ParagraphStyle('cell',fontName='Arial',fontSize=9.1,leading=12.2,textColor=NAVY),
 'head':ParagraphStyle('head',fontName='Arial-Bold',fontSize=9.1,leading=12,textColor=colors.white),
 'eq':ParagraphStyle('eq',fontName='Arial',fontSize=11,leading=16,textColor=NAVY,alignment=TA_CENTER),
 'code':ParagraphStyle('code',fontName='Code',fontSize=8.5,leading=12,textColor=NAVY,spaceAfter=6),
}
story=[]
def p(s,kind='body'): return Paragraph(s,styles[kind])
def add(s,kind='body'): story.append(p(s,kind))
def h(s): add(s,'h')
def start(title,subtitle):
    if story: story.append(PageBreak())
    add(title,'title'); add(subtitle,'sub')
def note(title,body):
    t=Table([[p(title,'h')],[p(body)]],colWidths=[WIDTH-24])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.5,GRID),
                          ('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),
                          ('TOPPADDING',(0,0),(-1,0),1),('BOTTOMPADDING',(0,-1),(-1,-1),7)]))
    story.append(t); story.append(Spacer(1,7))
def eq(s):
    t=Table([[p(s,'eq')]],colWidths=[WIDTH])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIGHT),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    story.append(t); story.append(Spacer(1,8))
def table(headers,rows,widths):
    data=[[p(escape(str(s)),'head') for s in headers]]+[[p(escape(str(s)),'cell') for s in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f4f7fa')]),
                          ('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,GRID),
                          ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                          ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.append(t); story.append(Spacer(1,8))
def code(s):
    add(escape(s).replace('\n','<br/>').replace(' ','&nbsp;'),'code')

# 1
start('Méthodologies de récupération','Projet RAG FOMC | BM25, Dense E5 et Hybride RRF | 8 novembre 2026')
note('Le rôle de ces trois méthodes',
     'À partir d’une question, produire une liste ordonnée de passages susceptibles de contenir la réponse. '
     'Le résultat est une sélection de textes sources, pas encore une réponse rédigée par un modèle de langage.')
h('1. Un socle de données commun')
add('L’expérience porte sur <b>40 comptes rendus FOMC de 2021 à 2025</b>, huit réunions par année. '
    'L’extraction représente 563 pages et 6 080 paragraphes. Le découpage produit <b>1 454 passages</b>, '
    'avec au maximum 400 tokens de corps et un chevauchement visé de 60 tokens, sans traverser les documents ou les sections.')
add('Chaque passage conserve son identifiant, la réunion, la section, les paragraphes et les pages sources. '
    'Le texte recherché, nommé <b>search_text</b>, comprend la date de réunion et la section, suivies du texte du passage. '
    'Ce même champ est utilisé pour les représentations BM25 et E5. [C1]')
h('2. Les mots à distinguer')
table(['Terme','Signification'],[
 ('Document','Le compte rendu PDF complet.'),('Passage / chunk','Une portion du document effectivement classée par les moteurs.'),
 ('Preuve','Une information source qui justifie une réponse ; plusieurs passages peuvent apporter la même preuve.'),
 ('K / top-k','Nombre de passages finalement conservés ; K = 20 dans la comparaison.'),
 ('Score / rang','Le score sert au tri ; le rang 1 désigne le premier résultat. Un score n’est pas une probabilité de réponse correcte.')],[112,WIDTH-112])
h('3. Vue d’ensemble du traitement')
add('<b>Rapports → extraction et nettoyage → découpage → représentations lexicales/vectorielles → '
    'question → recherche BM25 et/ou E5 → éventuellement fusion RRF → passages classés.</b>')
add('Le reranking appris, la génération d’une réponse et la décision de s’abstenir sont des composants distincts. '
    'Aucune des trois méthodes décrites ici ne les implémente à elle seule. Les exemples numériques des pages suivantes sont pédagogiques, sans valeur de résultat FOMC.','small')

# 2
start('BM25 : procédure de recherche','Méthode lexicale | Principe : des termes informatifs partagés rendent un passage pertinent.')
h('1. Préparer la représentation des passages')
add('Le nettoyage normalise Unicode en NFC et les espaces, tout en conservant les chiffres, fractions et négations. '
    'La fonction <b>lexical_tokens()</b> met le texte en minuscules et extrait les termes et formes numériques. '
    'Elle ne supprime pas les mots-outils et n’applique ni racinisation ni lemmatisation. [C1]')
add('La bibliothèque <b>rank-bm25 0.2.2</b> reçoit ces listes de tokens. Elle calcule les occurrences de chaque terme '
    'dans chaque passage, le nombre de passages qui le contiennent et la longueur moyenne des passages. '
    'Il s’agit de statistiques de la collection, pas d’un entraînement sur les réponses aux questions.')
h('2. Traiter une nouvelle question')
add('<b>Étape 1.</b> Découper la question avec exactement la même fonction lexicale que les documents.<br/>'
    '<b>Étape 2.</b> Pour chaque terme de la question, calculer sa contribution dans chacun des 1 454 passages.<br/>'
    '<b>Étape 3.</b> Additionner les contributions afin d’obtenir un score BM25 par passage.<br/>'
    '<b>Étape 4.</b> Trier les scores par ordre décroissant et conserver les 20 premiers passages.<br/>'
    '<b>Étape 5.</b> Joindre aux résultats les identifiants, le texte, les dates, sections et sources.')
h('3. Pourquoi trois facteurs interviennent')
table(['Facteur','Interprétation'],[
 ('Rareté du terme (IDF)','Un terme présent dans peu de passages est généralement plus discriminant qu’un terme très courant.'),
 ('Fréquence locale','Un terme répété dans un passage contribue davantage, mais avec saturation : doubler les occurrences ne double pas nécessairement le score.'),
 ('Longueur du passage','La normalisation limite l’avantage qu’aurait un texte long contenant mécaniquement davantage de mots.')],[132,WIDTH-132])
note('Exemple de rapprochement lexical',
     'Question illustrative : « What unemployment rate was reported in February? » Un passage contenant '
     '« unemployment rate » et « February » peut recevoir des contributions sur plusieurs termes. '
     'La présence de ces mots ne prouve toutefois ni que le chiffre est le bon, ni que la bonne réunion a été retrouvée.')
add('Implémentation : <b>Retriever._bm25()</b> dans src/rag_fomc/retrieval.py. La bibliothèque calcule les scores sur toute la collection ; '
    'le projet ne met pas en œuvre ici un moteur à index inversé optimisé pour de très grandes collections. [C1, R1]','small')

# 3
start('BM25 : formule et exemple','Paramètres effectifs : k1 = 1,5 ; b = 0,75 ; epsilon = 0,25 (défaut de la bibliothèque).')
eq('BM25(q, d) = Σ<sub>t dans q</sub> IDF(t) × '
   '[ f(t,d) × (k1 + 1) ] / [ f(t,d) + k1 × (1 - b + b × |d| / avgdl) ]')
add('<b>q</b> : question ; <b>d</b> : passage ; <b>f(t,d)</b> : nombre d’occurrences du terme t dans d ; '
    '<b>|d|</b> : longueur en tokens lexicaux ; <b>avgdl</b> : longueur lexicale moyenne. '
    'La somme suit les tokens de la question : répéter un terme peut répéter sa contribution dans cette implémentation. '
    'Ces longueurs lexicales incluent les métadonnées et ne sont pas les tokens du tokenizer E5.')
add('<b>k1</b> contrôle la saturation de la fréquence. <b>b = 0</b> désactive la normalisation de longueur ; '
    '<b>b = 1</b> applique la correction de longueur complète de cette formule. Les valeurs actuelles sont des choix de baseline, pas des optimums démontrés.')
h('L’IDF réellement utilisée')
eq('IDF<sub>0</sub>(t) = ln[ (N - df(t) + 0,5) / (df(t) + 0,5) ]')
add('<b>N</b> est le nombre de passages et <b>df(t)</b> le nombre de passages contenant t. '
    'Dans BM25Okapi, une IDF initiale négative est remplacée par <b>epsilon × moyenne des IDF initiales</b>. '
    'Un terme absent du vocabulaire ne contribue pas au score. Cette variante est celle du paquet installé ; '
    'elle diffère des présentations utilisant ln(1 + …). [R1]')
h('Calcul pédagogique : un seul terme')
add('Collection fictive : N = 100, df = 5 et avgdl = 100. Alors IDF = ln(95,5 / 5,5) ≈ 2,854. '
    'Avec les paramètres du projet, on obtient :')
idf=math.log(95.5/5.5)
def bm(tf,length): return idf*tf*2.5/(tf+1.5*(.25+.75*length/100))
table(['Passage fictif','Occurrences','Longueur','Score BM25'],[
 ('A',2,100,f'{bm(2,100):.3f}'),('B',2,200,f'{bm(2,200):.3f}'),('C',5,100,f'{bm(5,100):.3f}')],[145,100,100,WIDTH-345])
add('À fréquence identique, A dépasse B car il est plus court. À longueur identique, C dépasse A, '
    'mais passer de 2 à 5 occurrences n’a pas multiplié le score par 2,5. Le classement de cet exemple est C, A, B.')
add('Limites : synonymes non explicitement rapprochés, correspondances numériques parfois trompeuses, poids possible des métadonnées. '
    'En cas d’absence totale de termes communs, le moteur peut quand même retourner des passages à score égal ; un diagnostic est enregistré, sans abstention automatique.','small')

# 4
start('Dense E5 : préparer les vecteurs','Méthode sémantique | Une représentation numérique apprise remplace la seule correspondance des mots.')
h('1. Le modèle effectivement utilisé')
add('Le projet charge <b>intfloat/e5-small-v2</b>, avec la révision figée suivante :')
code('ffb93f3bd4047442299a41ebb6fa998a38507c52')
add('Ce modèle produit un vecteur de <b>384 dimensions</b>. Ses poids sont déjà appris à l’extérieur du projet. '
    '<b>Aucun fine-tuning sur les rapports FOMC n’a été réalisé.</b> Les données et questions du projet servent ici à l’indexation et à l’évaluation. [C1, R2]')
h('2. Préparer chaque entrée documentaire')
code('passage: Meeting ending ... | Section ...\nTexte du passage ...')
add('Le préfixe <b>passage:</b> indique le rôle documentaire. Le tokenizer du modèle convertit le texte en sous-unités, '
    'différentes des tokens lexicaux BM25. Le contrôle de longueur inclut préfixe, métadonnées et tokens spéciaux. '
    'Le projet vérifie la limite effective, au plus 512 tokens, et refuse une entrée trop longue plutôt que de la tronquer silencieusement.')
h('3. Transformer le texte en embedding')
add('Le réseau calcule des représentations contextualisées des tokens. La configuration locale utilise un '
    '<b>pooling moyen</b> : les représentations sont agrégées en un vecteur de passage, en tenant compte du masque des tokens valides. '
    'Les 384 coordonnées ne sont pas des variables manuellement nommées, comme « inflation » ou « chômage ». [C1, R2]')
eq('v = Encodeur("passage: " + search_text)<br/>v̂ = v / ||v||<sub>2</sub>')
add('La normalisation L2 fixe la norme du vecteur à 1. Les valeurs sont enregistrées en <b>float32</b>, '
    'dans une matrice de forme <b>1 454 × 384</b>. Les identifiants sont conservés dans le même ordre canonique pour éviter toute confusion entre un vecteur et son texte.')
note('Ce qui est calculé une fois',
     'Les embeddings documentaires sont préparés à l’indexation puis réutilisés. '
     'À chaque question, on recalcule seulement son embedding, avant de le comparer aux vecteurs stockés. '
     'La version du modèle, l’alignement des IDs et les empreintes sont vérifiés au chargement.')
add('Fichiers : encoding.py (encodeur), indexing.py (construction et intégrité), indexes/vectors.npy '
    '(vecteurs), indexes/chunk_ids.json (ordre des passages).','small')

# 5
start('Dense E5 : rechercher et classer','La comparaison utilise la direction des vecteurs, par similarité cosinus.')
h('1. Transformer la question')
add('La question est transmise au même modèle, avec le préfixe <b>query:</b>, puis normalisée en L2. '
    'Le préfixe de rôle est important : le projet n’utilise pas passage: pour la question. '
    'Le corpus et le jeu évalué sont en anglais ; la fiche de ce modèle indique un usage anglais. '
    'Les performances sur une question française ne sont pas établies par notre expérience. [R2]')
eq('û = Encodeur("query: " + question) / ||Encodeur("query: " + question)||<sub>2</sub><br/>'
   'sim(q,d) = (u · v) / (||u||<sub>2</sub> × ||v||<sub>2</sub>) = û · v̂')
h('2. Calculer les similarités exactes')
add('Le code effectue le produit matrice-vecteur <b>vectors @ query</b>. Tous les 1 454 passages sont évalués ; '
    'aucune recherche approximative de type ANN n’est utilisée ici. Les scores sont triés par ordre décroissant et les '
    '20 premiers passages sont conservés. À scores égaux, l’ordre canonique des passages stabilise le résultat.')
h('3. Exemple géométrique simplifié')
add('Pour visualiser le calcul, supposons des vecteurs fictifs à <b>deux dimensions</b>, déjà de norme 1 : '
    'question u = (1 ; 0), A = (0,8 ; 0,6), B = (0,6 ; 0,8), C = (0 ; 1). '
    'Le vrai modèle utilise 384 dimensions ; ces coordonnées ne sont pas des sorties FOMC.')
table(['Passage fictif','Produit scalaire avec u','Rang'],[
 ('A','1 × 0,8 + 0 × 0,6 = 0,8','1'),('B','1 × 0,6 + 0 × 0,8 = 0,6','2'),('C','1 × 0 + 0 × 1 = 0','3')],[135,WIDTH-205,70])
h('4. Intérêt et limites')
add('E5 peut rapprocher « difficulty hiring workers » et « trouble recruiting staff » même si plusieurs mots diffèrent. '
    'Ce comportement potentiel vient de la représentation apprise, et non d’un dictionnaire de synonymes ajouté par le projet.')
add('Une proximité sémantique ne garantit toutefois ni la bonne réunion, ni la bonne valeur, ni la preuve complète. '
    'Un passage parlant du même sujet mais d’une autre période peut être bien classé. Le cosinus n’est pas une probabilité '
    'de réponse correcte ; un seuil de rejet devrait être calibré et évalué séparément.')
add('Implémentation : Retriever._dense() dans retrieval.py. Le temps de recherche inclut l’encodage de la question ; '
    'l’indexation des documents et le chargement initial du modèle sont des coûts distincts.','small')

# 6
start('Hybride RRF : fusion des rangs','Méthode hybride | Combiner deux recherches sans additionner leurs scores bruts.')
h('1. Pourquoi une fusion ?')
add('BM25 peut être utile pour les termes précis ; E5 peut rapprocher certaines formulations différentes. '
    'L’hybride cherche à exploiter cette complémentarité. Les scores BM25 et cosinus n’ont pas la même échelle : '
    'une addition brute imposerait une calibration. <b>RRF utilise uniquement les positions dans les listes.</b> [R3]')
h('2. Procédure réellement exécutée')
add('<b>Étape 1.</b> Exécuter BM25 et conserver ses 20 premiers candidats.<br/>'
    '<b>Étape 2.</b> Exécuter E5 et conserver ses 20 premiers candidats.<br/>'
    '<b>Étape 3.</b> Former l’union des identifiants, au plus 40 candidats distincts.<br/>'
    '<b>Étape 4.</b> Ajouter pour chaque passage sa contribution de rang dans chaque liste où il apparaît.<br/>'
    '<b>Étape 5.</b> Trier les scores RRF et retourner les 20 premiers passages distincts.')
eq('RRF(d) = Σ<sub>m où d est présent</sub> 1 / (c + r<sub>m</sub>(d))<br/>c = 60 ; r<sub>m</sub>(d) commence à 1')
add('<b>r<sub>m</sub>(d)</b> est le rang du passage d pour la méthode m. '
    'Une absence des 20 premiers résultats d’une branche apporte <b>zéro contribution</b>. '
    'Les deux branches ont le même poids ; il n’y a pas de coefficient appris dans la fusion actuelle.')
note('Ne pas confondre les paramètres',
     '<b>c = 60</b> adoucit les différences de rang. <b>K = 20</b> est le nombre final de passages. '
     'Dans le code actuel, K fixe aussi la profondeur de chaque branche. Ces deux profondeurs pourraient être '
     'dissociées dans une future variante, mais ce n’est pas l’expérience évaluée ici.')
h('3. Propriétés d’implémentation')
add('Les branches sont appelées successivement par <b>search()</b> ; la durée hybride comprend les deux recherches et la fusion. '
    'Un ID ne compte qu’une fois dans chaque branche. Les égalités finales sont départagées par l’index canonique du passage. '
    'La déduplication concerne les IDs : deux chunks différents portant une information semblable peuvent rester tous deux dans le résultat.')
add('RRF n’est pas un reranker neuronal : il ne relit pas le couple question/passage avec un nouveau modèle. '
    'Il agrège deux classements déjà obtenus. Implémentation : reciprocal_rank_fusion() et search() dans retrieval.py. [C1]','small')

# 7
start('RRF : exemple numérique complet','Illustration fictive à trois candidats par branche ; les véritables listes ont une profondeur de 20.')
table(['Rang','Liste BM25','Liste E5'],[(1,'A','B'),(2,'B','D'),(3,'C','A')],[70,(WIDTH-70)/2,(WIDTH-70)/2])
add('Le passage B est deuxième pour BM25 et premier pour E5. A est premier pour BM25 et troisième pour E5. '
    'C et D ne figurent chacun que dans une seule liste. Avec c = 60 :')
table(['Passage','Calcul','Score RRF','Rang final'],[
 ('B','1/62 + 1/61',f'{1/62+1/61:.6f}','1'),
 ('A','1/61 + 1/63',f'{1/61+1/63:.6f}','2'),
 ('D','1/62',f'{1/62:.6f}','3'),('C','1/63',f'{1/63:.6f}','4')],[65,190,125,WIDTH-380])
add('<b>La fusion place donc B devant A</b>, bien que BM25 ait classé A premier. '
    'L’accord des deux méthodes favorise B. Le score de pertinence brut produit par BM25 ou E5 n’intervient pas dans ce calcul.')
h('Effet important de la configuration actuelle')
add('Avec deux listes de 20 passages et c = 60, un candidat présent dans les deux listes reçoit au minimum '
    '<b>2/(60 + 20) = 0,025</b>. Un candidat présent dans une seule liste reçoit au maximum '
    '<b>1/(60 + 1) ≈ 0,01639</b>.')
note('Conséquence exacte, pas une hypothèse',
     'Dans cette configuration, <b>tout candidat commun aux deux listes passe devant tout candidat présent dans une seule liste</b>. '
     'Cela renforce fortement les accords. Cela peut aussi reléguer une preuve pertinente trouvée seulement par BM25 ou seulement par E5. '
     'L’accord ne constitue donc pas une garantie de pertinence.')
h('Ce que la fusion ne peut pas faire')
add('Si une preuve est absente des deux listes d’entrée, RRF ne peut pas l’inventer ni la récupérer. '
    'Une liste finale de 20 éléments peut aussi omettre un candidat pourtant présent dans l’union de 40 éléments. '
    'Enfin, une bonne position de la première preuve n’assure pas que les deux réunions nécessaires à une comparaison sont représentées.')
add('Modifier c ou la profondeur des branches constitue une nouvelle configuration à régler sur développement. '
    'Ces paramètres ne doivent pas être choisis pour améliorer rétrospectivement les scores du test déjà observé.','small')

# 8
start('Comparer les trois méthodologies','La pertinence se juge par rapport à la question et aux preuves, pas à la grandeur des scores bruts.')
table(['Aspect','BM25','Dense E5','Hybride RRF'],[
 ('Signal utilisé','Correspondances lexicales','Proximité des embeddings','Positions dans les deux listes'),
 ('Préparation','Tokens et statistiques du corpus','Embeddings des passages','Les deux préparations'),
 ('À la question','Tokenisation et scores lexicaux','Embedding puis cosinus','BM25 + E5 + fusion'),
 ('Apprentissage FOMC','Aucun','Aucun fine-tuning','Aucun poids de fusion appris'),
 ('Atout potentiel','Termes, chiffres et dates explicites','Formulations différentes mais proches','Complémentarité et accords'),
 ('Risque typique','Vocabulaire différent ou faux rapprochement lexical','Bon sujet, mauvaise période ou valeur','Preuve unique à une branche reléguée')],[98,130,137,WIDTH-365])
h('Conditions constantes de l’expérience')
add('Les trois méthodes partagent le corpus, les chunks, les métadonnées, les questions et le nombre final de candidats. '
    'Les dates issues du corrigé ne filtrent pas les documents pendant la recherche. Une question comparative doit donc '
    'faire émerger ses deux réunions dans une seule liste de résultats.')
add('Les métadonnées de réunion sont un signal commun utile mais peuvent influencer les classements. '
    'Une analyse d’ablation avec/sans métadonnées serait une expérience supplémentaire, non réalisée dans cette baseline. '
    'L’index exact E5 évite ici de mélanger erreur du modèle et erreur d’un algorithme de voisinage approximatif.')
h('Deux opérations à ne pas confondre')
add('<b>Récupération :</b> produire une liste de candidats à partir de la collection.<br/>'
    '<b>Reranking appris :</b> réévaluer les candidats avec un modèle dédié, souvent en examinant la question et le passage ensemble. '
    'Ce composant n’est pas encore implémenté. Il ne pourrait pas sauver une preuve absente de sa liste d’entrée.')
note('Pas de preuve par simple score élevé',
     'Un passage est une preuve s’il justifie effectivement la réponse, avec la bonne date, la bonne variable et les bons qualificatifs. '
     'Les variantes d’une même information forment un seul groupe ; deux informations complémentaires forment deux groupes nécessaires.')

# 9
start('Protocole d’évaluation et portée','Même méthode de mesure pour les trois stratégies ; distinction explicite entre annotations v1 et révision v2.')
add('Le jeu contient <b>200 questions</b> : 80 factuelles, 40 reformulations, 40 explicatives, 30 comparatives et 10 sans réponse. '
    'Il est partagé en 50 questions dev et 150 test. Les familles restent dans un seul lot et les documents utilisés comme preuves sont disjoints entre lots ; '
    'la collection entière reste cependant recherchable. Aucune optimisation systématique des hyperparamètres n’a encore été menée.')
table(['Mesure à K','Ce qui est mesuré'],[
 ('Recall','Fraction des chunks annotés acceptables retrouvés, puis moyenne par question.'),
 ('MRR','Moyenne de 1/rang de la première preuve ; 0 si aucune preuve dans les K premiers.'),
 ('Couverture','Fraction des groupes de preuves dont au moins une variante est retrouvée.'),
 ('Complétude','1 si tous les groupes nécessaires sont couverts ; sinon 0. La moyenne est une proportion de questions.')],[100,WIDTH-100])
add('Le benchmark initial a trois répétitions, un échauffement exclu des durées et des ordres de recherche mélangés. '
    'Les classements sont stables. Les répétitions ne multiplient pas le nombre de questions indépendantes. '
    'Les durées initiales des lots concurrents ne permettent pas de conclure sur la rapidité relative.')
with (ROOT/'results/comparison_200_v2_rescored/test/summary.csv').open(encoding='utf-8-sig',newline='') as f:
    results={r['method']:r for r in csv.DictReader(f) if r['type']=='ALL'}
h('Repère actuel : test de 145 questions répondables')
table(['Méthode','Recall@20','MRR@20','Complétude@20'],[
 (label,f"{float(results[m]['recall']):.3f}",f"{float(results[m]['mrr']):.3f}",f"{float(results[m]['all_evidence']):.1%}")
 for m,label in [('bm25','BM25'),('dense','Dense E5'),('hybrid_rrf','Hybride RRF')]],[130,110,110,WIDTH-350])
add('<b>Statut : analyse exploratoire v2.</b> Les ajouts de preuves ont été relus par l’assistant et contrôlés dans les PDF, '
    'mais attendent une validation indépendante. Les classements v1 ont été réutilisés sans modifier les moteurs. '
    'BM25 couvre le mieux les preuves annotées à K=20 ; RRF obtient le meilleur MRR dans cette configuration.')
add('Les annotations ne sont pas garanties exhaustives ; le rappel peut baisser lorsque l’on ajoute des variantes acceptées à son dénominateur. '
    'Les questions sans réponse sont exclues de ces scores : pas de règle d’abstention évaluée. '
    'Les intervalles bootstrap par famille restent exploratoires et ne couvrent pas toute la dépendance documentaire. '
    'Le test ayant été observé, une future optimisation nécessitera une confirmation indépendante. [C2]','small')

# 10
start('Retrouver le code et les références','Le document décrit le code du projet et les paramètres de l’index, plutôt qu’une variante théorique différente.')
table(['Fichier dans RAG_FOMC','Rôle'],[
 ('src/rag_fomc/preprocessing.py','Nettoyage conservateur et tokens lexicaux.'),
 ('src/rag_fomc/chunking.py','Découpage et ajout des métadonnées de recherche.'),
 ('src/rag_fomc/encoding.py','Chargement E5, préfixes, longueur et normalisation.'),
 ('src/rag_fomc/indexing.py','Vecteurs, tokens, alignement et empreintes.'),
 ('src/rag_fomc/retrieval.py','BM25, cosinus exact, RRF et tri stable.'),
 ('src/rag_fomc/evaluation.py','Validation des annotations et calcul des métriques.'),
 ('indexes/metadata.json','Configuration réellement attachée à l’index utilisé.'),
 ('scripts/plot_comparison.py','Figures produites à partir des résultats enregistrés.')],[260,WIDTH-260])
h('Exécution d’une nouvelle comparaison avec les annotations validées v1')
code('cd C:\\Users\\LENOVO\\Desktop\\VS_Codex\\RAG_FOMC\n$env:HF_HUB_OFFLINE = "1"\n.\\.venv\\Scripts\\python.exe run.py compare --split test `\n    --output results/ma_comparaison_methodes/test')
add('Choisir un nouveau dossier de sortie. Le modèle est déjà en cache sur ce poste. '
    'Le résultat détaillé est dans summary.csv, metrics_per_question.csv, rankings.jsonl et run.json. '
    'Cette commande utilise le fichier humainement validé v1 ; elle ne promeut pas les annotations v2 provisoires.','small')
h('Sources du projet')
add('<b>[C1]</b> Code local et indexes/metadata.json ; paquet installé rank-bm25 0.2.2 ; '
    'configuration locale E5 1_Pooling/config.json (pooling moyen).<br/>'
    '<b>[C2]</b> results/comparison_200_v2_rescored/test/summary.csv ; evaluation/revision_v2/README.md ; '
    'docs/REVUE_METHODOLOGIQUE_COURS_ECC.md. Les résultats v2 restent provisoires.','small')
h('Sources techniques primaires consultées')
add('<b>[R1]</b> Dorian Brown, code source de rank_bm25, classe BM25Okapi. Le paquet installé fait foi pour la variante utilisée.<br/>'
    '<link href="https://github.com/dorianbrown/rank_bm25/blob/master/rank_bm25.py" color="#245f96">github.com/dorianbrown/rank_bm25/blob/master/rank_bm25.py</link><br/>'
    '<b>[R2]</b> intfloat, fiche officielle du modèle e5-small-v2 : dimensions, préfixes, normalisation et limites.<br/>'
    '<link href="https://huggingface.co/intfloat/e5-small-v2" color="#245f96">huggingface.co/intfloat/e5-small-v2</link><br/>'
    '<b>[R3]</b> Cormack, Clarke et Büttcher, « Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods », SIGIR 2009, p. 758-759.<br/>'
    '<link href="https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf" color="#245f96">cormack.uwaterloo.ca/cormacksigir09-rrf.pdf</link>','small')

def footer(canvas,document):
    canvas.saveState(); w,height=A4
    canvas.setFillColor(BLUE); canvas.rect(0,height-8,w,8,stroke=0,fill=1)
    canvas.setFont('Arial-Bold',8); canvas.setFillColor(BLUE)
    canvas.drawString(44,height-30,'RAG FOMC / MÉTHODOLOGIES DE RÉCUPÉRATION')
    canvas.setStrokeColor(GRID); canvas.line(44,43,w-44,43)
    canvas.setFont('Arial',8); canvas.setFillColor(MUTED)
    canvas.drawString(44,29,'BM25 · Dense E5 · Hybride RRF | 8 novembre 2026')
    canvas.drawRightString(w-44,29,f'{document.page} / 10'); canvas.restoreState()

OUT.parent.mkdir(parents=True,exist_ok=True)
document=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=52,bottomMargin=58,
                           title='Méthodologies détaillées : BM25, Dense E5 et Hybride RRF',author='Projet RAG FOMC')
document.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
