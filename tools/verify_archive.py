"""Verify imported source bytes against the archive manifest; run from repo root."""
from pathlib import Path
import csv
import hashlib

root = Path(__file__).resolve().parents[1]
checked = 0
errors = []
with (root / '研究分析/资料清单.csv').open(encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        if row['included'] != 'True':
            continue
        path = root / row['path']
        if not path.is_file():
            errors.append(row['path'] + ': missing')
            continue
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if path.stat().st_size != int(row['bytes']) or digest != row['sha256']:
            errors.append(row['path'] + ': checksum mismatch')
        checked += 1
print(f'Checked {checked} archived files; failures: {len(errors)}')
for error in errors:
    print(error)
raise SystemExit(bool(errors))
