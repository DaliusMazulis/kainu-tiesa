"""Public HTML collector. Standard library only; no login, proxies or retries on blocks."""
import argparse
import csv
import io
import datetime as dt
from decimal import Decimal
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
from zoneinfo import ZoneInfo
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

def aibe_extract(html, source, observed_at):
    """Only explicitly labelled prices without a card; never use the card unit price."""
    if source != 'https://aibe.lt/akcijos/': raise ValueError('Unsupported source')
    p = Parser(); p.feed(html); out = []
    today = dt.datetime.fromisoformat(observed_at.replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Vilnius')).date()
    # Resolve short section dates only against a full, explicitly stated campaign range.
    ranges = []
    for match in re.finditer(r'(20\d{2})[.](\d{2})[.](\d{2})\s*[-–]\s*(20\d{2})[.](\d{2})[.](\d{2})', p.root.text()):
        try:
            a,b,c,d,e,f = map(int, match.groups())
            start,end = dt.date(a,b,c),dt.date(d,e,f)
            if start <= today <= end and (end-start).days <= 45: ranges.append((start,end))
        except ValueError: continue
    for section in p.root.all():
        if 'bestOffers' not in section.attrs.get('class', '').split(): continue
        section_dates = [n.text() for n in section.all() if 'top-block-date' in n.attrs.get('class', '').split()]
        matches = [(a,b) for a,b in set(ranges) if section_dates and all(re.search(rf'{re.escape(a.strftime("%m.%d"))}\s*[-–]\s*{re.escape(b.strftime("%m.%d"))}', t) for t in section_dates)]
        if len(matches) != 1: continue
        start,end = matches[0]
        for card in section.all():
            if 'bestOffers-block' not in card.attrs.get('class', '').split(): continue
            name = card.find('bestOffers-block-discountProduct-name')
            label, amount = card.find('discount-without-card-name'), card.find('discount-without-card-price')
            if not name or not label or not amount or label.text().strip() != 'Be kortelės': continue
            m = re.fullmatch(r'\s*(\d+[.,]\d{2})\s*€\s*', amount.text())
            price = price_value(m.group(1)) if m else None
            full_name = ' '.join(name.text().split())
            # Variant groups cannot identify a single product and package reliably.
            if not price or re.search(r'(įv\.|įvairių|[2-9]\s+rūšių)', full_name, re.I): continue
            identity = unicodedata.normalize('NFKC', full_name).casefold()
            key = hashlib.sha256(identity.encode()).hexdigest()[:24]
            out.append(dict(product_id='aibe:'+key, sku=card.attrs.get('data-id'), name=full_name, store='Aibė', channel='in_store_offer', conditions='public_without_card', price=price, regular_price=None, currency='EUR', unit_price=None, source=source, listing_source=source, observed_at=observed_at, valid_from=start.isoformat(), valid_to=end.isoformat(), identity_method='exact_name_and_package', status='observed', evidence_sha256=hashlib.sha256(html.encode()).hexdigest()))
    return out

def catalog_extract(html, source, observed_at):
    """Public SSR prices only, cross-checked against a second card field."""
    host=urlparse(source).hostname
    stores={'www.jysk.lt':('JYSK','jysk','online'), 'www.drogas.lt':('Drogas','drogas','online'), 'pepco.lt':('Pepco','pepco','in_store_catalog')}
    if host not in stores: raise ValueError('Unsupported source')
    store,prefix,channel=stores[host];p=Parser();p.feed(html);out=[];seen=set()
    def amount(text):
        return price_value(re.sub(r'[\s€]', '', text))
    for card in p.root.all():
        regular=None;category='Buities prekės'
        if prefix=='jysk':
            if 'product-item' not in card.attrs.get('class','').split(): continue
            try: meta=json.loads(card.attrs['data-ga4-item'])
            except (KeyError,ValueError): continue
            sku=card.attrs.get('data-ga4-product-id','')
            final=card.find('final-price');visible=final.find('price-wo-currency') if final else None
            price=amount(visible.text()) if visible else None
            name=re.sub(r'\\u([0-9a-fA-F]{4})',lambda m:chr(int(m[1],16)),str(meta.get('item_name','')))
            links=[n for n in card.all() if n.tag=='a' and n.attrs.get('href','').endswith('.html')]
            if not links or str(meta.get('item_id'))!=sku or price_value(meta.get('price'))!=price: continue
            url=urljoin(source,links[0].attrs['href'])
            if not final or not any(n.tag=='meta' and n.attrs.get('itemprop')=='priceCurrency' and n.attrs.get('content')=='EUR' for n in final.all()): continue
            old=card.find('old-price');v=old.find('price-wo-currency') if old else None
            regular=amount(v.text()) if v else None
        elif prefix=='drogas':
            if card.tag!='e2-product-tile': continue
            name_node=card.find('product-list-item__name');v=card.find('price__default-value');a=card.find('product-list-item__link')
            if not name_node or not v or not a or v.attrs.get('aria-hidden')!='false': continue
            price=amount(v.text())
            if amount(v.attrs.get('aria-label',''))!=price: continue
            url=urljoin(source,a.attrs.get('href',''));m=re.search(r'/p/(BP_\d+)$',url)
            if not m: continue
            sku=m[1];name=name_node.text();category='Kosmetika ir higiena'
        else:
            if card.tag!='a' or '/products/' not in card.attrs.get('href',''): continue
            h=next((n for n in card.all() if n.tag=='h3'),None)
            v=next((n for n in card.all() if n.attrs.get('aria-label','').startswith('Product price: ')),None)
            m=re.search(r'(?:, | - )(\d+(?:[.,]\d+)?)(?:-€| €)',card.attrs.get('aria-label',''))
            if not h or not v or not m: continue
            price=amount(v.attrs['aria-label'].removeprefix('Product price: '))
            if price_value(m[1])!=price: continue
            # Check displayed digits as well as accessible labels.
            whole=card.find('price-small');parts=[n.text() for n in card.all() if 'price-small-subscript' in n.attrs.get('class','').split() and re.fullmatch(r'[.,]?\d{2}',n.text())]
            if not whole or price_value(whole.text()+('.'+parts[0].lstrip('.,') if parts else ''))!=price: continue
            url=urljoin(source,card.attrs['href']);match=re.search(r'-(\d+)$',url)
            if not match: continue
            sku=match[1];name=h.text();subtitle=next((n.text() for n in card.all() if n.tag=='p' and 'body-xsmall' in n.attrs.get('class','').split()), '')
            if subtitle: name+=' · '+subtitle
            if re.search(r'šun|šuns|kat[ėe]|augintin|gyvūn',name,re.I): category='Gyvūnams'
            elif re.search(r'vyrišk|moterišk',name,re.I): category='Apranga'
            elif re.search(r'žaisl(?!iuk)|pliušinis imbierinis|lėl|lego|vaik|berniuk|mergai|žaid|kūdiki|putplasčio šov',name,re.I): category='Vaikams'
        if not sku or not name or not price or urlparse(url).hostname!=host or sku in seen: continue
        seen.add(sku)
        out.append(dict(product_id=prefix+':'+sku,sku=sku,name=' '.join(name.split()),store=store,category=category,channel=channel,conditions='public_without_card',price=price,regular_price=regular,currency='EUR',source=url,listing_source=source,observed_at=observed_at,status='observed',evidence_sha256=hashlib.sha256(html.encode()).hexdigest()))
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
        if parsed.scheme != 'https' or parsed.hostname not in {'www.rimi.lt', 'www.barbora.lt', 'www.varle.lt', 'www.senukai.lt', 'www.lidl.lt', 'aibe.lt', 'leidiniai.rimi.lt', 'www.jysk.lt', 'www.drogas.lt', 'pepco.lt'}: raise ValueError('Host not allowed')
        origin = 'https://' + parsed.netloc
        if origin not in self.robots:
            rp = RobotFileParser(); rp.parse(self.read(origin+'/robots.txt').lstrip('\ufeff').splitlines()); self.robots[origin] = rp
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

def csv_export(rows):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter=';', lineterminator='\n')
    writer.writerow(['Prekės ID','Prekė','Parduotuvė','Kanalas','Sąlygos','Kaina EUR','Stebėjimo laikas UTC','Galioja nuo','Galioja iki','Šaltinis'])
    def safe(value):
        text = str(value or '')
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text
    for r in rows:
        writer.writerow([safe(r.get(k)) for k in ['product_id','name','store','channel','conditions']] + [r['price'].replace('.', ','), r['observed_at'], r.get('valid_from', ''), r.get('valid_to', ''), safe(r['source'])])
    return '\ufeff' + stream.getvalue()


