# 🚀 Quick Start Guide - Discord Stock Bot

## ขั้นตอนการติดตั้งอย่างรวดเร็ว

### 1. ดาวน์โหลด Dependencies
```bash
pip install -r requirements.txt
```

### 2. ตั้งค่า Google Sheets API

#### a. สร้าง Google Cloud Project
1. ไปที่ [Google Cloud Console](https://console.cloud.google.com/)
2. สร้าง Project ใหม่
3. เปิดใช้งาน Google Sheets API และ Google Drive API

#### b. สร้าง Service Account
1. ไปที่ IAM & Admin > Service Accounts
2. สร้าง Service Account ใหม่
3. ดาวน์โหลด JSON Key และเปลี่ยนชื่อเป็น `credentials.json`
4. วางไฟล์ใน folder โปรเจกต์

#### c. สร้าง Google Sheets
1. สร้าง Google Sheets ใหม่
2. แชร์ให้กับ Service Account Email (ใน credentials.json)
3. คัดลอก Sheets ID จาก URL

### 3. ตั้งค่า Discord Bot

#### a. สร้าง Discord Application
1. ไปที่ [Discord Developer Portal](https://discord.com/developers/applications)
2. สร้าง New Application
3. ไปที่ Bot > Create Bot
4. คัดลอก Bot Token

#### b. เชิญ Bot เข้าเซิร์ฟเวอร์
1. ไปที่ OAuth2 > URL Generator
2. เลือก `bot` scope
3. เลือก permissions: `Send Messages`, `Use Slash Commands`, `Read Message History`
4. ใช้ URL ที่ได้เชิญ bot

### 4. ตั้งค่า Environment Variables

แก้ไขไฟล์ `.env`:
```env
DISCORD_TOKEN="your_bot_token_here"
GOOGLE_SHEETS_ID="your_sheets_id_here"
GOOGLE_SHEET_NAME="CatBot-Stock-Management"
```

### 5. รัน Bot
```bash
python bot.py
```

## 🎯 การใช้งานพื้นฐาน

### คำสั่งหลัก
- `!stock` - เมนูหลักพร้อมปุ่ม UI
- `!add ปากกา 10 ด้าม` - เพิ่มสินค้า
- `!remove ปากกา 2` - ลดสินค้า
- `!check ปากกา` - ตรวจสอบสินค้า
- `!list` - รายการสินค้าทั้งหมด
- `!history` - ประวัติการทำรายการ

### ฟีเจอร์พิเศษ
- **UI แบบปุ่ม**: ใช้งานง่าย ไม่ต้องจำคำสั่ง
- **Modal Forms**: กรอกข้อมูลผ่าน popup
- **Dropdown Menu**: เลือกสินค้าจาก dropdown
- **แจ้งเตือนอัตโนมัติ**: เมื่อสินค้าเหลือน้อย
- **Real-time Sync**: ข้อมูลอัปเดตทันทีใน Google Sheets

## 🔧 Troubleshooting

### ปัญหาที่พบบ่อย

1. **ModuleNotFoundError**
   ```bash
   pip install -r requirements.txt
   ```

2. **Google Sheets ไม่เชื่อมต่อ**
   - ตรวจสอบไฟล์ `credentials.json`
   - ตรวจสอบการแชร์ Google Sheets
   - ตรวจสอบ API permissions

3. **Bot ไม่ตอบสนอง**
   - ตรวจสอบ Discord Token
   - ตรวจสอบ Bot permissions
   - ตรวจสอบ Internet connection

### Command Line Tools (Windows)
```bash
# ติดตั้ง
setup.bat

# รัน bot
run.bat
```

## 📱 Demo การใช้งาน

1. พิมพ์ `!stock` ใน Discord
2. คลิกปุ่ม "➕ เพิ่มสินค้า"
3. กรอกข้อมูลใน popup form
4. ดูผลลัพธ์ใน Google Sheets

## 🎨 การปรับแต่ง

### เปลี่ยนสีธีม
ในไฟล์ `ui_components.py`:
```python
color=0x3498db  # เปลี่ยนเป็นสีที่ต้องการ
```

### เปลี่ยนค่าแจ้งเตือน
ในไฟล์ `bot.py`:
```python
LOW_STOCK_THRESHOLD = 5  # เปลี่ยนเป็นค่าที่ต้องการ
```

### เพิ่มฟีเจอร์
ดูตัวอย่างใน `ui_components.py` สำหรับการสร้าง UI components เพิ่มเติม

---

**🎉 ขอให้สนุกกับการใช้งาน Discord Stock Bot!**
