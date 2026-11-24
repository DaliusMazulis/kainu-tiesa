"""Public HTML collector. Standard library only; no login, proxies or retries on blocks."""
import argparse
import datetime as dt
from decimal import Decimal
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

UA = 'KainuTiesa/1.0 (+https://github.com/DaliusMazulis/kainu-tiesa)'
ROOT = Path(__file__).parent

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
    def all(self):
        yield self
        for child in self.children:
            if isinstance(child, Node): yield from child.all()
    def find(self, cls):
        return next((n for n in self.all() if cls in n.attrs.get('class', '').split()), None)
    def text(self):
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children).strip()

class Parser(HTMLParser):
    VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
    def __init__(self):
        super().__init__(); self.root = Node(); self.stack = [self.root]
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs); self.stack[-1].children.append(n)
        if tag not in self.VOID: self.stack.append(n)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID: self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]; break
    def handle_data(self, data): self.stack[-1].children.append(data)

def walk(x):
    if isinstance(x, list):
        for y in x: yield from walk(y)
    elif isinstance(x, dict):
        if 'Product' in ([x.get('@type')] if isinstance(x.get('@type'), str) else (x.get('@type') or [])): yield x
        for y in x.values(): yield from walk(y)

def price_value(value):
    try:
        n = Decimal(str(value).strip().replace(',', '.'))
        if n.is_finite() and n > 0 and n.as_tuple().exponent >= -2: return format(n, '.2f')
    except (ArithmeticError, ValueError): pass
    return None

def extract(html, source):
    """Generic JSON-LD is retained for offline review; never auto-published."""
    p = Parser(); p.feed(html); out = []
    for n in p.root.all():
        if n.tag != 'script' or n.attrs.get('type') != 'application/ld+json': continue
        try: data = json.loads(n.text())
        except ValueError: continue
        for item in walk(data):
            offers = item.get('offers', [])
            for offer in offers if isinstance(offers, list) else [offers]:
                if not isinstance(offer, dict) or offer.get('priceCurrency') != 'EUR': continue
                price = price_value(offer.get('price'))
                if not price: continue
                out.append(dict(name=item.get('name'), sku=item.get('sku'), gtin=item.get('gtin13') or item.get('gtin'), price=price, currency='EUR', source=source, observed_at=dt.datetime.now(dt.timezone.utc).isoformat(), channel='online', conditions='unverified', status='requires_review'))
    return out

def rimi_extract(html, source, observed_at):
    if urlparse(source).hostname != 'www.rimi.lt': raise ValueError('Unsupported source')
    p = Parser(); p.feed(html); out = []
    for card in p.root.all():
        sku = card.attrs.get('data-product-code')
        if not sku or 'card' not in card.attrs.get('class', '').split(): continue
        name, amount = card.find('card__name'), card.find('card__price')
        link = card.find('card__url')
        if not name or not amount or not link: continue
        accessible = amount.find('sr-only')
        m = re.search(r'(?<![\d.,])(\d+[.,]\d{2})\s*€', accessible.text() if accessible else '')
        price = price_value(m.group(1)) if m else None
        product_url = urljoin(source, link.attrs.get('href', ''))
        if not price or urlparse(product_url).hostname != 'www.rimi.lt' or not product_url.endswith('/p/' + sku): continue
        # Cross-check visible price against the public card's product metadata.
        try: meta = json.loads(card.attrs['data-gtm-eec-product'])
        except (KeyError, ValueError): continue
        if str(meta.get('id')) != sku or price_value(meta.get('price')) != price or meta.get('currency') != 'EUR': continue
        old = card.find('card__old-price')
        om = re.search(r'(\d+[.,]\d{2})\s*€', old.text()) if old else None
        previous = price_value(om.group(1)) if om else None
        unit = card.find('card__price-per')
        out.append(dict(product_id='rimi:'+sku, sku=sku, name=' '.join(name.text().split()), store='Rimi', channel='online', conditions='public_without_card', price=price, regular_price=previous, currency='EUR', unit_price=' '.join(unit.find('sr-only').text().split()) if unit and unit.find('sr-only') else None, source=product_url, listing_source=source, observed_at=observed_at, status='observed', evidence_sha256=hashlib.sha256(html.encode()).hexdigest()))
    return out

