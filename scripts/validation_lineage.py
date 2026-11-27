"""Record module/commit identity without claiming that any test was executed."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    try:
        proc = subprocess.run(['git', '-C', str(ROOT), *args],
            capture_output=True, text=True, check=False)
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Choose a fresh output path')
    reference_path = ROOT / 'validation/reference_modules.json'
    references = json.loads(reference_path.read_text(encoding='utf-8'))
    modules = {p.name:digest(p) for p in sorted((ROOT/'src/radpareto').glob('*.py'))}
    control = ROOT/'benchmarks/mutation/frozen_study/variants/CONTROL/src/radpareto'
    control_hashes = {p.name:digest(p) for p in sorted(control.glob('*.py'))}
    identity = []
    for release in references['releases']:
        compared = {name:modules.get(name)==sha for name,sha in release['modules_sha256'].items()}
        identity.append(dict(version=release['version'],commit=release['commit'],
            module_equal_to_current=compared))
    version = re.search(r'__version__ = "([^"]+)"',
        (ROOT/'src/radpareto/__init__.py').read_text(encoding='utf-8')).group(1)
    status = git('status','--porcelain','--untracked-files=no')
    report = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
        version=version,checkout_commit=git('rev-parse','HEAD'),
        tracked_worktree_clean=None if status is None else not bool(status),
        tracked_worktree_status=status,python=platform.python_version(),
        modules_sha256=modules,reference_modules_file_sha256=digest(reference_path),
        historical_release_identity=identity,frozen_control_modules_sha256=control_hashes,
        frozen_control_equal_to_current={name:modules.get(name)==sha for name,sha in control_hashes.items()},
        scope='Identity evidence only: no test, historical timing transfer, new hardware validation, '
              'or universal correctness is asserted. Use executed run manifests alongside this report.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(version=version,commit=report['checkout_commit'],
        tracked_worktree_clean=report['tracked_worktree_clean'],modules=len(modules))))


if __name__=='__main__':
    main()
