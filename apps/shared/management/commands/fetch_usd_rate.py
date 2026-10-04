"""Read today's USD rate and store it: `python manage.py fetch_usd_rate` (run from a cron job, D-080).

Exit status is 1 when the attempt failed, so the cron log shows it; the failure is also stored
as a row (without a number) and the last valid rate stays in use.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.shared.exchange import fetch_usd_rate
from apps.shared.models import ExchangeRate


class Command(BaseCommand):
    help = "Fetch the USD rate from the configured source and store it."

    def handle(self, *args, **options):
        row = fetch_usd_rate()
        if row.status != ExchangeRate.Status.OK:
            raise CommandError(f"USD rate not fetched: {row.error}")
        self.stdout.write(self.style.SUCCESS(f"USD rate {row.rate} Toman from {row.source}"))
