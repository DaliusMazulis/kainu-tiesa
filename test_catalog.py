import unittest
from pathlib import Path
from collector import catalog_extract

class CatalogTests(unittest.TestCase):
    stamp='2026-11-24T19:00:00Z'
    def rows(self,store,html=None):
        host={'jysk':'www.jysk.lt','drogas':'www.drogas.lt','pepco':'pepco.lt'}[store]
        return catalog_extract(html or Path('fixtures/'+store+'-card.html').read_text(),'https://'+host+'/',self.stamp)
    def test_jysk_public_price_not_old_or_lowest_placeholder(self):
        r=self.rows('jysk')[0];self.assertEqual((r['name'],r['price'],r['regular_price']),('Pagalvės užvalkalas JESSIKA','0.99','2.99'))
    def test_jysk_disagreement_excluded(self):
        s=Path('fixtures/jysk-card.html').read_text().replace('&quot;price&quot;:0.99','&quot;price&quot;:9.99')
        self.assertEqual(self.rows('jysk',s),[])
    def test_drogas_default_not_member(self):
        r=self.rows('drogas')[0];self.assertEqual(r['price'],'3.29');self.assertEqual(r['conditions'],'public_without_card');self.assertIsNone(r['regular_price'])
    def test_hidden_default_excluded(self):
        s=Path('fixtures/drogas-card.html').read_text().replace('aria-hidden="false"','aria-hidden="true"')
        self.assertEqual(self.rows('drogas',s),[])
    def test_pepco_three_price_fields_and_children_category(self):
        r=self.rows('pepco')[0];self.assertEqual((r['price'],r['channel'],r['category']),('7.00','in_store_catalog','Vaikams'))
    def test_pepco_disagreement_excluded(self):
        s=Path('fixtures/pepco-card.html').read_text().replace('Product price: 7 €','Product price: 8 €')
        self.assertEqual(self.rows('pepco',s),[])
    def test_unapproved_host_rejected(self):
        with self.assertRaises(ValueError):catalog_extract('', 'https://example.org/',self.stamp)

class LeafletPageTests(unittest.TestCase):
    def test_only_requested_public_json_page_used(self):
        from collector import leaflet_text
        source='<p>first page</p><script>window.staticSettings = {"pageTexts":["first page","second page 1,29"]};</script>'
        self.assertEqual(leaflet_text(source,{'page':2}),'second page 1,29')
