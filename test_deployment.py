import unittest
from scripts.deploy_pages import deploy

class PagesDeploymentTests(unittest.TestCase):
    def run_deploy(self,statuses):
        calls=[];ticks=[0]
        def transport(url, token, method='GET',payload=None):
            calls.append((url,method,payload))
            if method=='POST':return {'id':12,'page_url':'https://daliusmazulis.github.io/kainu-tiesa/'}
            return {'status':next(statuses)}
        def pause(seconds):ticks[0]+=seconds
        value=deploy(42,'DaliusMazulis/kainu-tiesa','commit','test-token','test-oidc',transport=transport,pause=pause,clock=lambda:ticks[0])
        return value,calls
    def test_uses_exact_uploaded_id_and_submits_once_while_polling(self):
        url,calls=self.run_deploy(iter(['deployment_queued','deployment_in_progress','succeed']))
        posts=[c for c in calls if c[1]=='POST'];self.assertEqual(len(posts),1)
        self.assertEqual(posts[0][2]['artifact_id'],42);self.assertEqual(posts[0][2]['oidc_token'],'test-oidc')
        self.assertEqual(url,'https://daliusmazulis.github.io/kainu-tiesa/')
    def test_failed_deployment_is_not_reported_as_success(self):
        with self.assertRaisesRegex(RuntimeError,'failed'):self.run_deploy(iter(['deployment_failed']))
    def test_does_not_deploy_to_another_project(self):
        with self.assertRaisesRegex(ValueError,'destination'):deploy(42,'DaliusMazulis/other','sha','test','test',transport=lambda *args:self.fail('Unexpected network call'))
    def test_rejects_missing_artifact(self):
        with self.assertRaisesRegex(ValueError,'artifact'):deploy(0,'DaliusMazulis/kainu-tiesa','sha','test','test',transport=lambda *args:self.fail('Unexpected network call'))
