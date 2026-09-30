# Reason: D-027 defines Owner vs Seller permission scope. This data
# migration seeds the two auth Groups so admin visibility and CRUD
# follow the roles, instead of being configured by hand in the UI.
from django.db import migrations


def get_perms(apps, model_label, codenames):
    """Return Permission objects for app_label.ModelName matching codenames."""
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    app_label, model_name = model_label.split(".")
    ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
    return list(Permission.objects.filter(content_type=ct, codename__in=codenames))


def seed_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # On a brand-new database the content types/permissions do not exist yet
    # (Django creates them after migrate finishes), so there is nothing to
    # attach. The roles were retired with the single-business rebuild anyway,
    # so a fresh install simply skips this seed.
    if not ContentType.objects.filter(app_label="sales", model="salesinvoice").exists():
        return

    seller_perms = []
    seller_perms += get_perms(apps, "products.Product", ["view_product"])
    seller_perms += get_perms(apps, "partners.Customer", ["view_customer"])
    seller_perms += get_perms(
        apps, "sales.SalesInvoice",
        ["add_salesinvoice", "view_salesinvoice", "change_salesinvoice"],
    )
    seller_perms += get_perms(
        apps, "sales.SaleItem",
        ["add_saleitem", "view_saleitem", "change_saleitem"],
    )
    seller_perms += get_perms(apps, "inventory.InventoryMovement", ["view_inventorymovement"])

    owner_perms = []
    owner_perms += get_perms(apps, "products.Product", ["add_product", "view_product", "change_product"])
    owner_perms += get_perms(apps, "partners.Customer", ["add_customer", "view_customer", "change_customer"])
    owner_perms += get_perms(apps, "partners.Supplier", ["add_supplier", "view_supplier", "change_supplier"])
    owner_perms += get_perms(
        apps, "sales.SalesInvoice",
        ["add_salesinvoice", "view_salesinvoice", "change_salesinvoice", "delete_salesinvoice"],
    )
    owner_perms += get_perms(
        apps, "sales.SaleItem",
        ["add_saleitem", "view_saleitem", "change_saleitem", "delete_saleitem"],
    )
    owner_perms += get_perms(
        apps, "purchasing.PurchaseInvoice",
        ["add_purchaseinvoice", "view_purchaseinvoice", "change_purchaseinvoice", "delete_purchaseinvoice"],
    )
    owner_perms += get_perms(
        apps, "purchasing.PurchaseItem",
        ["add_purchaseitem", "view_purchaseitem", "change_purchaseitem", "delete_purchaseitem"],
    )
    owner_perms += get_perms(apps, "inventory.InventoryMovement", ["view_inventorymovement"])
    owner_perms += get_perms(
        apps, "shared.BusinessMembership",
        ["add_businessmembership", "view_businessmembership", "change_businessmembership"],
    )
    owner_perms += get_perms(apps, "users.User", ["view_user"])

    seller_group, _ = Group.objects.get_or_create(name="Seller")
    seller_group.permissions.set(seller_perms)

    owner_group, _ = Group.objects.get_or_create(name="Owner")
    owner_group.permissions.set(owner_perms)


def unseed_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Owner", "Seller"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("shared", "0002_businessmembership"),
        ("products", "0002_product_is_onboarded"),
        ("partners", "0001_initial"),
        ("sales", "0001_initial"),
        ("purchasing", "0001_initial"),
        ("inventory", "0001_initial"),
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_groups, unseed_groups),
    ]