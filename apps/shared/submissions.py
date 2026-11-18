from uuid import UUID

from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect

from .models import FinancialSubmission


class FinancialSubmissionMixin:
    """Reserve a form operation before its first financial write."""

    submission_success_status = 302

    def dispatch(self, request, *args, **kwargs):
        raw_token = request.POST.get("submission_id") if request.method == "POST" and request.user.is_authenticated else None
        if raw_token is None:
            return super().dispatch(request, *args, **kwargs)
        try:
            token = UUID(raw_token)
        except ValueError:
            return HttpResponseBadRequest("شناسهٔ عملیات نامعتبر است.")

        key = {"user": request.user, "path": request.path, "token": token}
        try:
            with transaction.atomic():
                submission = FinancialSubmission.objects.create(**key)
                response = super().dispatch(request, *args, **kwargs)
                if self.submission_succeeded(response):
                    submission.location = response.get("Location", "")
                    submission.save(update_fields=["location"])
                else:
                    transaction.set_rollback(True)
                return response
        except IntegrityError:
            previous = FinancialSubmission.objects.filter(**key).first()
            if previous is None:
                raise
            if previous.location:
                return redirect(previous.location)
            return HttpResponse('<p role="status">این پرداخت قبلاً ثبت شده است.</p>')

    def submission_succeeded(self, response):
        return response.status_code == self.submission_success_status