class PublicClient:
    def __init__(self): self.robots = {}; self.last = 0
    def read(self, url):
        wait = 2 - (time.monotonic() - self.last)
        if wait > 0: time.sleep(wait)
        self.last = time.monotonic()
        # Redirects are refused rather than followed to a new, unchecked target.
        from urllib.request import HTTPRedirectHandler, build_opener
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        with build_opener(NoRedirect).open(Request(url, headers={'User-Agent': UA}), timeout=25) as r:
            if 'text/' not in r.headers.get('Content-Type', ''): raise ValueError('Not text')
            data = r.read(3_000_001)
            if len(data) > 3_000_000: raise ValueError('Response too large')
            return data.decode('utf-8')
    def get(self, url):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in {'www.rimi.lt', 'www.barbora.lt', 'www.varle.lt', 'www.senukai.lt', 'www.lidl.lt'}: raise ValueError('Host not allowed')
        origin = 'https://' + parsed.netloc
        if origin not in self.robots:
            rp = RobotFileParser(); rp.parse(self.read(origin+'/robots.txt').splitlines()); self.robots[origin] = rp
        rp = self.robots[origin]
        if not rp.can_fetch(UA, url): raise ValueError('robots.txt disallows this URL')
        delay = rp.crawl_delay(UA) or rp.crawl_delay('*') or 2
        if delay > 2:
            wait = delay - (time.monotonic() - self.last)
            if wait > 0: time.sleep(wait)
        return self.read(url)

def merge_observations(existing, incoming):
    # Keep the first observed value of each day. A repeated run cannot rewrite history.
    merged = {}
    for r in existing + incoming:
        key = (r['product_id'], r['conditions'], r['observed_at'][:10])
        merged.setdefault(key, r)
    return sorted(merged.values(), key=lambda r: (r['observed_at'], r['product_id']))

def atomic_json(path, data):
    temp = path.with_suffix('.tmp'); temp.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8'); temp.replace(path)

def collect():
    client = PublicClient(); stamp = dt.datetime.now(dt.timezone.utc).isoformat(); incoming=[]; sources=[]
    config = json.loads((ROOT/'sources.json').read_text())
    for store in config:
        count=0; errors=[]; pages=[]
        for url in store['urls']:
            try:
                html = client.get(url)
                rows = rimi_extract(html, url, stamp) if store['parser']=='rimi' else []
                incoming.extend(rows); count += len(rows)
                pages.append({'url':url, 'count':len(rows), 'sha256':hashlib.sha256(html.encode()).hexdigest()})
                if not rows: errors.append('Šios parduotuvės kainų parseris dar neprijungtas' if store['parser'] is None else 'Viešame HTML palaikomų kainų nerasta')
            except Exception as e:
                errors.append(str(e)); break  # Do not retry a blocked host.
        sources.append(dict(store=store['store'], status='ok' if count and not errors else 'partial' if count else 'unavailable', observations=count, errors=errors, pages=pages, checked_at=stamp))
    path = ROOT/'data/observations.json'
    existing = json.loads(path.read_text()) if path.exists() else []
    merged = merge_observations(existing, incoming)
    atomic_json(path, merged)
    atomic_json(ROOT/'data/status.json', dict(updated_at=stamp, sources=sources, total_observations=len(merged), products=len({r['product_id'] for r in merged}), new_observations=len(merged)-len(existing)))
    print(json.dumps({'products':len({r['product_id'] for r in merged}), 'new':len(merged)-len(existing), 'sources':sources}, ensure_ascii=False, indent=2))
    return bool(incoming)

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--collect', action='store_true'); ap.add_argument('html', nargs='?'); ap.add_argument('source', nargs='?'); args=ap.parse_args()
    if args.collect: raise SystemExit(0 if collect() else 1)
    if not args.html or not args.source: ap.error('Use --collect or page.html source_url')
    print(json.dumps(extract(Path(args.html).read_text(), args.source), ensure_ascii=False, indent=2))
