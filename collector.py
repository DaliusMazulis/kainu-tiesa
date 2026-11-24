"""Offline parser by default. Use only HTML obtained with permission.
Usage: python collector.py page.html https://example.com/product
"""
import json, sys, datetime
from html.parser import HTMLParser
from decimal import Decimal
class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.active=False; self.blocks=[]
    def handle_starttag(self, tag, attrs):
        if tag=='script' and dict(attrs).get('type')=='application/ld+json':
            self.active=True; self.blocks.append('')
    def handle_endtag(self, tag):
        if tag=='script': self.active=False
    def handle_data(self, data):
        if self.active: self.blocks[-1]+=data
def walk(x):
    if isinstance(x,list):
        for y in x: yield from walk(y)
    elif isinstance(x,dict):
        if 'Product' in ([x.get('@type')] if isinstance(x.get('@type'),str) else (x.get('@type') or [])): yield x
        for y in x.values(): yield from walk(y)
def extract(html,source):
    p=Parser(); p.feed(html); out=[]
    for block in p.blocks:
        try: data=json.loads(block)
        except ValueError: continue
        for item in walk(data):
            offers=item.get('offers',[])
            for offer in offers if isinstance(offers,list) else [offers]:
                if not isinstance(offer,dict) or offer.get('priceCurrency')!='EUR': continue
                try: price=Decimal(str(offer['price']))
                except (KeyError,ArithmeticError,ValueError): continue
                if not price.is_finite() or price<0: continue
                out.append(dict(name=item.get('name'),sku=item.get('sku'),gtin=item.get('gtin13') or item.get('gtin'),price=str(price),currency='EUR',source=source,observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),channel='online',conditions='unverified',status='requires_review'))
    return out
if __name__=='__main__':
    if len(sys.argv)!=3: sys.exit('Usage: python collector.py page.html source_url')
    with open(sys.argv[1],encoding='utf-8') as f: rows=extract(f.read(),sys.argv[2])
    if not rows: sys.exit('No supported EUR product offers found')
    print(json.dumps(rows,ensure_ascii=False,indent=2))
