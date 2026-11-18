"""Backup page: access rules, download, and what is inside the zip (D-060).

The restore round trip needs an empty database, so it is a manual check
(tools/qa/README.md): migrate a scratch schema, run `restore_db`, compare counts.
"""
import io
import json
import zipfile

from django.apps import apps
from tools.qa.qa_lib import *


def scenarios(h):
    p = h.product(stock=5)
    sale = h.post_sale(h.customer(), [(p, 1, 1000)], account=h.account())
    check("BK00 the fixture sale is confirmed before backup", sale.status_code == 302)

    r = h.anon.get("/backup/")
    check("BK01 anonymous is sent to sign-in", r.status_code == 302 and "/login" in r["Location"])
    check("BK02 an ordinary user (not superuser) sees the page", h.cu.get("/backup/").status_code == 200)
    r = h.cu.post("/backup/")
    check("BK03 …and can download", r.status_code == 200 and r["Content-Type"] == "application/zip")
    check("BK04 anonymous cannot download", h.anon.post("/backup/").status_code == 302)

    r = h.c.get("/backup/")
    check("BK05 superuser sees the page", r.status_code == 200 and has(r, "دانلود پشتیبان کامل"))
    check("BK06 a GET never downloads (no attachment)", "attachment" not in r.get("Content-Disposition", ""))
    check("BK07 the menu shows the link to the superuser", has(h.c.get("/"), "/backup/"))
    check("BK08 …and to an ordinary user", has(h.cu.get("/"), "/backup/"))

    r = h.c.post("/backup/")
    check("BK09 POST returns a zip attachment", r.status_code == 200 and r["Content-Type"] == "application/zip"
          and "attachment" in r["Content-Disposition"] and ".zip" in r["Content-Disposition"])
    body = b"".join(r.streaming_content)
    z = zipfile.ZipFile(io.BytesIO(body))
    check("BK10 the zip is valid and has manifest + database", z.testzip() is None and {"manifest.json", "database.json"} <= set(z.namelist()))
    manifest = json.loads(z.read("manifest.json"))
    rows = json.loads(z.read("database.json"))
    check("BK11 manifest row counts add up to the rows in database.json", sum(manifest["rows"].values()) == len(rows))
    Sale = apps.get_model("sales", "SalesInvoice")
    check("BK12 the data includes the invoice just created", manifest["rows"].get("sales.salesinvoice") == Sale.objects.count())
    check("BK13 sessions / content types are not carried", not any(k.startswith(("sessions.", "contenttypes.")) for k in manifest["rows"]))


run("backup", scenarios)
