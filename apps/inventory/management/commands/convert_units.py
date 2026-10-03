"""Convert carton-counted products to packs (D-081): `python manage.py convert_units [--map FILE] [--dry-run]`.

The map file is JSON, e.g. {"merge": {"CARTON-SKU": "PACK-SKU"}, "pack_per_carton": {"PACK-SKU": 5}}.
`merge` folds a carton product into the pack product that sells the same goods (never guessed: the owner
lists them after reading `inventory_unit_report`). Everything runs in one transaction and is checked against
the figures it started from; `--dry-run` does all of it and rolls back. Take a backup first on real data
(`manage.py backup_db`); a cost that does not divide evenly rounds to the nearest Toman and the drift is printed
(it is refused unless `--allow-rounding` is given).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.inventory.unit_conversion import ConversionError, convert


class Command(BaseCommand):
    help = "Rewrite carton products into packs, merging the ones listed in the map file."

    def add_arguments(self, parser):
        parser.add_argument("--map", help="JSON file with the merges and per-product packs per carton.")
        parser.add_argument("--dry-run", action="store_true", help="Do everything, print the result, change nothing.")
        parser.add_argument("--allow-rounding", action="store_true", help="Accept costs that do not divide evenly.")

    def handle(self, *args, **options):
        config = {}
        if options["map"]:
            try:
                config = json.loads(Path(options["map"]).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CommandError(f"map file unreadable: {exc}")
        try:
            result = convert(
                merge=config.get("merge"), pack_per_carton=config.get("pack_per_carton"), dry_run=True,
            )
            if result["uneven_costs"] and not options["allow_rounding"]:
                raise ConversionError(
                    f"costs not divisible by the packs per carton: {result['uneven_costs']} (use --allow-rounding to accept)"
                )
            if not options["dry_run"]:
                result = convert(merge=config.get("merge"), pack_per_carton=config.get("pack_per_carton"))
        except ConversionError as exc:
            raise CommandError(str(exc))
        self.stdout.write(f"inventory value drift: {result['value_drift']} Toman")
        self.stdout.write(f"cost of goods drift: {result['cost_of_goods_drift']} Toman")
        self.stdout.write(f"uneven costs rounded: {result['uneven_costs'] or 'none'}")
        self.stdout.write(self.style.SUCCESS("DRY RUN, nothing changed." if options["dry_run"] else "Converted."))
