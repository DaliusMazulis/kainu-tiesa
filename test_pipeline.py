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
            if r['store']=='Rimi': self.assertTrue(r['source'].endswith('/p/'+r['sku']))
            elif r['store']=='Aibė': self.assertEqual(r['source'],'https://aibe.lt/akcijos/')
            else: self.fail('Unknown store')

class AibeTests(unittest.TestCase):
    def setUp(self): self.html=(ROOT/'tests/fixtures/aibe.html').read_text()
    def rows(self, html=None, stamp=STAMP):
        from collector import aibe_extract
        return aibe_extract(html if html is not None else self.html,'https://aibe.lt/akcijos/',stamp)
    def test_explicit_without_card_prices(self):
        rows=self.rows();self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['price'],'2.09')
        self.assertEqual(rows[1]['price'],'3.99')
        self.assertIsNone(rows[0]['regular_price'])
        self.assertIsNone(rows[0]['unit_price'])
        self.assertEqual(rows[0]['valid_to'],'2026-11-24')
    def test_card_only_not_published(self):
        self.assertEqual(self.rows(self.html.replace('Be kortelės','Su kortele')),[])
    def test_expired_and_future_offer_rejected(self):
        self.assertEqual(self.rows(stamp='2026-11-25T12:00:00Z'),[])
        self.assertEqual(self.rows(stamp='2026-11-10T12:00:00Z'),[])
    def test_expiry_uses_lithuanian_midnight(self):
        self.assertEqual(self.rows(stamp='2026-11-24T22:01:00Z'),[])
    def test_no_year_no_publish(self):
        self.assertEqual(self.rows(self.html.replace('2026.','')),[])
    def test_invalid_dates_no_publish(self):
        self.assertEqual(self.rows(self.html.replace('2026.11.24','2026.99.24')),[])
    def test_identity_survives_campaign_id_change(self):
        self.assertEqual(self.rows()[0]['product_id'],self.rows(self.html.replace('77054','99999'))[0]['product_id'])
    def test_variant_groups_skipped(self):
        changed=self.html.replace('200 g','įv. rūšių, 200 g')
        self.assertEqual(len(self.rows(changed)),1)
    def test_csv_preserves_all_observations_and_utf8(self):
        from collector import csv_export
        import csv,io
        rows=self.rows();text=csv_export(rows)
        self.assertTrue(text.startswith('\ufeff'))
        parsed=list(csv.reader(io.StringIO(text.lstrip('\ufeff')),delimiter=';'))
        self.assertEqual(len(parsed),len(rows)+1);self.assertEqual(parsed[1][1],rows[0]['name']);self.assertEqual(parsed[1][5],'2,09')
    def test_csv_formula_escaping(self):
        from collector import csv_export
        rows=self.rows();rows[0]['name']='=1+1';rows[1]['name']='  @SUM(1)'
        text=csv_export(rows);self.assertIn("'=1+1",text);self.assertIn("'  @SUM(1)",text)

class PublishedOfferVerificationTests(unittest.TestCase):
    def setUp(self):
        self.record=next(r for r in json.loads((ROOT/'data/archive_offers.json').read_text()) if r['valid_from']=='2026-11-24')
        self.html='<title>„Rimi“ savaitinis leidinys Nr. 48 (2026.11.24 - 2026.11.30)</title><p>248955 '+self.record['price_context']+'</p>'
    def test_reviewed_price_context_and_title(self):
        from collector import check_published_offer
        self.assertTrue(check_published_offer(self.html,self.record))
    def test_wrong_price_does_not_rewrite_an_approved_price(self):
        from collector import check_published_offer
        self.assertFalse(check_published_offer(self.html.replace('1,29','8,99'),self.record))
        self.assertEqual(self.record['price'],'1.29')
    def test_script_only_evidence_is_rejected(self):
        from collector import check_published_offer
        self.assertFalse(check_published_offer(self.html.replace('<p>','<script>').replace('</p>','</script>'),self.record))
    def test_wrong_issue_or_product_rejected(self):
        from collector import check_published_offer
        self.assertFalse(check_published_offer(self.html.replace('Nr. 48','Nr. 49'),self.record))
        self.assertFalse(check_published_offer(self.html.replace('248955','888888'),self.record))
    def test_missing_page_text_is_not_a_changed_price(self):
        from collector import published_offer_state
        self.assertEqual(published_offer_state('<title>Other page</title><p>Other products</p>',self.record),'unavailable')
        self.assertEqual(published_offer_state(self.html,self.record),'verified')
