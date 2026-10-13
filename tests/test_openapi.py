import json
import re
import unittest
from pathlib import Path

from scripts.export_openapi import build_spec
from xunwei import create_app


class OpenApiTest(unittest.TestCase):
    def setUp(self):
        self.spec = build_spec()

    def test_export_is_current_and_covers_actual_routes(self):
        saved = json.loads((Path(__file__).resolve().parent.parent / 'docs/openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(saved, self.spec)
        app = create_app({'TESTING': True, 'SECRET_KEY': 'docs-test'})
        expected = set()
        for rule in app.url_map.iter_rules():
            if rule.endpoint == 'static':
                continue
            path = re.sub(r'<(?:int:)?(\w+)>', r'{\1}', rule.rule)
            expected.update((path, m.lower()) for m in rule.methods - {'HEAD', 'OPTIONS'})
        actual = {(p, m) for p, methods in self.spec['paths'].items() for m in methods}
        self.assertEqual(expected, actual)

    def test_parameters_ids_refs_and_post_security(self):
        ids = []
        for path, methods in self.spec['paths'].items():
            for method, op in methods.items():
                ids.append(op['operationId'])
                names = {p['name'] for p in op['parameters'] if p['in'] == 'path' and p['required']}
                self.assertEqual(names, set(re.findall(r'{(\w+)}', path)))
                self.assertTrue(op['responses'])
                if method == 'post':
                    self.assertIn('CsrfToken', op['security'][0])
                for response in op['responses'].values():
                    for media in response.get('content', {}).values():
                        ref = media['schema'].get('$ref')
                        if ref:
                            self.assertIn(ref.rsplit('/', 1)[1], self.spec['components']['schemas'])
        self.assertEqual(len(ids), len(set(ids)))

    def test_json_and_form_media_are_not_confused(self):
        paths = self.spec['paths']
        self.assertIn('application/json', paths['/favorites/migrate']['post']['requestBody']['content'])
        self.assertIn('application/x-www-form-urlencoded', paths['/login']['post']['requestBody']['content'])
        self.assertIn('text/html', paths['/rankings']['get']['responses']['200']['content'])
        self.assertIn('application/json', paths['/health']['get']['responses']['200']['content'])
        client = create_app({'TESTING': True, 'SECRET_KEY': 'docs-test'}).test_client()
        self.assertEqual(client.get('/favicon.ico').status_code, 204)


if __name__ == '__main__':
    unittest.main()
