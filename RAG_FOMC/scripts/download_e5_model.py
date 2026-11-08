"""Secours réseau : téléchargement reprenable par blocs, contrôlé par le SHA256 officiel.

Les seuls échanges distants concernent les fichiers publics du modèle E5 épinglé.
Aucun document du corpus n'est envoyé. Les blocs restent dans .cache/.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.request


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("1 à 8 téléchargements simultanés")
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/default.json").read_text(encoding="utf-8"))
    model, revision = config["model_name"], config["model_revision"]
    if model != "intfloat/e5-small-v2" or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Ce script est réservé à une révision SHA épinglée de E5-small-v2")
    api = f"https://huggingface.co/api/models/{model}/revision/{revision}?blobs=true"
    with urllib.request.urlopen(api, timeout=120) as response:
        metadata = json.load(response)
    artifact = next(f for f in metadata["siblings"] if f["rfilename"] == "model.safetensors")
    size, expected = artifact["lfs"]["size"], artifact["lfs"]["sha256"]
    cache = root / ".cache/huggingface/hub/models--intfloat--e5-small-v2"
    target = cache / "snapshots" / revision / "model.safetensors"
    if target.exists() and target.stat().st_size == size and digest(target) == expected:
        print("Modèle déjà présent et vérifié.", flush=True)
        return
    parts = root / ".cache/e5_verified_parts" / expected
    parts.mkdir(parents=True, exist_ok=True)
    chunk_size = 2 * 1024 * 1024
    count = (size + chunk_size - 1) // chunk_size
    # Récupérer les blocs complets des essais HTTP précédents. Le SHA final les contrôlera.
    existing = sorted((cache / "blobs").glob(expected + ".*.incomplete"),
                      key=lambda p: p.stat().st_size, reverse=True) if (cache / "blobs").exists() else []
    if existing:
        with existing[0].open("rb") as stream:
            for index in range(min(count, existing[0].stat().st_size // chunk_size)):
                data = stream.read(chunk_size)
                destination = parts / f"{index:04d}.part"
                if not destination.exists():
                    destination.write_bytes(data)

    def fetch(index):
        start, end = index * chunk_size, min(size, (index + 1) * chunk_size) - 1
        destination = parts / f"{index:04d}.part"
        expected_length = end - start + 1
        if destination.exists() and destination.stat().st_size == expected_length:
            return index
        url = f"https://huggingface.co/{model}/resolve/{revision}/model.safetensors?download=true&segment={start}"
        last_error = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}":
                        raise ValueError("Le serveur n'a pas honoré la plage demandée")
                    data = response.read(expected_length + 1)
                if len(data) != expected_length:
                    raise ValueError("Bloc incomplet")
                temporary = destination.with_suffix(".tmp")
                temporary.write_bytes(data)
                temporary.replace(destination)
                return index
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Bloc {index} non téléchargé") from last_error

    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch, index) for index in range(count)]
        for future in as_completed(futures):
            future.result()
            completed += 1
            print(f"Blocs vérifiés en longueur : {completed}/{count}", flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".verified-download")
    with temporary.open("wb") as stream:
        for index in range(count):
            stream.write((parts / f"{index:04d}.part").read_bytes())
    if temporary.stat().st_size != size or digest(temporary) != expected:
        raise ValueError("SHA256 final incorrect : modèle non activé, blocs à retélécharger")
    temporary.replace(target)
    print(f"Modèle activé : {size} octets, SHA256 {expected}", flush=True)


if __name__ == "__main__":
    main()
