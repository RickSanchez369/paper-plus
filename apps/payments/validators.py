# path: apps/payments/validators.py

"""Validation for uploaded expense receipts.

A receipt is a picture or a PDF and nothing else. Anything the browser could
run as a page (.html, .svg, ...) is refused, and the file's first bytes must
match what its extension claims, so renaming `x.html` to `x.pdf` does not
get it through.
"""

from django.core.exceptions import ValidationError

MAX_BYTES = 5 * 1024 * 1024

# extension -> a check on the file's leading bytes
_SIGNATURES = {
    ".pdf": lambda head: head.startswith(b"%PDF"),
    ".png": lambda head: head.startswith(b"\x89PNG\r\n\x1a\n"),
    ".jpg": lambda head: head.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda head: head.startswith(b"\xff\xd8\xff"),
    ".webp": lambda head: head[:4] == b"RIFF" and head[8:12] == b"WEBP",
}


def validate_receipt(upload):
    """Accept only a small PDF/PNG/JPEG/WebP whose content matches its extension."""
    name = (getattr(upload, "name", "") or "").lower()
    extension = name[name.rfind("."):] if "." in name else ""
    if extension not in _SIGNATURES:
        raise ValidationError("فقط فایل PDF یا تصویر (PNG، JPG، WebP) پذیرفته می‌شود.")
    if upload.size == 0:
        raise ValidationError("فایل خالی است.")
    if upload.size > MAX_BYTES:
        raise ValidationError("حجم فایل نباید بیشتر از ۵ مگابایت باشد.")
    position = upload.tell() if hasattr(upload, "tell") else 0
    upload.seek(0)
    head = upload.read(16)
    upload.seek(position)
    if not _SIGNATURES[extension](head):
        raise ValidationError("محتوای فایل با پسوند آن نمی‌خواند.")
