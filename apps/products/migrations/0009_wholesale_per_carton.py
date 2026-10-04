"""D-081: the wholesale price now means one whole carton, not one unit.

Only products counted in packs are converted here (their old wholesale price was per pack, so it becomes
that times `pack_per_carton`; a wholesale price that merely equalled retail was the "unset" marker and
becomes 0). Carton-counted products change meaning together with their stock, so `convert_units` handles them.
"""

from django.db import migrations


def to_carton_price(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    for product in Product.objects.filter(unit="بسته"):
        wholesale = product.wholesale_selling_price
        if wholesale > 0 and wholesale != product.default_selling_price:
            product.wholesale_selling_price = wholesale * product.pack_per_carton
        else:
            product.wholesale_selling_price = 0
        product.save(update_fields=["wholesale_selling_price"])


def to_unit_price(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    for product in Product.objects.filter(unit="بسته"):
        wholesale = product.wholesale_selling_price
        product.wholesale_selling_price = (
            wholesale // product.pack_per_carton if wholesale > 0 else product.default_selling_price
        )
        product.save(update_fields=["wholesale_selling_price"])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_carton_pack"),
    ]

    operations = [
        migrations.RunPython(to_carton_price, to_unit_price),
    ]
