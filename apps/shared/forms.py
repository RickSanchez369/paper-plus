# path: apps/shared/forms.py

"""
Form pieces every module reuses.

`JalaliDateField` is the only way a date should enter or leave a form in
this app. Using a plain `forms.DateField` anywhere would silently read the
typed digits as Gregorian and store a date ~621 years off — the kind of
mistake that looks fine on the screen it was typed into and wrong
everywhere else.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.shared import dates


class JalaliDateInput(forms.TextInput):
    """
    A text box the Jalali date-picker attaches to.

    Deliberately not `<input type="date">`: a native date input renders the
    browser's own Gregorian calendar, which is the one thing this field
    exists to avoid. The picker is progressive — with JavaScript off the
    box still accepts a typed date.
    """

    def __init__(self, attrs=None):
        defaults = {
            "class": "field__control js-jalali-date",
            "inputmode": "numeric",
            "autocomplete": "off",
            "placeholder": "۱۴۰۵/۰۷/۰۳",
            "dir": "ltr",
        }
        defaults.update(attrs or {})
        super().__init__(defaults)

    def format_value(self, value):
        """Show a stored Gregorian date back to the user as Jalali."""
        if value in (None, ""):
            return ""
        # A re-rendered invalid submission hands back the raw string the
        # user typed; leave it alone so they can correct it rather than
        # having their input silently vanish.
        if isinstance(value, str):
            return value
        return dates.format_date(value)


class JalaliDateField(forms.Field):
    """
    A date typed in Jalali, stored in Gregorian.

    Accepts Persian, Arabic-Indic or ASCII digits, and `/`, `-` or `.` as
    the separator, because all of those are what people actually type.
    """

    widget = JalaliDateInput

    default_error_messages = {
        "required": "تاریخ الزامی است.",
        "invalid": "تاریخ را به شکل ۱۴۰۵/۰۷/۰۳ وارد کنید.",
        "nonexistent": "این تاریخ در تقویم وجود ندارد.",
    }

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            parsed = dates.parse_jalali(value)
        except ValueError:
            # Well-formed but not a real day: 1405/13/01, or 30 Esfand in a
            # year that has no 30 Esfand. Worth its own message -- "wrong
            # format" would send the user hunting for a typo that is not there.
            raise ValidationError(self.error_messages["nonexistent"], code="nonexistent")
        if parsed is None:
            raise ValidationError(self.error_messages["invalid"], code="invalid")
        return parsed


class DateRangeForm(forms.Form):
    """
    The date range every report-shaped page filters by (REDESIGN_VISION
    4.8, 4.9, 4.10). Built once here because three modules use it and a
    fourth will; three copies would drift on what "this month" means.

    A GET form on purpose: the range belongs in the query string, so a
    range can be bookmarked and shared. Nothing about it is ever stored —
    the numbers it produces are always recomputed from the ledgers (2.9).

    "This week" and "this month" mean the JALALI week and month. A
    Gregorian month boundary would cut a Persian month in half and make
    every monthly total disagree with what the business actually counts.
    """

    class Preset(models.TextChoices):
        TODAY = "today", "امروز"
        WEEK = "week", "این هفته"
        MONTH = "month", "این ماه"
        CUSTOM = "custom", "بازهٔ دلخواه"

    preset = forms.ChoiceField(
        choices=Preset.choices,
        required=False,
        widget=forms.HiddenInput(),
    )
    start = JalaliDateField(required=False, label="از تاریخ")
    end = JalaliDateField(required=False, label="تا تاریخ")

    def clean(self):
        cleaned = super().clean()
        preset = cleaned.get("preset") or self.Preset.MONTH
        start = cleaned.get("start")
        end = cleaned.get("end")

        if preset == self.Preset.CUSTOM:
            # A custom range with nothing filled in is the user opening the
            # panel, not an error; fall back to the default rather than
            # shouting at them before they have typed anything.
            if not start and not end:
                preset = self.Preset.MONTH
            elif not start or not end:
                raise ValidationError("برای بازهٔ دلخواه، هر دو تاریخ لازم است.")
            elif start > end:
                raise ValidationError("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")

        if preset != self.Preset.CUSTOM:
            start, end = self.bounds_for(preset)

        cleaned["preset"] = preset
        cleaned["start"] = start
        cleaned["end"] = end
        return cleaned

    @staticmethod
    def bounds_for(preset):
        """The Gregorian dates a named preset covers, inclusive of both ends."""
        today = timezone.localdate()
        if preset == DateRangeForm.Preset.TODAY:
            return today, today
        if preset == DateRangeForm.Preset.WEEK:
            return dates.week_bounds(today)
        jalali_today = dates.today()
        return dates.month_bounds(jalali_today.year, jalali_today.month)

    @property
    def range(self):
        """
        (start, end) for this submission, falling back to the default when
        the form was never submitted or did not validate.

        A page should never have to handle "no range": there is always one,
        and a rejected custom range still shows its error beside a working
        page rather than an empty one.
        """
        if self.is_bound and self.is_valid():
            return self.cleaned_data["start"], self.cleaned_data["end"]
        return self.bounds_for(self.Preset.MONTH)

    @property
    def active_preset(self):
        """Which button should look pressed."""
        if self.is_bound and self.is_valid():
            return self.cleaned_data["preset"]
        if self.is_bound:
            return self.data.get("preset") or self.Preset.MONTH
        return self.Preset.MONTH
