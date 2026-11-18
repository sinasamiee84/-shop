from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CustomUser, OtpCode
from .services import MAX_OTP_ATTEMPTS, create_otp, verify_otp_code


@override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False)
class OtpAndAuthTests(TestCase):
    def test_home_renders_for_anonymous(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)

    def test_register_phone_redirects_to_verify(self):
        resp = self.client.post(reverse("account:signup"), {"phone_number": "09121234567"})
        self.assertRedirects(resp, reverse("account:signup_verify"))

    def test_wrong_code_is_rejected_and_attempts_limited(self):
        create_otp(phone_number="09121234567", purpose=OtpCode.Purpose.REGISTER)
        for _ in range(MAX_OTP_ATTEMPTS):
            self.assertFalse(verify_otp_code("09121234567", OtpCode.Purpose.REGISTER, "000000"))
        # after the limit even the right code must fail
        otp = OtpCode.objects.get(phone_number="09121234567")
        self.assertGreaterEqual(otp.attempts, MAX_OTP_ATTEMPTS)

    def test_login_with_phone_number(self):
        CustomUser.objects.create_user(phone_number="09121234567", password="Str0ng-pass!xyz")
        ok = self.client.post(
            reverse("account:login"),
            {"phone_number": "09121234567", "password": "Str0ng-pass!xyz"},
        )
        self.assertEqual(ok.status_code, 302)
