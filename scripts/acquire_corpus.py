"""Acquire the exact supplied corpus from a local source or official PDF URLs.

Existing mismatching files are never overwritten. Downloaded bytes must match
the versioned manifest; unavailable or changed publications remain explicit errors.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def acquire(manifest, destination, local_source=None, limit=None):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    entries=json.loads(Path(manifest).read_text(encoding='utf-8'))
    if limit: entries=entries[:limit]
    records=[]
    for doc in entries:
        relative=Path(doc['type'])/doc['filename']
        if doc['type'] not in ('minutes','statements') or Path(doc['filename']).name!=doc['filename']:
            raise ValueError('Invalid manifest destination')
        target=destination/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if sha(target)!=doc['sha256']: raise ValueError(f'Existing PDF differs: {target}')
            action='verified_existing'
        elif local_source:
            source=Path(local_source).resolve()/relative
            if sha(source)!=doc['sha256']: raise ValueError(f'Local PDF differs: {source}')
            shutil.copy2(source,target)
            action='imported_verified_local'
        else:
            with urllib.request.urlopen(doc['source_url'],timeout=15) as response:
                content=response.read()
            if not content.startswith(b'%PDF-') or hashlib.sha256(content).hexdigest()!=doc['sha256']:
                raise ValueError(f'Official content unavailable or different: {doc["filename"]}')
            target.write_bytes(content)
            action='downloaded_verified'
        assert sha(target)==doc['sha256']
        records.append(dict(filename=doc['filename'],sha256=doc['sha256'],action=action))
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=ROOT/'data/corpus_manifest.json')
    p.add_argument('--destination',type=Path,default=ROOT/'data/raw')
    p.add_argument('--from-dir',type=Path)
    p.add_argument('--limit',type=int)
    a=p.parse_args()
    records=acquire(a.manifest,a.destination,a.from_dir,a.limit)
    print(f'PASS: {len(records)} PDF avec empreintes identiques ({"source locale" if a.from_dir else "URL officielles ou fichiers présents"}).')


if __name__=='__main__': main()