def leaflet_text(html, record):
    # iPaper exposes all page text as JSON in its public HTML. Read JSON, never execute scripts.
    match=re.search(r'window\.staticSettings\s*=\s*',html)
    if match:
        try:
            settings,_=json.JSONDecoder().raw_decode(html[match.end():])
            pages=settings.get('pageTexts',[]);page=int(record.get('page',1))
            if 1<=page<=len(pages) and isinstance(pages[page-1],str):
                return ' '.join(pages[page-1].split())
        except (ValueError,TypeError,AttributeError): pass
    p=Parser();p.feed(html)
    return ' '.join(' '.join(n.text().split()) for n in p.root.all() if n.tag=='p')

def check_published_offer(html, record):
    """Re-check an already reviewed offer; never infer a new price or card condition."""
    p=Parser(); p.feed(html)
    text=leaflet_text(html,record)
    titles=' '.join(n.text() for n in p.root.all() if n.tag in {'title','h1'})
    required=record.get('required_title_tokens', [])
    context=record.get('price_context', '')
    return bool(required and context and all(token in titles for token in required) and context in text and re.search(r'(?<!\d)'+re.escape(record['sku'])+r'(?!\d)', text))

def published_offer_state(html,record):
    if check_published_offer(html,record): return 'verified'
    p=Parser();p.feed(html)
    visible=leaflet_text(html,record)
    # Some leaflet responses contain only the first page's text for another page URL.
    # Missing page text is not evidence that the reviewed price has changed.
    return 'changed_requires_review' if record['sku'] in visible and record['name'] in visible else 'unavailable'


