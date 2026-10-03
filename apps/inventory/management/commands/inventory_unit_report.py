"""Read-only report for the pack/carton conversion (D-081): `python manage.py inventory_unit_report`.

Lists every product (unit, stock, layers, prices), the carton products whose cost does not divide evenly by
the packs per carton, and likely pack/carton pairs. Writes nothing: show it to the owner, who then writes the
merge map for `convert_units`.
"""

from django.core.management.base import BaseCommand

from apps.inventory.unit_conversion import report


class Command(BaseCommand):
    help = "Show how products would convert to packs, and which look like the same goods. Changes nothing."

    def handle(self, *args, **options):
        data = report()
        self.stdout.write("== products (sku | name | unit | per carton | stock | layers (left, cost) | retail | wholesale)")
        for r in data["products"]:
            flags = []
            if not r["active"]:
                flags.append("inactive")
            if r["uneven_costs"]:
                flags.append(f"cost not divisible by {r['pack_per_carton']}: {r['uneven_costs']}")
            self.stdout.write(
                f"{r['sku']} | {r['name']} | {r['unit']} | {r['pack_per_carton']} | {r['stock']} | {r['layers']} | "
                f"{r['retail']} | {r['wholesale']}" + (f"   <-- {'; '.join(flags)}" if flags else "")
            )
        self.stdout.write("== carton products that look like the same goods as a pack product")
        if not data["candidate_pairs"]:
            self.stdout.write("none")
        for pair in data["candidate_pairs"]:
            note = "" if not pair["invoices_with_both"] else f"   <-- {pair['invoices_with_both']} invoice(s) carry both: cannot merge"
            self.stdout.write(f"{pair['carton']} -> {pair['pack']}  ({pair['name']}){note}")
        self.stdout.write("Write the pairs you confirm into a map file and run convert_units --dry-run first.")
