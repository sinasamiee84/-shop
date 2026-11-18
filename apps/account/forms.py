import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password

from .models import CustomUser

PHONE_RE = re.compile(r"09[0-9]{9}")  # فقط ارقام لاتین؛ isdigit ارقام فارسی را هم می‌پذیرد


# ---------- اعتبارسنجی مشترک ----------

def validate_phone_format(number):
    if not PHONE_RE.fullmatch(number):
        raise forms.ValidationError("شماره موبایل باید ۱۱ رقم و با 09 شروع شود.")


def validate_password_strength(password, user=None):
    """از همان validatorهای AUTH_PASSWORD_VALIDATORS استفاده می‌کند."""
    validate_password(password, user=user)


# ---------- فرم‌های شماره و OTP ----------

class RegisterPhoneForm(forms.Form):
    phone_number = forms.CharField(label="شماره موبایل", max_length=11)

    def clean_phone_number(self):
        number = self.cleaned_data["phone_number"]
        validate_phone_format(number)
        # توجه: پیام «قبلاً ثبت‌نام کرده‌اید» عمداً حذف شد تا شماره‌ها قابل کشف نباشند.
        # بررسی تکراری بودن در مرحله‌ی تکمیل ثبت‌نام انجام می‌شود.
        return number


class GetOtpForm(forms.Form):
    """برای فراموشی رمز عبور"""
    phone_number = forms.CharField(label="شماره موبایل", max_length=11)

    def clean_phone_number(self):
        number = self.cleaned_data["phone_number"]
        validate_phone_format(number)
        return number


class VerifyOtpForm(forms.Form):
    code = forms.CharField(
        label="کد تأیید",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code"}),
    )

    def clean_code(self):
        code = self.cleaned_data["code"]
        if not re.fullmatch(r"[0-9]{6}", code):
            raise forms.ValidationError("کد تأیید باید ۶ رقم باشد.")
        return code


# ---------- ثبت‌نام ----------

class RegisterForm(forms.ModelForm):
    password = forms.CharField(label="رمز عبور", widget=forms.PasswordInput)
    password_confirmation = forms.CharField(label="تکرار رمز عبور", widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name")

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password_strength(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirmation = cleaned_data.get("password_confirmation")

        if password and confirmation and password != confirmation:
            self.add_error("password_confirmation", "رمز عبور و تکرار آن یکسان نیستند.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


# ---------- ورود ----------

class LoginForm(forms.Form):
    phone_number = forms.CharField(label="شماره موبایل")
    password = forms.CharField(label="رمز عبور", widget=forms.PasswordInput)

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get("phone_number")
        password = cleaned_data.get("password")

        if phone and password:
            self.user = authenticate(
                self.request,
                phone_number=phone,
                password=password,
            )
            if self.user is None:
                raise forms.ValidationError("شماره موبایل یا رمز عبور اشتباه است.")

        return cleaned_data

    def get_user(self):
        return self.user


# ---------- رمز عبور جدید ----------

class SetNewPasswordForm(forms.Form):
    new_password = forms.CharField(label="رمز عبور جدید", widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="تکرار رمز عبور جدید", widget=forms.PasswordInput)

    def clean_new_password(self):
        password = self.cleaned_data["new_password"]
        validate_password_strength(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "رمز عبور و تکرار آن یکسان نیستند.")

        return cleaned_data


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(label="رمز عبور فعلی", widget=forms.PasswordInput)
    new_password = forms.CharField(label="رمز عبور جدید", widget=forms.PasswordInput)
    confirm_password = forms.CharField(label="تکرار رمز عبور جدید", widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data["current_password"]
        if not self.user.check_password(current):
            raise forms.ValidationError("رمز عبور فعلی درست نیست.")
        return current

    def clean_new_password(self):
        password = self.cleaned_data["new_password"]
        validate_password_strength(password, user=self.user)
        return password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "رمز عبور و تکرار آن یکسان نیستند.")

        return cleaned_data
