from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, FormView, TemplateView, View
from django.db import IntegrityError

from .forms import (
    ChangePasswordForm,
    GetOtpForm,
    LoginForm,
    RegisterForm,
    RegisterPhoneForm,
    SetNewPasswordForm,
    VerifyOtpForm,
)
from .models import CustomUser, OtpCode
from .services import ActiveOtpExists, OtpSendError, create_otp, verify_otp_code
from apps.cart.services import merge_session_cart_to_user_cart
ACTIVE_OTP_MSG = "کد قبلی هنوز معتبر است؛ لطفاً تا پایان اعتبار آن صبر کنید."
SEND_FAIL_MSG = "ارسال کد تأیید ممکن نشد. لطفاً دوباره تلاش کنید."
# پیام یکسان برای شماره‌های موجود و ناموجود تا فهرست شماره‌ها قابل کشف نباشد
GENERIC_SENT_MSG = "اگر این شماره در سامانه باشد، کد تأیید برای آن ارسال شد."


class HomeView(TemplateView):
    template_name = "home.html"


# 1. مرحله اول ثبت‌نام: دریافت شماره موبایل
class RegisterPhoneView(FormView):
    form_class = RegisterPhoneForm
    template_name = "account/signup.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        phone = form.cleaned_data["phone_number"]
        # اگر شماره قبلاً ثبت شده، پیامک ارسال نمی‌شود ولی پاسخ یکسان است
        if CustomUser.objects.filter(phone_number=phone).exists():
            self.request.session["pending_register_phone"] = phone
            return redirect("account:signup_verify")

        try:
            create_otp(phone_number=phone, purpose=OtpCode.Purpose.REGISTER)
        except ActiveOtpExists:
            form.add_error("phone_number", ACTIVE_OTP_MSG)
            return self.form_invalid(form)
        except OtpSendError:
            form.add_error("phone_number", SEND_FAIL_MSG)
            return self.form_invalid(form)

        self.request.session["pending_register_phone"] = phone
        return redirect("account:signup_verify")


# 2. مرحله دوم ثبت‌نام: تأیید کد OTP
class VerifyRegisterOtpView(FormView):
    form_class = VerifyOtpForm
    template_name = "account/signup_verify.html"
    extra_context = {"show_resend": True}

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("pending_register_phone"):
            return redirect("account:signup")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        phone = self.request.session["pending_register_phone"]

        is_valid = verify_otp_code(
            phone_number=phone,
            purpose=OtpCode.Purpose.REGISTER,
            raw_code=form.cleaned_data["code"],
        )

        if not is_valid:
            form.add_error("code", "کد واردشده نادرست یا منقضی شده است.")
            return self.form_invalid(form)

        self.request.session["verified_register_phone"] = phone
        self.request.session.pop("pending_register_phone", None)
        return redirect("account:signup_complete")


# ارسال مجدد کد ثبت‌نام
class ResendRegisterOtpView(View):
    def post(self, request):
        phone = request.session.get("pending_register_phone")
        if not phone:
            return redirect("account:signup")

        try:
            create_otp(phone_number=phone, purpose=OtpCode.Purpose.REGISTER)
            messages.success(request, "کد جدید ارسال شد.")
        except ActiveOtpExists:
            messages.warning(request, ACTIVE_OTP_MSG)
        except OtpSendError:
            messages.error(request, SEND_FAIL_MSG)

        return redirect("account:signup_verify")


# 3. مرحله سوم ثبت‌نام: تکمیل اطلاعات (نام، رمز عبور)
class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "account/signup_complete.html"
    success_url = reverse_lazy("account:login")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        if not request.session.get("verified_register_phone"):
            return redirect("account:signup")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        phone = self.request.session["verified_register_phone"]
        if CustomUser.objects.filter(phone_number=phone).exists():
            # شماره در فاصله‌ی بین مراحل ثبت شده است
            self.request.session.pop("verified_register_phone", None)
            messages.error(self.request, "این شماره قبلاً ثبت شده است.")
            return redirect("account:login")

        form.instance.phone_number = phone
        try:
            response = super().form_valid(form)
        except IntegrityError:
            form.add_error(None, "ثبت‌نام انجام نشد؛ لطفاً دوباره تلاش کنید.")
            return self.form_invalid(form)

        self.request.session.pop("verified_register_phone", None)
        return response


