from django.db import migrations

# The first real invoice number (D-022: a configurable start, set once).
FIRST_NUMBER = 9956001


def seed_sequences(apps, schema_editor):
    """Make sure one counter row exists per document type.

    `get_next_document_number` deliberately never creates the row, so a
    database without it (fresh install, or rows lost to a test teardown)
    turned the first confirmed invoice into a 500. Existing rows, with
    whatever counter they already reached, are left untouched.
    """
    DocumentSequence = apps.get_model("shared", "DocumentSequence")
    for doc_type in ("sale", "purchase"):
        DocumentSequence.objects.get_or_create(
            doc_type=doc_type, defaults={"next_number": FIRST_NUMBER}
        )


class Migration(migrations.Migration):

    dependencies = [
        ("shared", "0013_auditlog_change_selling_price"),
    ]

    operations = [
        migrations.RunPython(seed_sequences, migrations.RunPython.noop),
    ]
