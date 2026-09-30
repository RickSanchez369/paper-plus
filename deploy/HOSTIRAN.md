# راه‌اندازی روی هاست‌ایران (پلن فریم‌ورک، با SQLite)

این راهنما برای شاخهٔ `deploy` است: دیتابیس یک فایل SQLite است و به PostgreSQL نیازی نیست.
هر جا `USER` نوشته شده، نام کاربری cPanel شماست و `DOMAIN` دامنهٔ شما.

## ۰. پیش از شروع
- دامنه به هاست وصل باشد (nameserverها تنظیم شده) و گواهی SSL رایگان از پنل فعال شده باشد.
- فایل `paper-plus-deploy.zip` (خروجی `git archive` همین شاخه) را آماده داشته باشید.

## ۱. ساخت برنامه
cPanel ← **Setup Python App** ← **Create Application**
- Python version: **3.13** (اگر نبود ۳.۱۲)
- Application root: `paper-plus`
- Application URL: دامنهٔ شما
- Application startup file: `passenger_wsgi.py`
- Application Entry point: `application`
- دکمهٔ **Create**

بعد از ساخت، بالای صفحه یک دستور نشان می‌دهد که با `source .../activate` شروع می‌شود. آن را کپی کنید؛ در مرحلهٔ ۳ لازم است.

## ۲. بردن کد
File Manager ← پوشهٔ `paper-plus` (در خانهٔ `/home/USER/`، نه داخل `public_html`) ← **Upload** زیپ ← **Extract**.
اگر پرسید فایل `passenger_wsgi.py` جایگزین شود، بله.

## ۳. نصب کتابخانه‌ها (SSH یا ترمینال cPanel)
دستوری که در مرحلهٔ ۱ کپی کردید را اجرا کنید (وارد محیط مجازی و پوشهٔ برنامه می‌شود) و بعد:
```
pip install -r requirements.txt
mkdir -p data
```

## ۴. فایل `.env`
```
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
```
عدد چاپ‌شده را در `.env` جلوی `SECRET_KEY=` بگذارید و بقیه را این‌طور پر کنید (با `nano .env` یا ویرایشگر File Manager):
```
DEBUG=False
SECRET_KEY=<همان رشتهٔ تصادفی>
ALLOWED_HOSTS=DOMAIN,www.DOMAIN
CSRF_TRUSTED_ORIGINS=https://DOMAIN,https://www.DOMAIN
DATABASE_URL=sqlite:////home/USER/paper-plus/data/db.sqlite3
```
(چهار اسلش بعد از `sqlite:` درست است: یکی برای جداکننده و سه‌تا برای مسیر مطلق.)
بقیهٔ کلیدها (`COMPANY_*` برای سربرگ فاکتور) را هر وقت اطلاعات شرکت را داشتید پر کنید.

## ۵. ساخت جدول‌ها و کاربر مدیر
```
python manage.py update --no-backup
python manage.py createsuperuser
```
(شمارهٔ موبایل و رمز قوی بدهید. رمز را در چت نفرستید.)

## ۶. اجرا
Setup Python App ← **Restart** ← آدرس دامنه را باز کنید. صفحهٔ ورود باید بیاید.

اگر همه‌چیز درست بود، در `.env` بنویسید `SSL_REDIRECT=True` و دوباره Restart کنید (http خودکار به https می‌رود).

## عیب‌یابی
| نشانه | علت و راه‌حل |
|---|---|
| Incomplete response / 500 بدون توضیح | لاگ برنامه: Setup Python App ← لینک «stderr.log» یا `tmp/` پوشهٔ برنامه. معمولاً `.env` ناقص است |
| `DisallowedHost` | `ALLOWED_HOSTS` دامنه را ندارد |
| «CSRF verification failed» موقع ورود | `CSRF_TRUSTED_ORIGINS` باید `https://DOMAIN` باشد |
| صفحه بدون ظاهر (بدون CSS) | `python manage.py collectstatic --noinput` و Restart |
| `unable to open database file` | پوشهٔ `data` ساخته نشده یا مسیر `DATABASE_URL` غلط است |
| `database is locked` | نباید پیش بیاید؛ اگر آمد چند ثانیه صبر و دوباره تلاش کنید و به من خبر بدهید |
| حلقهٔ ریدایرکت بعد از `SSL_REDIRECT=True` | آن را به `False` برگردانید و Restart کنید |

## به‌روزرسانی‌های بعدی
۱. کد جدید (زیپ تازه یا `git pull`) را جایگزین کنید. `.env`، `data/`، `media/` و `backups/` را دست نزنید.
۲. در محیط مجازی:
```
pip install -r requirements.txt
python manage.py update
```
(قبل از هر تغییر دیتابیس، خودش بکاپ می‌گیرد.)
۳. Setup Python App ← Restart.

## بکاپ
منوی «پشتیبان‌گیری» داخل برنامه، یک فایل zip کامل می‌دهد. هفته‌ای یک‌بار آن را روی کامپیوتر خودتان نگه دارید. فایل `data/db.sqlite3` هم خودش یک نسخهٔ کامل است، ولی فقط وقتی بدون تغییر کپی شود که برنامه مشغول نوشتن نباشد؛ روش امن همان دکمهٔ بکاپ است.

## محدودیت‌های SQLite (بدانید)
- در هر لحظه فقط یک نفر می‌تواند ثبت کند؛ برای چند کاربر همزمان مشکلی نیست و درخواست‌ها پشت سر هم انجام می‌شوند.
- اگر بعداً به پلن پلاس (PostgreSQL) رفتید، فقط `DATABASE_URL` را عوض می‌کنید و بکاپ زیپ را با `restore_db` روی دیتابیس خالی بازیابی می‌کنید.
