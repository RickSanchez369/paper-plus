# path: apps/users/views.py

"""
Sign-in for the frontend.

The auth model itself does not change (D-007: phone is the USERNAME_FIELD).
What changes is that there is no business-picker step after it any more —
there is only one business now (D-033), so logging in lands straight on the
dashboard.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView

from apps.shared.dates import to_ascii_digits


class PhoneLoginForm(AuthenticationForm):
    """
    Django's login form, relabelled for a phone number.

    `AuthenticationForm` hard-codes the label "Username" and a text input;
    the field is redeclared here so the page says "شماره موبایل" and the
    browser offers the right keyboard and autofill on a phone.
    """

    username = forms.CharField(
        label="شماره موبایل",
        widget=forms.TextInput(attrs={
            "class": "field__control",
            "autofocus": True,
            "autocomplete": "username",
            "inputmode": "numeric",
            "dir": "ltr",
            "placeholder": "۰۹…",
        }),
    )
    password = forms.CharField(
        label="گذرواژه",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "class": "field__control",
            "autocomplete": "current-password",
            "dir": "ltr",
        }),
    )

    def clean_username(self):
        # Persian keyboards type ۰۹۱۲…; the stored phone is ASCII (D-007).
        return to_ascii_digits((self.cleaned_data.get("username") or "").strip())

    # Shown for both "no such phone" and "wrong password", deliberately:
    # a different message for each would tell an outsider which phone
    # numbers have accounts.
    error_messages = {
        "invalid_login": "شماره موبایل یا گذرواژه درست نیست.",
        "inactive": "این حساب غیرفعال است.",
    }


class PaperPlusLoginView(LoginView):
    """Sign-in page. Already-signed-in visitors are sent on to the dashboard."""

    template_name = "users/login.html"
    authentication_form = PhoneLoginForm
    redirect_authenticated_user = True


class PaperPlusLogoutView(LogoutView):
    """Sign-out. POST-only, which is Django's default and what the header posts."""
