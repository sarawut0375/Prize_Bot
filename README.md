# Price Bot — บอทสืบและเปรียบเทียบราคาสินค้า

เว็บแอปสำหรับใส่ข้อมูลสินค้าที่ต้องการติดตาม แล้วให้ระบบสืบราคาจากหลายแหล่ง
(Shopee, Lazada, Kaidee, Facebook Marketplace) มาเปรียบเทียบกันในหน้าเว็บ
พร้อมแจ้งเตือนทันทีผ่าน Telegram เมื่อราคาเปลี่ยนหรือถึงราคาเป้าหมาย

## ความสามารถ

- เพิ่มสินค้าที่ต้องการติดตาม พร้อมคำค้นหาและเลือกแหล่งที่จะสืบราคา
- ตั้งราคาเป้าหมาย (target price) และเลือกว่าจะแจ้งเตือนทุกครั้งที่ราคาเปลี่ยนหรือไม่
- ระบบสืบราคาอัตโนมัติตามรอบเวลาที่กำหนด (ตั้งค่าได้ใน `.env`) และกดรีเฟรชเองได้ทันที
- หน้าเว็บแสดงตารางเปรียบเทียบราคาล่าสุดจากทุกแหล่งของสินค้านั้น ๆ
- แจ้งเตือนผ่าน Telegram ทันทีเมื่อราคาต่ำสุดเปลี่ยนแปลง หรือถึงราคาเป้าหมาย
- เก็บประวัติราคาทุกครั้งที่สืบ ดูย้อนหลังได้ในหน้ารายละเอียดสินค้า

## ⚠️ ข้อจำกัดสำคัญเรื่องการสืบราคาแต่ละแหล่ง

| แหล่ง | สถานะ | หมายเหตุ |
|---|---|---|
| Kaidee | สืบอัตโนมัติ | ใช้ข้อมูลที่ฝังอยู่ในหน้าเว็บ อาจต้องแก้ selector ถ้าเว็บเปลี่ยนโครงสร้าง |
| Shopee | สืบอัตโนมัติ (best-effort) | ใช้ API ค้นหาสาธารณะของ Shopee เอง อาจถูกบล็อก/จำกัดจาก IP ของเซิร์ฟเวอร์ (anti-bot) |
| Lazada | สืบอัตโนมัติ (best-effort) | เช่นเดียวกับ Shopee อาจถูกจำกัดได้เช่นกัน |
| Facebook Marketplace | **ไม่มี API สาธารณะ และต้องล็อกอินเพื่อดูสินค้า** การสืบอัตโนมัติผ่าน Facebook ขัดกับ Terms of Service ของ Facebook จึงไม่ได้ทำให้ในโปรเจกต์นี้ | ใช้ฟอร์ม "เพิ่มราคาด้วยตนเอง" ในหน้ารายละเอียดสินค้าแทน ระบบจะเก็บและเปรียบเทียบราคานี้เหมือนแหล่งอื่น ๆ และยังแจ้งเตือนผ่าน Telegram ได้ปกติ |

ถ้า Shopee/Lazada เริ่มบล็อก ให้ลด `SCRAPE_INTERVAL_MINUTES` ให้ถี่น้อยลง หรือรันบอทจากเครื่อง/IP
บ้านของคุณเองแทนเซิร์ฟเวอร์คลาวด์ ดูรายละเอียดเพิ่มเติมในคอมเมนต์ของไฟล์
`app/scrapers/shopee.py` และ `app/scrapers/lazada.py`

## การติดตั้งและรัน (Windows)

```powershell
# 1. สร้างและเปิดใช้ virtual environment
python -m venv venv
venv\Scripts\activate

# 2. ติดตั้งไลบรารี
pip install -r requirements.txt

# 3. ตั้งค่า .env
copy .env.example .env
# แก้ TELEGRAM_BOT_TOKEN และ TELEGRAM_CHAT_ID ในไฟล์ .env (ดูวิธีได้มาในไฟล์นั้น)

# 4. รันเว็บแอป
python run.py
```

เปิดเบราว์เซอร์ไปที่ `http://localhost:8000`

## การติดตั้งและรัน (macOS / Linux)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

## ตั้งค่า Telegram Bot

1. เปิด Telegram คุยกับ `@BotFather` พิมพ์ `/newbot` แล้วทำตามขั้นตอน จะได้ token
2. ใส่ token ลงใน `.env` ที่ `TELEGRAM_BOT_TOKEN`
3. ส่งข้อความอะไรก็ได้ให้บอทของคุณ 1 ครั้งก่อน
4. เปิด `https://api.telegram.org/bot<TOKEN>/getUpdates` ในเบราว์เซอร์ จะเห็น
   `"chat":{"id": ...}` เอาเลขนั้นมาใส่ใน `.env` ที่ `TELEGRAM_CHAT_ID`

## โครงสร้างโปรเจกต์

```
app/
  main.py            FastAPI routes / หน้าเว็บ
  config.py          อ่านค่าตั้งค่าจาก .env
  database.py        เชื่อมต่อฐานข้อมูล SQLite
  models.py          โครงสร้างข้อมูล Product / PriceRecord
  price_checker.py   ตรรกะสืบราคา + ตัดสินใจแจ้งเตือน
  scheduler.py       รันงานตามรอบเวลา (APScheduler)
  telegram_notify.py ส่งข้อความแจ้งเตือนผ่าน Telegram
  scrapers/          โมดูลสืบราคาของแต่ละเว็บ (เพิ่ม/แก้ไขได้ที่นี่)
  templates/         หน้าเว็บ (Jinja2)
  static/            CSS
run.py               จุดเริ่มรันเว็บแอป
```

## แผนต่อยอด (ยังไม่ได้ทำ)

- เพิ่มกราฟราคาย้อนหลังในหน้ารายละเอียดสินค้า
- รองรับคำสั่งผ่าน Telegram (เช่น พิมพ์เพิ่มสินค้าจากแชทได้เลย)
- ใช้ Playwright/เบราว์เซอร์จริงสำหรับเว็บที่บล็อก request ธรรมดา (เพิ่ม robustness ให้ Shopee/Lazada)
- deploy ขึ้นเซิร์ฟเวอร์จริง (เช่น Railway, Render, VPS) ให้รันตลอดเวลา
