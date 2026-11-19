"""Service configuration catalog regressions, isolated from real cloud storage."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import app as backend
import persistent_history


class ServiceCatalogTests(unittest.TestCase):
    def setUp(self):
        backend.app.testing = True
        self.contents = {}
        self.callbacks = [
            patch.object(persistent_history, "put_blob", side_effect=self.fake_put),
            patch.object(persistent_history, "query_blobs", side_effect=self.fake_list),
            patch.object(persistent_history, "get_blob", side_effect=self.fake_get),
        ]
        for callback in self.callbacks:
            callback.start()
            self.addCleanup(callback.stop)

    def fake_put(self, pathname, content, **kwargs):
        self.assertEqual(kwargs["access"], "private")
        self.contents[pathname] = content
        return SimpleNamespace(pathname=pathname)

    def fake_list(self, prefix=None, **kwargs):
        return iter(SimpleNamespace(pathname=k) for k in self.contents if k.startswith(prefix or ""))

    def fake_get(self, pathname, **kwargs):
        return SimpleNamespace(body=self.contents[pathname])

    def test_saved_service_visible_after_request(self):
        with patch.object(backend, "HAS_PERSISTENT_STORAGE", True):
            saved_id = backend.db_save_service(
                "CalculatorService", "urn:calculator",
                "https://example.com/soap/calculator", "<definitions/>"
            )
            self.assertIsInstance(saved_id, int)
            response = backend.app.test_client().get("/api/v1/services")
            self.assertEqual(response.status_code, 200)
            services = response.get_json()["services"]
            self.assertEqual(len(services), 1)
            self.assertEqual(services[0]["id"], saved_id)
            self.assertEqual(services[0]["service_name"], "CalculatorService")
            self.assertNotIn("wsdl_content", services[0])

    def test_empty_service_catalog(self):
        with patch.object(backend, "HAS_PERSISTENT_STORAGE", True):
            response = backend.app.test_client().get("/api/v1/services")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["services"], [])


if __name__ == "__main__":
    unittest.main()