def verify_archives(client=None):
    client=client or PublicClient();stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    path=ROOT/'data/archive_offers.json';records=json.loads(path.read_text());cache={};blocked=set();verified=0;errors=[]
    for r in records:
        url=r['source'];host=urlparse(url).hostname
        r['last_checked_at']=stamp
        try:
            if host in blocked: raise ValueError('Source host unavailable earlier in this run')
            if url not in cache:
                try: cache[url]=client.get(url)
                except Exception:
                    blocked.add(host);raise
            html=cache[url]
            state=published_offer_state(html,r)
            if state=='verified':
                r['source_check']='verified';r['last_verified_at']=stamp;r['evidence_sha256']=hashlib.sha256(html.encode()).hexdigest();verified+=1
            else:
                r['source_check']=state;errors.append(('Leidinio kainai reikalinga peržiūra: ' if state=='changed_requires_review' else 'Šaltinio HTML nepateikia šios prekės puslapio teksto: ')+r['sku'])
        except Exception as e:
            r['source_check']='unavailable';errors.append(str(e))
    atomic_json(path,records)
    return dict(store='Rimi leidiniai',status='ok' if verified==len(records) else 'partial' if verified else 'unavailable',observations=verified,errors=sorted(set(errors)),checked_at=stamp)


def collect():
    client = PublicClient(); stamp = dt.datetime.now(dt.timezone.utc).isoformat(); incoming=[]; sources=[]
    config = json.loads((ROOT/'sources.json').read_text())
    for store in config:
        count=0; errors=[]; pages=[]; failed=False
        for url in store['urls']:
            try:
                html = client.get(url)
                parser = {'rimi':rimi_extract, 'aibe':aibe_extract, 'catalog':catalog_extract}.get(store['parser'])
                rows = parser(html, url, stamp) if parser else []
                incoming.extend(rows); count += len(rows)
                pages.append({'url':url, 'count':len(rows), 'sha256':hashlib.sha256(html.encode()).hexdigest()})
                if not rows: errors.append('Šios parduotuvės kainų parseris dar neprijungtas' if store['parser'] is None else 'Viešame HTML palaikomų kainų nerasta')
            except Exception as e:
                failed=True; errors.append(str(e)); break  # Do not retry a blocked host.
        sources.append(dict(store=store['store'], status='ok' if count and not errors else 'partial' if count else 'unavailable' if failed else 'no_data' if store['parser'] else 'unsupported', observations=count, errors=errors, pages=pages, checked_at=stamp))
    sources.append(verify_archives(client))
    path = ROOT/'data/observations.json'
    existing = json.loads(path.read_text()) if path.exists() else []
    merged = merge_observations(existing, incoming)
    atomic_json(path, merged)
    csv_path = ROOT/'data/observations.csv'
    csv_temp = csv_path.with_suffix('.tmp')
    csv_temp.write_text(csv_export(merged), encoding='utf-8', newline='')
    csv_temp.replace(csv_path)
    atomic_json(ROOT/'data/status.json', dict(updated_at=stamp, sources=sources, total_observations=len(merged), products=len({r['product_id'] for r in merged}), new_observations=len(merged)-len(existing)))
    print(json.dumps({'products':len({r['product_id'] for r in merged}), 'new':len(merged)-len(existing), 'sources':sources}, ensure_ascii=False, indent=2))
    return bool(incoming)

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--collect', action='store_true'); ap.add_argument('--verify-archives', action='store_true'); ap.add_argument('html', nargs='?'); ap.add_argument('source', nargs='?'); args=ap.parse_args()
    if args.verify_archives:
        print(json.dumps(verify_archives(),ensure_ascii=False,indent=2));raise SystemExit(0)
    if args.collect: raise SystemExit(0 if collect() else 1)
    if not args.html or not args.source: ap.error('Use --collect or page.html source_url')
    print(json.dumps(extract(Path(args.html).read_text(), args.source), ensure_ascii=False, indent=2))
