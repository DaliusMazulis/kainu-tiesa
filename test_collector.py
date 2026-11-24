import unittest
from collector import extract
class CollectorTests(unittest.TestCase):
    def test_eur(self):
        html='<script type="application/ld+json">{"@type":"Product","name":"Test","sku":"123","offers":{"price":"9.99","priceCurrency":"EUR"}}</script>'
        rows=extract(html,"https://example.com/test")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["price"],"9.99")
        self.assertEqual(rows[0]["status"],"requires_review")
    def test_empty(self):
        self.assertEqual(extract("<html></html>","https://example.com"),[])
    def test_invalid(self):
        for price in ["NaN","-1","Infinity","bad"]:
            html='<script type="application/ld+json">{"@type":"Product","offers":{"price":"'+price+'","priceCurrency":"EUR"}}</script>'
            self.assertEqual(extract(html,"https://example.com"),[])
if __name__=="__main__":
    unittest.main()
