import hashlib
import json
import ssl
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

import certifi

root = Path('车老师专利/11_工程完善_20261003')
out = root / '01_厂家依据/Wandfluh'
out.mkdir(parents=True, exist_ok=True)
context = ssl.create_default_context(cafile=certifi.where())
page = 'https://www.wandfluh.com/en/products/valves/sdspm22/'
html = urllib.request.urlopen(page, context=context, timeout=30).read().decode('utf-8')

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'a' and data.get('href'):
            self.links.append(urllib.parse.urljoin(page, data['href']))

parser = Links()
parser.feed(html)
urls = [u for u in parser.links if any(s in u.lower() for s in ('1_11_2061_e.pdf', '2_13_1008_e.pdf', 'stp_1.11-2061.zip'))]
records = []
for url in dict.fromkeys(urls):
    data = urllib.request.urlopen(url, context=context, timeout=30).read()
    name = urllib.parse.unquote(url.rsplit('/', 1)[-1])
    (out / name).write_bytes(data)
    records.append({'url': url, 'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
(out / 'sources.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(records, ensure_ascii=False))
