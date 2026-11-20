"""Record the user's explicit global acceptance; never infer semantic adjudication."""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from common import digest, write_json
from protocol import verify


def main():
    verify()
    base = ROOT/'data/holdout_candidate/assistant_review/completed_proposal'
    path = base/'human_review.csv'
    record = base/'user_approval.json'
    if record.exists():
        print('Validation déjà enregistrée ; aucune écriture supplémentaire.')
        return
    original = path.read_bytes()
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)
    assert len(rows)==294 and all(r['proposed_grade'] in ('0','1','2') for r in rows)
    if any(r['human_grade'].strip() or r['reviewer'].strip() for r in rows):
        raise ValueError('Des jugements existent déjà : ne pas les remplacer par une validation globale.')
    archive = base/'human_review_before_user_approval.csv'
    if archive.exists(): raise ValueError('Sauvegarde déjà présente ; contrôler avant reprise.')
    archive.write_bytes(original)
    for row in rows:
        row['human_grade'] = row['proposed_grade']
        row['reviewer'] = 'Utilisateur du projet — accord explicite dans la conversation'
        row['annotation_status'] = 'user_accepted_assistant_proposal_global'
        row['notes'] = ('Validation globale explicite : « concernant la validation humanie,je valide donc revois ! ». '
            'Acceptation du grade proposé ; aucune déclaration de lecture indépendante page par page '
            'ni de comparaison sémantique des 145 questions n’est déduite de cet accord.')
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text,fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    path.write_text(text.getvalue(),encoding='utf-8-sig',newline='')
    write_json(record,dict(status='user_global_acceptance_recorded',
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        user_statement='concernant la validation humanie,je valide donc revois !',
        acceptance_scope='All 294 proposed page grades accepted globally by project user',
        accepted_page_grades=294,grade_changes=0,
        independent_page_by_page_reading_attested=False,
        semantic_comparison_against_145_attested=False,
        answer_and_facet_adjudication_attested=False,
        final_independent_test=False,
        proposed_qrels_sha256=digest(base/'qrels_PAGES_proposed.trec'),
        original_grid_sha256=digest(archive),accepted_grid_sha256=digest(path)))
    print('294 grades acceptés par validation globale explicite ; décisions sémantiques préservées.')
    verify()


if __name__=='__main__': main()
