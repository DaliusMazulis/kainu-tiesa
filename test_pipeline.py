import datetime as dt
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from collector import rimi_extract, merge_observations, PublicClient, price_value
ROOT=Path(__file__).parent
SOURCE='https://www.rimi.lt/e-parduotuve/lt/paieska?query=pienas'
STAMP='2026-11-24T17:15:37+00:00'
class PipelineTests(unittest.TestCase):
    def setUp(self): self.html=(ROOT/'tests/fixtures/rimi.html').read_text()
    def test_actual_public_cards(self):
        rows=rimi_extract(self.html,SOURCE,STAMP)
        self.assertEqual(len(rows),3)
        self.assertEqual(rows[0]['sku'],'4000040')
        self.assertEqual(rows[0]['price'],'1.29')
        self.assertEqual(rows[2]['price'],'2.05')
        self.assertEqual(rows[2]['regular_price'],'2.59')
        self.assertTrue(all(r['evidence_sha256'] for r in rows))
    def test_loyalty_price_is_not_used(self):
        rows=rimi_extract(self.html,SOURCE,STAMP)
        r=next(r for r in rows if r['sku']=='196376')
        self.assertEqual(r['price'],'2.55') # Card-only 1.53 is deliberately excluded.
        self.assertEqual(r['conditions'],'public_without_card')
    def test_disagreeing_visible_and_metadata_price_rejected(self):
        altered=self.html.replace('1.29 €','9.99 €')
        self.assertFalse(any(r['sku']=='4000040' for r in rimi_extract(altered,SOURCE,STAMP)))
    def test_missing_metadata_rejected(self):
        self.assertEqual(rimi_extract(self.html.replace('data-gtm-eec-product=','data-removed='),SOURCE,STAMP),[])
    def test_foreign_source_rejected(self):
        with self.assertRaises(ValueError): rimi_extract(self.html,'https://evil.test/',STAMP)
    def test_bad_prices(self):
        for n in ['0','-1','NaN','Infinity','1.001',None,'bad']: self.assertIsNone(price_value(n))
    def test_idempotent_and_append_only(self):
        rows=rimi_extract(self.html,SOURCE,STAMP)
        changed=[dict(rows[0],price='999.00')]
        self.assertEqual(merge_observations(rows,rows+changed),merge_observations(rows,[]))
        tomorrow=[dict(rows[0],observed_at='2026-11-25T17:15:37Z')]
        self.assertEqual(len(merge_observations(rows,tomorrow)),4)
    def test_robots_blocks_page(self):
        c=PublicClient()
        with patch.object(c,'read',return_value='User-agent: *\nDisallow: /e-parduotuve/') as read:
            with self.assertRaisesRegex(ValueError,'robots'): c.get(SOURCE)
            self.assertEqual(read.call_count,1)
    def test_robots_failure_fails_closed(self):
        c=PublicClient()
        with patch.object(c,'read',side_effect=OSError('403')) as read:
            with self.assertRaises(OSError): c.get(SOURCE)
            self.assertEqual(read.call_count,1)
    def test_dataset_has_only_unique_real_observations(self):
        rows=json.loads((ROOT/'data/observations.json').read_text())
        self.assertTrue(rows)
        self.assertEqual(len(rows),len({(r['product_id'],r['conditions'],r['observed_at'][:10]) for r in rows}))
        for r in rows:
            self.assertEqual(r['status'],'observed');self.assertEqual(r['currency'],'EUR')
            self.assertTrue(price_value(r['price']));self.assertEqual(len(r['evidence_sha256']),64)
            self.assertTrue(r['source'].endswith('/p/'+r['sku']))
