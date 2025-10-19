from django.test import TestCase
from django.urls import reverse

class AuthHubTests(TestCase):
    def test_hub_loads(self):
        url = reverse("accounts:start")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Get Started")

    def test_pick_role_sets_session_and_redirects_to_login(self):
        url = reverse("accounts:pick_role", kwargs={"role": "organizer"})
        r = self.client.get(url, follow=False)
        self.assertEqual(self.client.session.get("desired_role"), "organizer")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login", r["Location"])

    def test_guest_sets_flag_and_redirects(self):
        url = reverse("accounts:guest_entry")
        r = self.client.get(url, follow=False)
        self.assertTrue(self.client.session.get("guest"))
        self.assertEqual(r.status_code, 302)
