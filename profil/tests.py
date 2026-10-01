from django.test import TestCase


class HomeViewTest(TestCase):
    def test_home_status_200(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_home_uses_base_template(self):
        response = self.client.get("/")
        self.assertTemplateUsed(response, "base.html")
