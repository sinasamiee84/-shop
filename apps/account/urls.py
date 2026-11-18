from django.urls import path

from .views import (
    ChangePasswordView,
    ForgotPasswordPhoneView,
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    RegisterPhoneView,
    RegisterView,
    ResendRegisterOtpView,
    SetNewPasswordView,
    VerifyRegisterOtpView,
    VerifyResetOtpView,
)

app_name = "account"

urlpatterns = [
    # ثبت‌نام
    path("signup/", RegisterPhoneView.as_view(), name="signup"),
    path("signup/verify/", VerifyRegisterOtpView.as_view(), name="signup_verify"),
    path("signup/resend/", ResendRegisterOtpView.as_view(), name="resend_signup_otp"),
    path("signup/complete/", RegisterView.as_view(), name="signup_complete"),

    # ورود و خروج
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # بازیابی رمز عبور
    path("password-reset/", ForgotPasswordPhoneView.as_view(), name="password_reset_request"),
    path("password-reset/verify/", VerifyResetOtpView.as_view(), name="password_reset_verify"),
    path("password-reset/confirm/", SetNewPasswordView.as_view(), name="password_reset_confirm"),

    # تغییر رمز عبور (کاربر وارد شده)
    path("password-change/", ChangePasswordView.as_view(), name="password_change"),
    path("password-change/done/", PasswordChangeDoneView.as_view(), name="password_change_done"),
]
