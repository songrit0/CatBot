# 🤖 Discord Stock Bot 

Discord Bot สำหรับจัดการสต๊อกสินค้าด้วยการเชื่อมต่อ Google Sheets

## ✨ ฟีเจอร์

### 📝 คำสั่งพื้นฐาน
- `!add [ชื่อสินค้า] [จำนวน] [หน่วย]` - เพิ่มสินค้าเข้าสต๊อก
- `!remove [ชื่อสินค้า] [จำนวน]` - ลดสินค้าจากสต๊อก  
- `!check [ชื่อสินค้า]` - ตรวจสอบจำนวนสินค้า
- `!list` - แสดงรายการสินค้าทั้งหมด
- `!history` - แสดงประวัติการทำรายการ
- `!stock` - แสดงเมนูหลักพร้อมปุ่ม UI

### 🎯 ฟีเจอร์พิเศษ
- **UI แบบปุ่ม**: ใช้งานผ่านปุ่มได้อย่างสะดวก
- **แจ้งเตือนอัตโนมัติ**: แจ้งเตือนเมื่อสินค้าเหลือน้อยกว่า 5 ชิ้น
- **บันทึกประวัติ**: เก็บประวัติการทำรายการทั้งหมด
- **Google Sheets**: ข้อมูลสินค้าถูกเก็บใน Google Sheets แบบ Real-time

## 🚀 การติดตั้ง

### 1. ความต้องการของระบบ
- Python 3.8+
- Discord Bot Token
- Google Service Account Credentials

### 2. ตั้งค่า Google Sheets API

1. ไปที่ [Google Cloud Console](https://console.cloud.google.com/)
2. สร้างโปรเจกต์ใหม่หรือเลือกโปรเจกต์ที่มีอยู่
3. เปิดใช้งาน Google Sheets API และ Google Drive API
4. สร้าง Service Account:
   - ไปที่ IAM & Admin > Service Accounts
   - คลิก "Create Service Account"
   - ใส่ชื่อและคำอธิบาย
   - ใน Keys tab คลิก "Add Key" > "Create New Key" > "JSON"
   - ดาวน์โหลดไฟล์ JSON และเปลี่ยนชื่อเป็น `credentials.json`
5. แชร์ Google Sheets ให้กับ Service Account Email (ที่อยู่ในไฟล์ credentials.json)

### 3. ตั้งค่า Discord Bot

1. ไปที่ [Discord Developer Portal](https://discord.com/developers/applications)
2. สร้าง New Application
3. ไปที่ Bot section และสร้าง bot
4. คัดลอก Bot Token
5. ใน OAuth2 > URL Generator:
   - เลือก `bot` scope
   - เลือก permissions: `Send Messages`, `Use Slash Commands`, `Read Message History`
   - ใช้ URL ที่ได้เพื่อเชิญ bot เข้าเซิร์ฟเวอร์

### 4. ติดตั้งและรัน

```bash
# ติดตั้ง dependencies
pip install -r requirements.txt

# หรือใช้ script สำหรับ Windows
setup.bat

# รัน bot
python bot.py

# หรือใช้ script สำหรับ Windows  
run.bat
```

### 5. ตั้งค่า Environment Variables

แก้ไขไฟล์ `.env`:

```env
DISCORD_TOKEN="your_discord_bot_token_here"
GOOGLE_SHEETS_ID="your_google_sheets_id_here"
GOOGLE_SHEET_NAME="CatBot-Stock-Management"
```

**หมายเหตุ**: 
- `GOOGLE_SHEETS_ID` คือ ID ใน URL ของ Google Sheets
- ตัวอย่าง: `https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit`
- ID คือ: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`

## 📊 โครงสร้าง Google Sheets

Bot จะสร้างชีตอัตโนมัติ 2 ชีต:

### ชีต "Stock"
| ID | ชื่อสินค้า | จำนวน | หน่วย | วันที่อัปเดตล่าสุด |
|----|-----------|--------|-------|-------------------|
| 1  | ปากกา     | 10     | ด้าม  | 2025-01-01 10:00  |

### ชีต "History"  
| วันที่ | ชื่อผู้ใช้ | การทำรายการ | ชื่อสินค้า | จำนวน | หมายเหตุ |
|--------|-----------|-------------|-----------|--------|----------|
| 2025-01-01 | User#1234 | เพิ่มสินค้า | ปากกา | 10 | หน่วย: ด้าม |

## 🎮 การใช้งาน

### ตัวอย่างคำสั่ง

```
!add ปากกา 10 ด้าม          # เพิ่มปากกา 10 ด้าม
!remove ปากกา 2             # ลดปากกา 2 ด้าม  
!check ปากกา                # ตรวจสอบจำนวนปากกา
!list                       # ดูรายการสินค้าทั้งหมด
!history                    # ดูประวัติการทำรายการ
!stock                      # เมนูหลักพร้อมปุ่ม UI
!help                       # ดูคำสั่งทั้งหมด
```

### ปุ่ม UI

เมื่อใช้คำสั่ง `!stock` จะแสดงปุ่ม:
- 📦 **รายการสินค้า**: ดูสินค้าทั้งหมด
- 📋 **ประวัติ**: ดูประวัติการทำรายการ
- ⚠️ **สินค้าใกล้หมด**: ดูสินค้าที่เหลือน้อย

## ⚙️ การตั้งค่า

### เปลี่ยนค่าแจ้งเตือน
แก้ไขไฟล์ `bot.py` บรรทัดที่ 20:
```python
LOW_STOCK_THRESHOLD = 5  # เปลี่ยนเป็นจำนวนที่ต้องการ
```

### ตั้งค่าช่วงเวลาแจ้งเตือน
แก้ไขไฟล์ `bot.py` บรรทัดที่ 235:
```python
await asyncio.sleep(1800)  # 1800 วินาที = 30 นาที
```

## 🔧 Troubleshooting

### ปัญหาทั่วไป

1. **Bot ไม่ตอบสนอง**
   - ตรวจสอบ Discord Token
   - ตรวจสอบ permissions ของ bot

2. **ไม่สามารถเชื่อมต่อ Google Sheets**
   - ตรวจสอบไฟล์ `credentials.json`
   - ตรวจสอบการแชร์ Google Sheets
   - ตรวจสอบ `GOOGLE_SHEETS_ID`

3. **แจ้งเตือนไม่ทำงาน**
   - ตรวจสอบชื่อช่อง (general, stock, แจ้งเตือน)
   - ตรวจสอบ permissions ของ bot

### ไฟล์ Log

Bot จะแสดงข้อความ log ใน console:
- ✅ สำเร็จ
- ❌ ข้อผิดพลาด
- 🔗 การเชื่อมต่อ

## 📝 License

MIT License

## 🙏 Credits

สร้างโดย MARU
- Discord.py
- Google Sheets API
- Python-dotenv

---

**หมายเหตุ**: อย่าลืมเก็บ Discord Token และ Google Credentials ให้ปลอดภัย!
