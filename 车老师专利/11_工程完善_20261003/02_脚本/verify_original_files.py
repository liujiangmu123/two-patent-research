import hashlib
import json
from pathlib import Path
root=Path('.').resolve()
base=root/'车老师专利/11_工程完善_20261003'
records=json.loads((base/'00_设计基准/原始文件基线.json').read_text(encoding='utf-8'))
changed=[];missing=[]
for row in records:
    path=root/row['path']
    if not path.exists():missing.append(row['path']);continue
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual!=row['sha256']:changed.append({'file':row['path'],'expected':row['sha256'],'actual':actual})
report={'checked':len(records),'changed':changed,'missing':missing,'scope':'176 registered original engineering files; not a claim about every historical file'}
(base/'04_检查/原始文件基线复核.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
