"""Replay the exact frozen mutation study into a fresh directory."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = HERE / 'frozen_study'
    target = args.output.resolve()
    if target.exists():
        raise SystemExit('Use a fresh output directory; retained results are never overwritten')
    manifest = json.loads((source / 'freeze.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()):
            raise SystemExit('Frozen path escapes the source directory')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit('Frozen source hash mismatch: ' + name)
    target.mkdir(parents=True)
    shutil.copyfile(source / 'freeze.json', target / 'freeze.json')
    for name in manifest['files']:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, dest)
    command = [sys.executable, str(target / 'frozen/run_mutation.py'), 'run', '--target', str(target)]
    subprocess.run(command, check=True)
    def matrix(path):
        with path.open(encoding='utf-8', newline='') as handle:
            return list(csv.DictReader(handle))
    if matrix(target / 'results/detection_matrix.csv') != matrix(HERE / 'retained/detection_matrix.csv'):
        raise SystemExit('Replay differs from the retained diagnostic matrix; inspect results')
    summary = json.loads((target / 'results/summary.json').read_text(encoding='utf-8'))
    if not (summary['control_all_families_pass'] and summary['detected'] == 11 and summary['survivors'] == ['M01']):
        raise SystemExit('Replay summary differs from retained outcomes')
    print(json.dumps({'matrix_reproduced': True, 'mutants': 12, 'detected': 11, 'survivors': ['M01']}))

if __name__ == '__main__':
    main()
