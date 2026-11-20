"""Exécuter les six étapes du projet dans un seul processus Python."""
import argparse
import importlib
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from common import log

STEPS=('chunk','align_references','build_indexes','retrieve','rerank','evaluate','audit_project')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-step',choices=STEPS,default='chunk')
    parser.add_argument('--to-step',choices=STEPS,default='audit_project')
    args=parser.parse_args()
    first,last=STEPS.index(args.from_step),STEPS.index(args.to_step)
    if first>last: parser.error('Ordre des étapes invalide')
    for step in STEPS[first:last+1]:
        started=time.perf_counter(); log(f'ÉTAPE : {step}')
        module=importlib.import_module(step)
        if step=='build_indexes': module.build()
        else: module.main()
        log(f'Étape {step} terminée en {time.perf_counter()-started:.1f} s')

if __name__=='__main__': main()