# ورود به حساب
class LoginView(FormView):
    form_class = LoginForm
    template_name = "account/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)

        # **انتقال و حفظ سبد خرید مهمان به کاربر لاگین‌کرده**
        merge_session_cart_to_user_cart(self.request, user)

        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
        ):
            return redirect(next_url)
        return redirect("home")


# خروج از حساب
class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("account:login")


# 1. بازیابی رمز عبور: دریافت شماره موبایل
class ForgotPasswordPhoneView(FormView):
    form_class = GetOtpForm
    template_name = "account/password_reset_request.html"

    def form_valid(self, form):
        phone = form.cleaned_data["phone_number"]
        self.request.session["pending_reset_phone"] = phone

        user = CustomUser.objects.filter(phone_number=phone, is_active=True).first()
        if user is not None:
            try:
                create_otp(phone_number=phone, purpose=OtpCode.Purpose.RESET_PASSWORD, user=user)
            except ActiveOtpExists:
                # پیام یکسان؛ کاربر همچنان به مرحله‌ی تأیید هدایت می‌شود
                pass
            except OtpSendError:
                form.add_error("phone_number", SEND_FAIL_MSG)
                return self.form_invalid(form)

        messages.info(self.request, GENERIC_SENT_MSG)
        return redirect("account:password_reset_verify")


# 2. بازیابی رمز عبور: تأیید کد OTP
class VerifyResetOtpView(FormView):
    form_class = VerifyOtpForm
    template_name = "account/signup_verify.html"
    extra_context = {"show_resend": False}

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("pending_reset_phone"):
            return redirect("account:password_reset_request")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        phone = self.request.session["pending_reset_phone"]

        is_valid = verify_otp_code(
            phone_number=phone,
            purpose=OtpCode.Purpose.RESET_PASSWORD,
            raw_code=form.cleaned_data["code"],
        )

        if not is_valid:
            form.add_error("code", "کد واردشده نادرست یا منقضی شده است.")
            return self.form_invalid(form)

        self.request.session["verified_reset_phone"] = phone
        self.request.session.pop("pending_reset_phone", None)
        return redirect("account:password_reset_confirm")


# 3. بازیابی رمز عبور: ثبت رمز جدید
class SetNewPasswordView(FormView):
    form_class = SetNewPasswordForm
    template_name = "account/password_reset_confirm.html"
    success_url = reverse_lazy("account:login")

    def dispatch(self, request, *args, **kwargs):
        if not request.session.get("verified_reset_phone"):
            return redirect("account:password_reset_request")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        phone = self.request.session["verified_reset_phone"]
        user = CustomUser.objects.filter(phone_number=phone, is_active=True).first()
        if user is None:
            self.request.session.pop("verified_reset_phone", None)
            return redirect("account:password_reset_request")

        user.set_password(form.cleaned_data["new_password"])
        user.save(update_fields=["password"])

        self.request.session.pop("verified_reset_phone", None)
        messages.success(self.request, "رمز عبور با موفقیت تغییر کرد.")
        return super().form_valid(form)


# تغییر رمز عبور (وقتی کاربر لاگین است)
class ChangePasswordView(LoginRequiredMixin, FormView):
    form_class = ChangePasswordForm
    template_name = "account/password_change.html"
    success_url = reverse_lazy("account:password_change_done")
    login_url = reverse_lazy("account:login")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        user.set_password(form.cleaned_data["new_password"])
        user.save(update_fields=["password"])
        update_session_auth_hash(self.request, user)
        return super().form_valid(form)


class PasswordChangeDoneView(LoginRequiredMixin, TemplateView):
    template_name = "account/password_change_done.html"
    login_url = reverse_lazy("account:login")
