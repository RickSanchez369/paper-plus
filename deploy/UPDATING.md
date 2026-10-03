# نصب و به‌روزرسانی روی هاست

این راهنما مستقل از نوع هاست نوشته شده (cPanel، DirectAdmin، پلسک، VPS). فقط اسم دکمه‌ها در پنل هاست فرق می‌کند.

## پیش‌نیازهای هاست (قبل از خرید بپرسید)
- پایتون ۳.۱۲ یا بالاتر (پروژه با ۳.۱۳ تست شده)
- پایگاه داده **PostgreSQL** (MySQL پشتیبانی نمی‌شود)
- امکان اجرای برنامهٔ پایتون (Setup Python App / Passenger / gunicorn) و دسترسی SSH یا ترمینال پنل

## نصب اول
1. کد پروژه را روی هاست بگذارید (`git clone` یا آپلود zip). پوشه‌های `media/`، `backups/` و فایل `.env` جزو کد نیستند.
2. محیط مجازی بسازید و وابستگی‌ها را نصب کنید:
   ```
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
3. فایل `.env` را از روی `.env.example` بسازید و پر کنید:
   - `SECRET_KEY` یک رشتهٔ تصادفی بلند
   - `DEBUG=False`
   - `ALLOWED_HOSTS=your-domain.ir`
   - `CSRF_TRUSTED_ORIGINS=https://your-domain.ir`
   - `DATABASE_URL=postgres://USER:PASSWORD@localhost:5432/DBNAME`
   - مشخصات شرکت برای فاکتور: `COMPANY_*`
4. جدول‌ها و فایل‌های استاتیک:
   ```
   .venv/bin/python manage.py update --no-backup
   .venv/bin/python manage.py createsuperuser
   ```
5. برنامه را در پنل هاست به `core.wsgi:application` وصل کنید. اگر هاست Passenger دارد، فایل `deploy/passenger_wsgi.py` را به ریشهٔ پروژه کپی کنید (با همین نام).
6. اگر HTTPS فعال است و هاست، پروکسی دارد، `SSL_REDIRECT=True` را هم بگذارید.

## هر بار که تغییری داده شد (به‌روزرسانی)
۱. کد جدید را روی هاست بگذارید (`git pull` یا آپلود جایگزین فایل‌ها). **این‌ها را جایگزین/حذف نکنید:** `.env`، `media/`، `backups/`.

۲. یک دستور:
```
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py update
```
این دستور به ترتیب: از اطلاعات پشتیبان می‌گیرد (داخل `backups/`)، تغییرات پایگاه داده را اعمال می‌کند، فایل‌های استاتیک را جمع می‌کند و تنظیمات را بررسی می‌کند.

۳. برنامه را ری‌استارت کنید: دکمهٔ Restart در پنل، یا برای Passenger: `touch tmp/restart.txt`.

اگر چیزی خراب شد: فایل `before-update-…zip` داخل `backups/` همان لحظهٔ قبل از به‌روزرسانی است (بازیابی در پایین).

## پشتیبان‌گیری
- از داخل برنامه: منوی «پشتیبان‌گیری» (برای همهٔ کاربران) ← «دانلود پشتیبان کامل»
- از ترمینال: `.venv/bin/python manage.py backup_db`
- پیشنهاد: هفته‌ای یک بار فایل را از هاست به کامپیوتر خودتان منتقل کنید و قدیمی‌ها را پاک کنید.

## بازیابی
روی یک پایگاه دادهٔ **خالی** که `migrate` خورده (و هیچ کاربری ندارد):
```
.venv/bin/python manage.py restore_db /path/to/paper-plus-backup-….zip
```
بازیابی روی پایگاه پر را خودش رد می‌کند تا دو تاریخچه قاطی نشوند.

## تنظیم مشخصات شرکت روی فاکتور
فقط کلیدهای `COMPANY_*` در `.env` را عوض کنید و برنامه را ری‌استارت کنید؛ نیازی به تغییر کد نیست. کلیدِ خالی = آن خط روی فاکتور چاپ نمی‌شود.

## یک‌بار بعد از به‌روزرسانیِ D-081 (کالای واحد با کارتن و بسته)
بعد از `manage.py update`، کالاهایی که تا حالا «کارتنی» ثبت شده بودند باید به بسته تبدیل شوند. هیچ ادغامی خودکار نیست.
```
.venv/bin/python manage.py inventory_unit_report
```
خروجی را بخوانید (فقط نمایش است). اگر کالای کارتنی و بسته‌ایِ یکسان دارید، یک فایل `map.json` بسازید:
```
{"merge": {"SKU-کارتنی": "SKU-بسته‌ای"}, "pack_per_carton": {"SKU-بسته‌ای": 5}}
```
اول آزمایشی (چیزی تغییر نمی‌کند)، بعد واقعی (قبلش `manage.py backup_db`):
```
.venv/bin/python manage.py convert_units --map map.json --dry-run
.venv/bin/python manage.py convert_units --map map.json
```
اگر بهای خرید بر تعداد بسته در کارتن بخش‌پذیر نباشد دستور رد می‌کند؛ با `--allow-rounding` پذیرفته می‌شود و اختلاف چاپ می‌شود.

## نرخ دلار (D-080)
یک cron job هر ۳ ساعت: `.venv/bin/python manage.py fetch_usd_rate`. اگر هاست اجازهٔ اتصال خروجی ندهد، دریافت ناموفق ثبت می‌شود و آخرین نرخ معتبر روی فاکتورها می‌ماند؛ دکمهٔ «بروزرسانی نرخ» هم در صفحهٔ انبار هست.
