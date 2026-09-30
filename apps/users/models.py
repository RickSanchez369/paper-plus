# path: apps/users/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.shared.models import BaseModel

# Iranian mobile number: 11 digits starting with 09
phone_validator = RegexValidator(
    regex=r"^09\d{9}$",
    message="شماره موبایل باید ۱۱ رقم باشد و با ۰۹ شروع شود.",
)


class UserManager(BaseUserManager):
    """
    Manager for the custom User model.

    Django calls these two methods; they must exist and must accept
    `phone` as the identifying argument instead of `username`.
    """

    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("شماره موبایل الزامی است.")

        extra_fields.setdefault("is_active", True)

        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)  # hashes the password; never store raw
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("سوپریوزر باید is_staff=True داشته باشد.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("سوپریوزر باید is_superuser=True داشته باشد.")

        return self.create_user(phone, password, **extra_fields)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """
    Custom user, identified by mobile phone number.

    Carries no role: any authenticated user may use every page. `is_superuser`
    is the only distinction
    left, and it gates one action (cancellation).
    """

    phone = models.CharField(
        max_length=11,
        unique=True,
        validators=[phone_validator],
        verbose_name="شماره موبایل",
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="نام",
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="نام خانوادگی",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )
    is_staff = models.BooleanField(
        default=False,  # required by Django admin
        verbose_name="دسترسی به پنل مدیریت",
    )

    history = HistoricalRecords()

    objects = UserManager()

    USERNAME_FIELD = "phone"  # what the user logs in with
    REQUIRED_FIELDS = []  # extra prompts in createsuperuser; password is always asked

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"
        ordering = ["phone"]

    def __str__(self):
        return f"{self.get_full_name()} ({self.phone})" if self.get_full_name() else self.phone

    def get_full_name(self):
        """
        First + last name, or "" when neither is set.

        AbstractBaseUser does not provide this (only AbstractUser does), but
        Django's admin and any template writing `user.get_full_name` expect
        it -- without it a template silently falls back instead of failing,
        which hides the mistake rather than fixing it.
        """
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        """First name if known, otherwise the phone number."""
        return self.first_name or self.phone