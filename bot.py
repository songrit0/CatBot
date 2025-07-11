import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
import asyncio
import json
import os
from datetime import datetime
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials
from ui.views.product_card_view import ProductCardView
from ui_components import *

# ฟังก์ชันช่วยสำหรับการลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย
async def remove_seller_permission(ctx, seller_user):
    """ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย"""
    try:
        # ตรวจสอบว่าเป็นห้องที่สามารถจัดการสิทธิ์ได้
        if isinstance(ctx.channel, discord.TextChannel):
            # ลบสิทธิ์ของผู้ขายออกจากห้องนี้
            overwrite = discord.PermissionOverwrite()
            overwrite.view_channel = False
            overwrite.send_messages = False
            overwrite.read_message_history = False
            
            await ctx.channel.set_permissions(seller_user, overwrite=overwrite)
            
            # ส่งข้อความแจ้งเตือนในช่อง (ถ้าจำเป็น)
            try:
                embed = discord.Embed(
                    title="🔒 ห้องถูกปิดการเข้าถึง",
                    description=f"สิทธิ์การเข้าถึงของ {seller_user.mention} ถูกลบออกจากห้องนี้หลังจากการขายเสร็จสิ้น",
                    color=0xff6b6b
                )
                embed.add_field(
                    name="📝 หมายเหตุ",
                    value="นี่เป็นการดำเนินการอัตโนมัติหลังจากแสดงใบเสร็จการขาย",
                    inline=False
                )
                await ctx.send(embed=embed)
            except:
                pass  # ถ้าไม่สามารถส่งข้อความได้ก็ข้าม
            
            print(f"✅ ลบสิทธิ์ผู้ขาย {seller_user.name} ({seller_user.id}) ออกจากห้อง {ctx.channel.name} ({ctx.channel.id}) เรียบร้อยแล้ว")
            
        else:
            print(f"❌ ไม่สามารถลบสิทธิ์ได้: ห้องนี้ไม่ใช่ TextChannel")
            
    except discord.Forbidden:
        print(f"❌ ไม่มีสิทธิ์ในการจัดการสิทธิ์ของห้อง {ctx.channel.name}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการลบสิทธิ์: {e}")

# โหลด environment variables
load_dotenv()

# ตั้งค่า Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# ตั้งค่า Google Sheets
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

# ตั้งค่าการแจ้งเตือน
LOW_STOCK_THRESHOLD = 5

# Dictionary เก็บข้อมูลผู้ใช้ที่กำลังรอการอัปโหลดรูป
pending_image_uploads = {}

# Dictionary เก็บข้อมูลการขายที่กำลังดำเนินการ
active_sales = {}

# Dictionary เก็บช่องแชทการขายสำหรับแต่ละผู้ใช้
sales_channels = {}

# ID ของช่องประวัติบิล
BILL_HISTORY_CHANNEL_ID = 1393184006748635156

class StockManager:
    def __init__(self):
        self.credentials = None
        self.gc = None
        self.spreadsheet = None
        self.setup_google_sheets()
    
    def setup_google_sheets(self):
        """ตั้งค่าการเชื่อมต่อ Google Sheets"""
        try:
            # ใช้ credentials.json file
            if os.path.exists('credentials.json'):
                self.credentials = Credentials.from_service_account_file(
                    'credentials.json', scopes=SCOPE)
            else:
                print("❌ ไม่พบไฟล์ credentials.json")
                return
            
            self.gc = gspread.authorize(self.credentials)
            
            # เปิด Google Sheets
            sheets_id = os.getenv('GOOGLE_SHEETS_ID')
            if sheets_id:
                self.spreadsheet = self.gc.open_by_key(sheets_id)
            else:
                sheet_name = os.getenv('GOOGLE_SHEET_NAME', 'CatBot-Stock-Management')
                self.spreadsheet = self.gc.open(sheet_name)
            
            # สร้างชีตหากยังไม่มี
            self.setup_sheets()
            print("✅ เชื่อมต่อ Google Sheets สำเร็จ")
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {e}")
    
    async def upload_image_to_drive(self, image_url, filename):
        """ใช้ Discord CDN สำหรับเก็บรูปภาพ"""
        try:
            # ตรวจสอบว่า URL เป็นรูปภาพจาก Discord หรือไม่
            if "cdn.discordapp.com" in image_url or "media.discordapp.net" in image_url:
                print(f"✅ ใช้ Discord CDN สำหรับรูปภาพ: {filename}")
                return image_url
            else:
                print(f"⚠️ URL ไม่ใช่ Discord CDN: {image_url}")
                return image_url
                
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการจัดการรูปภาพ: {e}")
            return image_url
    
    def setup_sheets(self):
        """สร้างชีตและตั้งค่าหัวตาราง"""
        try:
            # ตรวจสอบและสร้างชีต Stock
            try:
                stock_sheet = self.spreadsheet.worksheet('Stock')
                print("✅ พบชีต Stock แล้ว")
                
                # ตรวจสอบว่าชีตมีหัวตารางหรือไม่
                try:
                    first_row = stock_sheet.row_values(1)
                    if not first_row or len(first_row) < 8 or first_row[0] != 'ID':
                        print("⚠️ หัวตารางของชีต Stock ไม่ถูกต้อง กำลังแก้ไข...")
                        stock_sheet.update(
                            range_name='A1:H1',
                            values=[['ID', 'ชื่อสินค้า', 'จำนวน', 'หน่วย', 'ราคา', 'คำอธิบาย', 'รูปภาพURL', 'วันที่อัปเดตล่าสุด']]
                        )
                        print("✅ แก้ไขหัวตารางชีต Stock เรียบร้อย")
                except Exception as e:
                    print(f"⚠️ ไม่สามารถตรวจสอบหัวตารางชีต Stock ได้: {e}")
                    
            except gspread.WorksheetNotFound:
                print("⚠️ ไม่พบชีต Stock กำลังสร้างใหม่...")
                stock_sheet = self.spreadsheet.add_worksheet(title='Stock', rows=1000, cols=8)
                # ตั้งค่าหัวตาราง
                stock_sheet.update(
                    range_name='A1:H1',
                    values=[['ID', 'ชื่อสินค้า', 'จำนวน', 'หน่วย', 'ราคา', 'คำอธิบาย', 'รูปภาพURL', 'วันที่อัปเดตล่าสุด']]
                )
                print("✅ สร้างชีต Stock เรียบร้อย")
            
            # ตรวจสอบและสร้างชีต History
            try:
                history_sheet = self.spreadsheet.worksheet('History')
                print("✅ พบชีต History แล้ว")
                
                # ตรวจสอบว่าชีตมีหัวตารางหรือไม่
                try:
                    first_row = history_sheet.row_values(1)
                    if not first_row or len(first_row) < 6 or first_row[0] != 'วันที่':
                        print("⚠️ หัวตารางของชีต History ไม่ถูกต้อง กำลังแก้ไข...")
                        history_sheet.update(
                            range_name='A1:F1',
                            values=[['วันที่', 'ชื่อผู้ใช้', 'การทำรายการ', 'ชื่อสินค้า', 'จำนวน', 'หมายเหตุ']]
                        )
                        print("✅ แก้ไขหัวตารางชีต History เรียบร้อย")
                except Exception as e:
                    print(f"⚠️ ไม่สามารถตรวจสอบหัวตารางชีต History ได้: {e}")
                    
            except gspread.WorksheetNotFound:
                print("⚠️ ไม่พบชีต History กำลังสร้างใหม่...")
                history_sheet = self.spreadsheet.add_worksheet(title='History', rows=1000, cols=6)
                # ตั้งค่าหัวตาราง
                history_sheet.update(
                    range_name='A1:F1',
                    values=[['วันที่', 'ชื่อผู้ใช้', 'การทำรายการ', 'ชื่อสินค้า', 'จำนวน', 'หมายเหตุ']]
                )
                print("✅ สร้างชีต History เรียบร้อย")
            
            # ตรวจสอบและสร้างชีต Bills (ใบเสร็จ)
            try:
                bills_sheet = self.spreadsheet.worksheet('Bills')
                print("✅ พบชีต Bills แล้ว")
                
                # ตรวจสอบว่าชีตมีหัวตารางหรือไม่
                try:
                    first_row = bills_sheet.row_values(1)
                    if not first_row or len(first_row) < 10 or first_row[0] != 'เลขที่ใบเสร็จ':
                        print("⚠️ หัวตารางของชีต Bills ไม่ถูกต้อง กำลังแก้ไข...")
                        bills_sheet.update(
                            range_name='A1:J1',
                            values=[['เลขที่ใบเสร็จ', 'วันที่', 'ผู้ขาย', 'ชื่อสินค้า', 'จำนวน', 'หน่วย', 'ราคาต่อหน่วย', 'ราคารวม', 'ยอดรวม', 'หมายเหตุ']]
                        )
                        print("✅ แก้ไขหัวตารางชีต Bills เรียบร้อย")
                except Exception as e:
                    print(f"⚠️ ไม่สามารถตรวจสอบหัวตารางชีต Bills ได้: {e}")
                    
            except gspread.WorksheetNotFound:
                print("⚠️ ไม่พบชีต Bills กำลังสร้างใหม่...")
                bills_sheet = self.spreadsheet.add_worksheet(title='Bills', rows=1000, cols=10)
                # ตั้งค่าหัวตาราง
                bills_sheet.update(
                    range_name='A1:J1',
                    values=[['เลขที่ใบเสร็จ', 'วันที่', 'ผู้ขาย', 'ชื่อสินค้า', 'จำนวน', 'หน่วย', 'ราคาต่อหน่วย', 'ราคารวม', 'ยอดรวม', 'หมายเหตุ']]
                )
                print("✅ สร้างชีต Bills เรียบร้อย")
                
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการสร้างชีต: {e}")
    
    def add_stock(self, product_name, quantity, unit, user, price=0, description="", image_url=""):
        """เพิ่มสินค้าเข้าสต๊อก"""
        try:
            stock_sheet = self.spreadsheet.worksheet('Stock')
            
            # ตรวจสอบว่าชีตมีข้อมูลหรือไม่
            try:
                existing_products = stock_sheet.get_all_records()
            except Exception as e:
                print(f"⚠️ ไม่สามารถอ่านข้อมูลจากชีตได้: {e}")
                existing_products = []
            
            # ตรวจสอบว่าชีตมีหัวตารางหรือไม่
            if not existing_products:
                # ตรวจสอบว่าแถวแรกมีหัวตารางหรือไม่
                try:
                    first_row = stock_sheet.row_values(1)
                    if not first_row or first_row[0] != 'ID':
                        # ตั้งค่าหัวตารางใหม่
                        stock_sheet.clear()
                        stock_sheet.update(
                            range_name='A1:H1',
                            values=[['ID', 'ชื่อสินค้า', 'จำนวน', 'หน่วย', 'ราคา', 'คำอธิบาย', 'รูปภาพURL', 'วันที่อัปเดตล่าสุด']]
                        )
                        print("✅ ตั้งค่าหัวตารางใหม่สำเร็จ")
                except Exception as e:
                    print(f"⚠️ ไม่สามารถตั้งค่าหัวตารางได้: {e}")
                    return False
            
            # ค้นหาสินค้าที่มีอยู่
            product_found = False
            
            for i, product in enumerate(existing_products):
                try:
                    if product.get('ชื่อสินค้า', '').lower() == product_name.lower():
                        # อัปเดตจำนวนสินค้าที่มีอยู่
                        current_quantity = int(product.get('จำนวน', 0))
                        new_quantity = current_quantity + int(quantity)
                        
                        # อัปเดตข้อมูลในชีต
                        row_number = i + 2  # +2 เพราะเริ่มจากแถวที่ 2 (แถว 1 เป็นหัวตาราง)
                        stock_sheet.update(f'C{row_number}', new_quantity)
                        stock_sheet.update(f'H{row_number}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        
                        # อัปเดตข้อมูลอื่นๆ ถ้ามีการใส่ข้อมูลใหม่
                        if price > 0:
                            stock_sheet.update(f'E{row_number}', price)
                        if description:
                            stock_sheet.update(f'F{row_number}', description)
                        if image_url:
                            stock_sheet.update(f'G{row_number}', image_url)
                        
                        product_found = True
                        print(f"✅ อัปเดตสินค้า {product_name} สำเร็จ")
                        break
                except Exception as e:
                    print(f"⚠️ เกิดข้อผิดพลาดในการอัปเดตสินค้า: {e}")
                    continue
            
            if not product_found:
                try:
                    # เพิ่มสินค้าใหม่
                    next_row = len(existing_products) + 2
                    new_id = len(existing_products) + 1
                    
                    stock_sheet.update(
                        range_name=f'A{next_row}:H{next_row}',
                        values=[[
                            new_id,
                            product_name,
                            quantity,
                            unit,
                            price,
                            description,
                            image_url,
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        ]]
                    )
                    print(f"✅ เพิ่มสินค้าใหม่ {product_name} สำเร็จ")
                except Exception as e:
                    print(f"⚠️ เกิดข้อผิดพลาดในการเพิ่มสินค้าใหม่: {e}")
                    return False
            
            # บันทึกประวัติ
            try:
                self.add_history(user, 'เพิ่มสินค้า', product_name, quantity, f'หน่วย: {unit}, ราคา: {price}')
            except Exception as e:
                print(f"⚠️ เกิดข้อผิดพลาดในการบันทึกประวัติ: {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการเพิ่มสินค้า: {e}")
            return False
    
    def remove_stock(self, product_name, quantity, user):
        """ลดสินค้าจากสต๊อก"""
        try:
            stock_sheet = self.spreadsheet.worksheet('Stock')
            existing_products = stock_sheet.get_all_records()
            
            for i, product in enumerate(existing_products):
                if product['ชื่อสินค้า'].lower() == product_name.lower():
                    current_quantity = int(product['จำนวน'])
                    new_quantity = max(0, current_quantity - int(quantity))
                    
                    stock_sheet.update(f'C{i+2}', new_quantity)
                    stock_sheet.update(f'H{i+2}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
                    # บันทึกประวัติ
                    self.add_history(user, 'ลดสินค้า', product_name, quantity, f'คงเหลือ: {new_quantity}')
                    
                    return True, new_quantity
            
            return False, 0
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการลดสินค้า: {e}")
            return False, 0
    
    def check_stock(self, product_name):
        """ตรวจสอบจำนวนสินค้า"""
        try:
            stock_sheet = self.spreadsheet.worksheet('Stock')
            existing_products = stock_sheet.get_all_records()
            
            for product in existing_products:
                if product['ชื่อสินค้า'].lower() == product_name.lower():
                    return product
            
            return None
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการตรวจสอบสินค้า: {e}")
            return None
    
    def get_all_stock(self):
        """ดึงรายการสินค้าทั้งหมด"""
        try:
            stock_sheet = self.spreadsheet.worksheet('Stock')
            return stock_sheet.get_all_records()
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการดึงรายการสินค้า: {e}")
            return []
    
    def get_history(self, limit=10):
        """ดึงประวัติการทำรายการ"""
        try:
            history_sheet = self.spreadsheet.worksheet('History')
            records = history_sheet.get_all_records()
            return records[-limit:] if len(records) > limit else records
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการดึงประวัติ: {e}")
            return []
    
    def add_history(self, user, action, product_name, quantity, note):
        """เพิ่มประวัติการทำรายการ"""
        try:
            history_sheet = self.spreadsheet.worksheet('History')
            
            # ตรวจสอบว่าชีตมีข้อมูลหรือไม่
            try:
                existing_records = history_sheet.get_all_records()
                next_row = len(existing_records) + 2
            except Exception as e:
                print(f"⚠️ ไม่สามารถอ่านข้อมูลจากชีต History ได้: {e}")
                # ตรวจสอบว่าชีตมีหัวตารางหรือไม่
                try:
                    first_row = history_sheet.row_values(1)
                    if not first_row or first_row[0] != 'วันที่':
                        # ตั้งค่าหัวตารางใหม่
                        history_sheet.clear()
                        history_sheet.update(
                            range_name='A1:F1',
                            values=[['วันที่', 'ชื่อผู้ใช้', 'การทำรายการ', 'ชื่อสินค้า', 'จำนวน', 'หมายเหตุ']]
                        )
                        next_row = 2
                    else:
                        next_row = 2
                except Exception as e2:
                    print(f"⚠️ ไม่สามารถตั้งค่าหัวตาราง History ได้: {e2}")
                    return
            
            # เพิ่มข้อมูลใหม่
            history_sheet.update(
                range_name=f'A{next_row}:F{next_row}',
                values=[[
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    str(user),
                    action,
                    product_name,
                    quantity,
                    note
                ]]
            )
            print(f"✅ บันทึกประวัติสำเร็จ: {action} {product_name}")
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการเพิ่มประวัติ: {e}")
    
    def check_low_stock(self):
        """ตรวจสอบสินค้าที่มีจำนวนต่ำ"""
        try:
            stock_sheet = self.spreadsheet.worksheet('Stock')
            existing_products = stock_sheet.get_all_records()
            
            low_stock_items = []
            for product in existing_products:
                if int(product['จำนวน']) < LOW_STOCK_THRESHOLD:
                    low_stock_items.append(product)
            
            return low_stock_items
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการตรวจสอบสินค้าต่ำ: {e}")
            return []
    
    def generate_bill_number(self):
        """สร้างเลขที่ใบเสร็จ"""
        try:
            bills_sheet = self.spreadsheet.worksheet('Bills')
            records = bills_sheet.get_all_records()
            
            # สร้างเลขที่ใบเสร็จในรูปแบบ YYYYMMDD-XXX
            today = datetime.now().strftime('%Y%m%d')
            today_bills = [record for record in records if record['เลขที่ใบเสร็จ'].startswith(today)]
            
            next_number = len(today_bills) + 1
            bill_number = f"{today}-{next_number:03d}"
            
            return bill_number
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการสร้างเลขที่ใบเสร็จ: {e}")
            return f"{datetime.now().strftime('%Y%m%d')}-001"
    
    def create_bill(self, seller, items, notes=""):
        """สร้างใบเสร็จ"""
        try:
            bills_sheet = self.spreadsheet.worksheet('Bills')
            bill_number = self.generate_bill_number()
            
            total_amount = 0
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # เพิ่มรายการสินค้าในใบเสร็จ
            for item in items:
                product_name = item['name']
                quantity = item['quantity']
                unit_price = item['price']
                unit = item['unit']
                item_total = quantity * unit_price
                total_amount += item_total
                
                # ลดสต็อกสินค้า
                self.remove_stock(product_name, quantity, seller)
                
                # เพิ่มรายการในชีต Bills
                try:
                    existing_records = bills_sheet.get_all_records()
                    next_row = len(existing_records) + 2
                except:
                    next_row = 2
                
                bills_sheet.update(
                    range_name=f'A{next_row}:J{next_row}',
                    values=[[
                        bill_number,
                        current_date,
                        str(seller),
                        product_name,
                        quantity,
                        unit,
                        unit_price,
                        item_total,
                        total_amount if item == items[-1] else "",  # แสดงยอดรวมเฉพาะบรรทัดสุดท้าย
                        notes if item == items[-1] else ""  # แสดงหมายเหตุเฉพาะบรรทัดสุดท้าย
                    ]]
                )
            
            # บันทึกประวัติการขาย
            item_names = [item['name'] for item in items]
            self.add_history(seller, 'การขาย', ', '.join(item_names), len(items), f'ใบเสร็จ: {bill_number}, ยอดรวม: {total_amount:,.0f}')
            
            return bill_number, total_amount
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการสร้างใบเสร็จ: {e}")
            return None, 0
    
    def get_bill_details(self, bill_number):
        """ดึงรายละเอียดใบเสร็จ"""
        try:
            bills_sheet = self.spreadsheet.worksheet('Bills')
            records = bills_sheet.get_all_records()
            
            bill_items = []
            for record in records:
                if record['เลขที่ใบเสร็จ'] == bill_number:
                    bill_items.append(record)
            
            return bill_items
            
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการดึงรายละเอียดใบเสร็จ: {e}")
            return []

class Cart:
    def __init__(self):
        self.items = []  # รายการสินค้าในรถเข็น

    def add_item(self, product_name, quantity, price, unit):
        self.items.append({
            'product_name': product_name,
            'quantity': quantity,
            'price': price,
            'unit': unit
        })

    def clear(self):
        self.items = []

    def get_total(self):
        return sum(item['price'] * item['quantity'] for item in self.items)

    def get_items(self):
        return self.items

user_carts = {}

# สร้าง instance ของ StockManager
stock_manager = StockManager()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} เชื่อมต่อสำเร็จ!')
    print(f'🔗 เชื่อมต่อกับ Google Sheets: {os.getenv("GOOGLE_SHEET_NAME")}')
    
    # ตรวจสอบสินค้าใกล้หมดทุก 30 นาที
    bot.loop.create_task(low_stock_checker())
    
    # ลบช่องแชทการขายที่ไม่ใช้งานแล้ว
    bot.loop.create_task(cleanup_sales_channels())

async def low_stock_checker():
    """ตรวจสอบสินค้าใกล้หมดและแจ้งเตือนอัตโนมัติ"""
    while True:
        try:
            await asyncio.sleep(1800)  # 30 นาที
            
            low_stock_items = stock_manager.check_low_stock()
            
            if low_stock_items:
                for guild in bot.guilds:
                    for channel in guild.text_channels:
                        if channel.name in ['general', 'stock', 'แจ้งเตือน']:
                            embed = discord.Embed(
                                title="⚠️ แจ้งเตือนสินค้าใกล้หมด",
                                description="มีสินค้าใกล้หมดแล้ว กรุณาเติมสินค้า",
                                color=0xe74c3c
                            )
                            
                            for product in low_stock_items:
                                embed.add_field(
                                    name=f"🔴 {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
                                    value=f"จำนวน: {product.get('จำนวน', 0)} {product.get('หน่วย', 'ชิ้น')}",
                                    inline=True
                                )
                            
                            await channel.send(embed=embed)
                            break
                        
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการตรวจสอบสินค้าใกล้หมด: {e}")

async def create_sales_channel(guild, user):
    """สร้างช่องแชทการขายสำหรับผู้ใช้"""
    try:
        # ตรวจสอบว่ามีช่องแชทการขายอยู่แล้วหรือไม่
        existing_channel = None
        for channel in guild.text_channels:
            if channel.name == f"การขาย-{user.name.lower()}":
                existing_channel = channel
                break
        
        if existing_channel:
            # เพิ่มผู้ใช้เข้าช่องที่มีอยู่
            await existing_channel.set_permissions(user, read_messages=True, send_messages=True)
            return existing_channel
        
        # สร้างช่องแชทใหม่
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await guild.create_text_channel(
            name=f"การขาย-{user.name.lower()}",
            overwrites=overwrites,
            topic=f"ห้องการขายส่วนตัวของ {user.display_name}",
            reason=f"สร้างห้องการขายสำหรับ {user}"
        )
        
        # บันทึกช่องแชทในระบบ
        sales_channels[user.id] = channel.id
        
        # ส่งข้อความต้อนรับและเมนูการขาย
        embed = discord.Embed(
            title="🛒 ห้องการขายส่วนตัว",
            description=f"ยินดีต้อนรับสู่ห้องการขายของ {user.mention}",
            color=0x2ecc71
        )
        embed.add_field(
            name="📋 คำแนะนำการใช้งาน",
            value="""
            • ใช้ปุ่ม "🛒 สร้างการขาย" เพื่อสร้างรายการขายใหม่
            • ใช้ปุ่ม "📋 ดูประวัติการขาย" เพื่อดูประวัติการขาย
            • ห้องนี้จะถูกลบหลังจาก 24 ชั่วโมงหากไม่มีการใช้งาน
            """,
            inline=False
        )
        embed.add_field(
            name="🔒 ความเป็นส่วนตัว",
            value="เฉพาะคุณเท่านั้นที่สามารถเห็นและใช้งานห้องนี้ได้",
            inline=False
        )
        
        await channel.send(embed=embed, view=SalesChannelView(stock_manager))
        
        return channel
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการสร้างช่องแชทการขาย: {e}")
        return None

async def cleanup_sales_channels():
    """ลบช่องแชทการขายที่ไม่ใช้งานแล้ว"""
    while True:
        try:
            await asyncio.sleep(3600)  # ทุก 1 ชั่วโมง
            
            for guild in bot.guilds:
                for channel in guild.text_channels:
                    if channel.name.startswith("การขาย-"):
                        # ตรวจสอบว่ามีข้อความล่าสุดเมื่อไหร่
                        try:
                            last_message = None
                            async for message in channel.history(limit=1):
                                last_message = message
                                break
                            
                            if last_message:
                                # ลบช่องแชทหากไม่มีข้อความมานานกว่า 24 ชั่วโมง
                                time_diff = discord.utils.utcnow() - last_message.created_at
                                if time_diff.total_seconds() > 86400:  # 24 ชั่วโมง
                                    await channel.delete(reason="ไม่มีการใช้งานมานานกว่า 24 ชั่วโมง")
                                    print(f"✅ ลบช่องแชทการขาย: {channel.name}")
                        except Exception as e:
                            print(f"❌ เกิดข้อผิดพลาดในการตรวจสอบช่องแชท {channel.name}: {e}")
                        
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการลบช่องแชทการขาย: {e}")
            await asyncio.sleep(3600)  # รอ 1 ชั่วโมงก่อนลองใหม่
            
@bot.command(name='add')
async def add_stock(ctx, product_name: str, quantity: int, unit: str, price: float = 0):
    """เพิ่มสินค้าเข้าสต๊อก"""
    if stock_manager.add_stock(product_name, quantity, unit, ctx.author, price, "", ""):
        embed = discord.Embed(
            title="✅ เพิ่มสินค้าสำเร็จ",
            description=f"เพิ่ม **{product_name}** จำนวน **{quantity} {unit}** แล้ว",
            color=0x2ecc71
        )
        if price > 0:
            embed.add_field(name="💰 ราคา", value=f"{price:,.0f}", inline=True)
        embed.set_footer(text=f"ดำเนินการโดย {ctx.author}")
        await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))
    else:
        embed = discord.Embed(
            title="❌ เกิดข้อผิดพลาด",
            description="ไม่สามารถเพิ่มสินค้าได้",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

@bot.command(name='remove')
async def remove_stock(ctx, product_name: str, quantity: int):
    """ลดสินค้าจากสต๊อก"""
    success, remaining = stock_manager.remove_stock(product_name, quantity, ctx.author)
    
    if success:
        embed = discord.Embed(
            title="✅ ลดสินค้าสำเร็จ",
            description=f"ลด **{product_name}** จำนวน **{quantity}** แล้ว\nคงเหลือ: **{remaining}**",
            color=0x2ecc71
        )
        
        if remaining < LOW_STOCK_THRESHOLD:
            embed.add_field(
                name="⚠️ แจ้งเตือน",
                value="สินค้าใกล้หมดแล้ว กรุณาเติมสินค้า",
                inline=False
            )
        
        embed.set_footer(text=f"ดำเนินการโดย {ctx.author}")
        await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))
    else:
        embed = discord.Embed(
            title="❌ เกิดข้อผิดพลาด",
            description=f"ไม่พบสินค้า **{product_name}** หรือไม่สามารถลดสินค้าได้",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

@bot.command(name='check')
async def check_stock(ctx, product_name: str):
    """ตรวจสอบจำนวนสินค้า"""
    product = stock_manager.check_stock(product_name)
    
    if product:
        quantity = int(product.get('จำนวน', 0))
        status_emoji = "⚠️" if quantity < LOW_STOCK_THRESHOLD else "✅"
        price = float(product.get('ราคา', 0)) if product.get('ราคา') else 0
        
        embed = discord.Embed(
            title=f"{status_emoji} {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
            color=0xe74c3c if quantity < LOW_STOCK_THRESHOLD else 0x2ecc71
        )
        
        embed.add_field(name="จำนวน", value=f"{quantity} {product.get('หน่วย', 'ชิ้น')}", inline=True)
        if price > 0:
            embed.add_field(name="ราคา", value=f"{price:,.0f}", inline=True)
        embed.add_field(name="อัปเดตล่าสุด", value=product.get('วันที่อัปเดตล่าสุด', 'ไม่ระบุ'), inline=True)
        
        if product.get('คำอธิบาย'):
            embed.add_field(name="คำอธิบาย", value=product.get('คำอธิบาย'), inline=False)
        
        if product.get('รูปภาพURL'):
            embed.set_image(url=product.get('รูปภาพURL'))
        
        if quantity < LOW_STOCK_THRESHOLD:
            embed.add_field(
                name="⚠️ แจ้งเตือน",
                value="สินค้าใกล้หมดแล้ว",
                inline=False
            )
        
        await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))
    else:
        embed = discord.Embed(
            title="❌ ไม่พบสินค้า",
            description=f"ไม่พบสินค้า **{product_name}** ในระบบ",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

@bot.command(name='list')
async def list_stock(ctx):
    """แสดงรายการสินค้าทั้งหมด"""
    products = stock_manager.get_all_stock()
    
    if not products:
        embed = discord.Embed(
            title="📦 รายการสินค้า",
            description="ไม่มีสินค้าในระบบ",
            color=0xff6b6b
        )
    else:
        embed = discord.Embed(
            title="📦 รายการสินค้าทั้งหมด",
            color=0x4ecdc4
        )
        
        for product in products:
            quantity = int(product.get('จำนวน', 0))
            status_emoji = "⚠️" if quantity < LOW_STOCK_THRESHOLD else "✅"
            price = float(product.get('ราคา', 0)) if product.get('ราคา') else 0
            
            value_text = f"จำนวน: {quantity} {product.get('หน่วย', 'ชิ้น')}"
            if price > 0:
                value_text += f"\nราคา: {price:,.0f}"
            value_text += f"\nอัปเดต: {product.get('วันที่อัปเดตล่าสุด', 'ไม่ระบุ')}"
            
            embed.add_field(
                name=f"{status_emoji} {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
                value=value_text,
                inline=True
            )
    
    await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))

@bot.command(name='history')
async def show_history(ctx):
    """แสดงประวัติการทำรายการ"""
    history = stock_manager.get_history(10)
    
    if not history:
        embed = discord.Embed(
            title="📋 ประวัติการทำรายการ",
            description="ไม่มีประวัติการทำรายการ",
            color=0xff6b6b
        )
    else:
        embed = discord.Embed(
            title="📋 ประวัติการทำรายการ (10 รายการล่าสุด)",
            color=0xfeca57
        )
        
        for record in reversed(history):
            embed.add_field(
                name=f"{record.get('การทำรายการ', 'ไม่ระบุ')} - {record.get('ชื่อสินค้า', 'ไม่ระบุ')}",
                value=f"ผู้ใช้: {record.get('ชื่อผู้ใช้', 'ไม่ระบุ')}\nจำนวน: {record.get('จำนวน', 0)}\nวันที่: {record.get('วันที่', 'ไม่ระบุ')}\nหมายเหตุ: {record.get('หมายเหตุ', 'ไม่มี')}",
                inline=False
            )
    
    await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))

@bot.command(name='products')
async def show_products(ctx):
    """แสดงสินค้าทั้งหมดเป็น card"""
    products = stock_manager.get_all_stock()
    
    if not products:
        embed = discord.Embed(
            title="📦 รายการสินค้า",
            description="ไม่มีสินค้าในระบบ",
            color=0xff6b6b
        )
        await ctx.send(embed=embed)
        return
    
    # ส่งสินค้าแต่ละรายการเป็น card
    for product in products:
        quantity = int(product.get('จำนวน', 0))
        status_emoji = "⚠️" if quantity < LOW_STOCK_THRESHOLD else "✅"
        price = float(product.get('ราคา', 0)) if product.get('ราคา') else 0
        
        embed = discord.Embed(
            title=f"{status_emoji} {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
            color=0xe74c3c if quantity < LOW_STOCK_THRESHOLD else 0x2ecc71
        )
        
        # ข้อมูลพื้นฐาน
        embed.add_field(
            name="📦 จำนวน",
            value=f"{quantity} {product.get('หน่วย', 'ชิ้น')}",
            inline=True
        )
        
        if price > 0:
            embed.add_field(
                name="💰 ราคา",
                value=f"{price:,.0f} บาท",
                inline=True
            )
        
        embed.add_field(
            name="🆔 ID",
            value=f"#{product.get('ID', 'N/A')}",
            inline=True
        )
        
        # คำอธิบาย
        if product.get('คำอธิบาย'):
            embed.add_field(
                name="📝 คำอธิบาย",
                value=product.get('คำอธิบาย'),
                inline=False
            )
        
        # วันที่อัปเดต
        embed.add_field(
            name="🕒 อัปเดตล่าสุด",
            value=product.get('วันที่อัปเดตล่าสุด', 'ไม่ระบุ'),
            inline=False
        )
        
        # รูปภาพ
        if product.get('รูปภาพURL'):
            embed.set_image(url=product.get('รูปภาพURL'))
        
        # แจ้งเตือนสต็อกต่ำ
        if quantity < LOW_STOCK_THRESHOLD:
            embed.add_field(
                name="⚠️ แจ้งเตือน",
                value="สินค้าใกล้หมดแล้ว",
                inline=False
            )
        
        # สถานะสินค้า
        if quantity == 0:
            embed.add_field(
                name="🚫 สถานะ",
                value="สินค้าหมด",
                inline=False
            )
            embed.color = 0x95a5a6
        
        # ส่งเป็น card พร้อมปุ่ม
        await ctx.send(embed=embed, view=ProductCardView(product, stock_manager))
        
        # รอเล็กน้อยเพื่อไม่ให้ spam
        await asyncio.sleep(0.5)

@bot.command(name='product')
async def show_product(ctx, *, product_name: str):
    """แสดงสินค้าแต่ละรายการเป็น card"""
    product = stock_manager.check_stock(product_name)
    
    if not product:
        embed = discord.Embed(
            title="❌ ไม่พบสินค้า",
            description=f"ไม่พบสินค้า **{product_name}** ในระบบ",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
        return
    
    quantity = int(product.get('จำนวน', 0))
    status_emoji = "⚠️" if quantity < LOW_STOCK_THRESHOLD else "✅"
    price = float(product.get('ราคา', 0)) if product.get('ราคา') else 0
    
    embed = discord.Embed(
        title=f"{status_emoji} {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
        color=0xe74c3c if quantity < LOW_STOCK_THRESHOLD else 0x2ecc71
    )
    
    # ข้อมูลพื้นฐาน
    embed.add_field(
        name="📦 จำนวน",
        value=f"{quantity} {product.get('หน่วย', 'ชิ้น')}",
        inline=True
    )
    
    if price > 0:
        embed.add_field(
            name="💰 ราคา",
            value=f"{price:,.0f} บาท",
            inline=True
        )
    
    embed.add_field(
        name="🆔 ID",
        value=f"#{product.get('ID', 'N/A')}",
        inline=True
    )
    
    # คำอธิบาย
    if product.get('คำอธิบาย'):
        embed.add_field(
            name="📝 คำอธิบาย",
            value=product.get('คำอธิบาย'),
            inline=False
        )
    
    # วันที่อัปเดต
    embed.add_field(
        name="🕒 อัปเดตล่าสุด",
        value=product.get('วันที่อัปเดตล่าสุด', 'ไม่ระบุ'),
        inline=False
    )
    
    # รูปภาพ
    if product.get('รูปภาพURL'):
        embed.set_image(url=product.get('รูปภาพURL'))
    
    # แจ้งเตือนสต็อกต่ำ
    if quantity < LOW_STOCK_THRESHOLD:
        embed.add_field(
            name="⚠️ แจ้งเตือน",
            value="สินค้าใกล้หมดแล้ว",
            inline=False
        )
    
    # สถานะสินค้า
    if quantity == 0:
        embed.add_field(
            name="🚫 สถานะ",
            value="สินค้าหมด",
            inline=False
        )
        embed.color = 0x95a5a6
    
    # ส่งเป็น card พร้อมปุ่ม
    await ctx.send(embed=embed, view=ProductCardView(product, stock_manager))

@bot.command(name='stock')
async def stock_menu(ctx):
    """แสดงเมนูหลักของระบบสต๊อก"""
    embed = discord.Embed(
        title="🏪 ระบบจัดการสต๊อกสินค้า",
        description="เลือกใช้งานฟีเจอร์ด้านล่าง",
        color=0x3498db
    )
    
    embed.add_field(
        name="📝 คำสั่งพื้นฐาน",
        value="""
        `!add [ชื่อสินค้า] [จำนวน] [หน่วย] [ราคา]` - เพิ่มสินค้า
        `!remove [ชื่อสินค้า] [จำนวน]` - ลดสินค้า
        `!check [ชื่อสินค้า]` - ตรวจสอบสินค้า
        `!list` - รายการสินค้าทั้งหมด
        `!history` - ประวัติการทำรายการ
        `!upload_help` - วิธีอัปโหลดรูปภาพ
        """,
        inline=False
    )
    
    embed.add_field(
        name="🛒 คำสั่งการขายใหม่",
        value="""
        `!products` - แสดงสินค้าทั้งหมดเป็น card
        `!product [ชื่อสินค้า]` - แสดงสินค้าเฉพาะเป็น card
        `!add_to_cart [ชื่อสินค้า] [จำนวน]` - เพิ่มเข้ารถเข็น
        `!cart` - ดูรถเข็น
        `!checkout` - ชำระเงิน
        `!clear_cart` - เคลียร์รถเข็น
        """,
        inline=False
    )
    
    embed.add_field(
        name="🔗 การเชื่อมต่อ",
        value=f"Google Sheets: {os.getenv('GOOGLE_SHEET_NAME')}",
        inline=False
    )
    
    embed.set_footer(text="ใช้ปุ่มด้านล่างเพื่อเข้าใช้งานอย่างรวดเร็ว")
    
    await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ ข้อมูลไม่ครบถ้วน",
            description="กรุณาใส่ข้อมูลให้ครบถ้วน",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❌ ข้อมูลไม่ถูกต้อง",
            description="กรุณาตรวจสอบข้อมูลที่ใส่",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)
    else:
        print(f"Error: {error}")

# Help command
@bot.command(name='manual')
async def help_command(ctx):
    """แสดงคำสั่งทั้งหมด"""
    embed = discord.Embed(
        title="📚 คำสั่งทั้งหมด",
        description="รายการคำสั่งที่ใช้ได้ในระบบ",
        color=0x9b59b6
    )
    
    embed.add_field(
        name="🔧 คำสั่งหลัก",
        value="""
        `!stock` - แสดงเมนูหลัก
        `!add [ชื่อสินค้า] [จำนวน] [หน่วย] [ราคา]` - เพิ่มสินค้า
        `!remove [ชื่อสินค้า] [จำนวน]` - ลดสินค้า
        `!check [ชื่อสินค้า]` - ตรวจสอบสินค้า
        `!list` - รายการสินค้าทั้งหมด
        `!history` - ประวัติการทำรายการ
        `!upload_help` - วิธีอัปโหลดรูปภาพ
        """,
        inline=False
    )
    
    embed.add_field(
        name="� คำสั่งการขายใหม่",
        value="""
        `!products` - แสดงสินค้าทั้งหมดเป็น card
        `!product [ชื่อสินค้า]` - แสดงสินค้าเฉพาะเป็น card
        `!add_to_cart [ชื่อสินค้า] [จำนวน]` - เพิ่มเข้ารถเข็น
        `!cart` - ดูรถเข็น
        `!checkout` - ชำระเงิน
        `!clear_cart` - เคลียร์รถเข็น
        """,
        inline=False
    )
    
    embed.add_field(
        name="🧾 คำสั่งใบเสร็จ",
        value="""
        `!bill [เลขที่ใบเสร็จ]` - ดูรายละเอียดใบเสร็จ
        `!sales` - เมนูการขาย
        """,
        inline=False
    )
    
    embed.add_field(
        name="�💡 ตัวอย่างการใช้งาน",
        value="""
        `!add ปากกา 10 ด้าม 15` - เพิ่มปากกา 10 ด้าม ราคา 15 บาท
        `!product ปากกา` - ดูข้อมูลปากกาแบบ card
        `!add_to_cart ปากกา 2` - เพิ่มปากกา 2 ด้าม เข้ารถเข็น
        `upload: ปากกา` + แนบรูปภาพ - อัปโหลดรูปปากกา
        """,
        inline=False
    )
    
    embed.add_field(
        name="🎯 คำสั่งใหม่ที่แนะนำ",
        value="""
        • `!products` - ดูสินค้าทั้งหมดแบบ card พร้อมปุ่มสั่งซื้อ
        • `!product [ชื่อสินค้า]` - ดูสินค้าเฉพาะแบบ card
        • การซื้อผ่านปุ่ม: เพิ่มเข้ารถเข็น, ซื้อทันที, ดูรถเข็น, เคลียร์รถเข็น
        """,
        inline=False
    )
    
    embed.set_footer(text="ระบบจะแจ้งเตือนอัตโนมัติเมื่อสินค้าเหลือน้อยกว่า 5 ชิ้น")
    
    await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))

@bot.command(name='upload_help')
async def upload_help(ctx):
    """แสดงวิธีอัปโหลดรูปภาพสินค้า"""
    embed = discord.Embed(
        title="📸 วิธีอัปโหลดรูปภาพสินค้า",
        description="คำแนะนำในการอัปโหลดรูปภาพสำหรับสินค้า (ใช้ Discord CDN)",
        color=0x3498db
    )
    
    embed.add_field(
        name="🔧 วิธีที่ 1: อัปโหลดพร้อมสร้างสินค้า",
        value="""
        1. ใช้ปุ่ม "สร้างสินค้าใหม่" จากเมนูหลัก
        2. กรอกข้อมูลสินค้า (ชื่อ, จำนวน, หน่วย, ราคา, คำอธิบาย)
        3. ส่งรูปภาพในข้อความถัดไป
        """,
        inline=False
    )
    
    embed.add_field(
        name="🔧 วิธีที่ 2: อัปโหลดให้สินค้าที่มีอยู่",
        value="""
        1. พิมพ์ `upload: ชื่อสินค้า` 
        2. แนบรูปภาพในข้อความเดียวกัน
        3. ส่งข้อความ
        """,
        inline=False
    )
    
    embed.add_field(
        name="💡 ตัวอย่าง",
        value="`upload: ปากกา` (พร้อมแนบรูปภาพ)",
        inline=False
    )
    
    embed.add_field(
        name="📁 รองรับไฟล์",
        value="JPG, PNG, GIF, WEBP",
        inline=True
    )
    
    embed.add_field(
        name="🔗 Discord CDN",
        value="รูปภาพจะถูกเก็บไว้ใน Discord CDN โดยอัตโนมัติ",
        inline=True
    )
    
    embed.add_field(
        name="✨ ข้อดี",
        value="• ไม่จำกัดเนื้อที่\n• ความเร็วสูง\n• เสถียรภาพดี",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='bill')
async def view_bill(ctx, bill_number: str):
    """ดูรายละเอียดใบเสร็จ"""
    try:
        bill_items = stock_manager.get_bill_details(bill_number)
        
        if not bill_items:
            embed = discord.Embed(
                title="❌ ไม่พบใบเสร็จ",
                description=f"ไม่พบใบเสร็จหมายเลข **{bill_number}**",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            return
        
        # สร้าง embed แสดงรายละเอียดใบเสร็จ
        embed = discord.Embed(
            title="🧾 รายละเอียดใบเสร็จ",
            description=f"เลขที่ใบเสร็จ: **{bill_number}**",
            color=0x3498db
        )
        
        # ข้อมูลทั่วไป
        embed.add_field(
            name="👤 ผู้ขาย",
            value=bill_items[0]['ผู้ขาย'],
            inline=True
        )
        
        embed.add_field(
            name="📅 วันที่",
            value=bill_items[0]['วันที่'],
            inline=True
        )
        
        # รายการสินค้า
        items_text = ""
        total_amount = 0
        
        for item in bill_items:
            item_total = float(item['ราคารวม']) if item['ราคารวม'] else 0
            total_amount += item_total
            
            items_text += f"• {item['ชื่อสินค้า']} x {item['จำนวน']} {item['หน่วย']}\n"
            items_text += f"  ราคา: {float(item['ราคาต่อหน่วย']):,.0f} x {item['จำนวน']} = {item_total:,.0f} บาท\n"
        
        embed.add_field(
            name="📦 รายการสินค้า",
            value=items_text,
            inline=False
        )
        
        embed.add_field(
            name="💰 ยอดรวมทั้งหมด",
            value=f"{total_amount:,.0f} บาท",
            inline=False
        )
        
        # หมายเหตุ
        if bill_items[0]['หมายเหตุ']:
            embed.add_field(
                name="📝 หมายเหตุ",
                value=bill_items[0]['หมายเหตุ'],
                inline=False
            )
        
        embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
        
        await ctx.send(embed=embed)
        
        # ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย
        await remove_seller_permission(ctx, ctx.author)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ เกิดข้อผิดพลาด",
            description=f"ไม่สามารถดึงข้อมูลใบเสร็จได้: {str(e)}",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

@bot.command(name='sales')
async def sales_menu(ctx):
    """แสดงเมนูการขาย"""
    embed = discord.Embed(
        title="🛒 ระบบการขาย",
        description="เลือกใช้งานฟีเจอร์การขายด้านล่าง",
        color=0x2ecc71
    )
    
    embed.add_field(
        name="📝 คำสั่งการขาย",
        value="`!bill [เลขที่ใบเสร็จ]` - ดูรายละเอียดใบเสร็จ\n`!sales` - เมนูการขาย",
        inline=False
    )
    
    embed.add_field(
        name="🛒 การสร้างการขาย",
        value="1. คลิกปุ่ม \"🛒 สร้างการขาย\" ด้านล่าง\n2. ระบบจะสร้างห้องการขายส่วนตัวให้คุณ\n3. ใช้เมนูในห้องเพื่อสร้างการขาย",
        inline=False
    )
    
    embed.add_field(
        name="📋 ประวัติการขาย",
        value=f"ประวัติการขายทั้งหมดจะถูกส่งไปยัง <#{BILL_HISTORY_CHANNEL_ID}>",
        inline=False
    )
    
    embed.add_field(
        name="🔒 ความปลอดภัย",
        value="ห้องการขายเป็นส่วนตัว เฉพาะผู้ขายเท่านั้นที่เข้าถึงได้",
        inline=False
    )
    
    # สร้างปุ่มสำหรับสร้างการขาย
    view = discord.ui.View()
    
    async def create_sales_callback(interaction):
        await interaction.response.defer()
        
        try:
            sales_channel = await create_sales_channel(interaction.guild, interaction.user)
            
            if sales_channel:
                embed = discord.Embed(
                    title="✅ สร้างห้องการขายสำเร็จ",
                    description=f"ห้องการขายส่วนตัวของคุณ: {sales_channel.mention}",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="📋 คำแนะนำ",
                    value="• ห้องนี้เป็นส่วนตัวเฉพาะคุณเท่านั้น\n• ใช้สำหรับสร้างการขายและจัดการใบเสร็จ\n• ห้องจะถูกลบหลังจาก 24 ชั่วโมงหากไม่มีการใช้งาน",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ เกิดข้อผิดพลาด",
                    description="ไม่สามารถสร้างห้องการขายได้",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"ไม่สามารถสร้างห้องการขายได้: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    button = discord.ui.Button(
        label="🛒 สร้างการขาย",
        style=discord.ButtonStyle.success,
        emoji="🛒"
    )
    button.callback = create_sales_callback
    view.add_item(button)
    
    await ctx.send(embed=embed, view=view)

async def add_item_to_cart_helper(user_id: str, product_name: str, quantity: int):
    """Helper function to add items to cart with validation and return result"""
    if user_id not in user_carts:
        user_carts[user_id] = Cart()
    
    # ค้นหาสินค้าในสต็อก
    products = stock_manager.get_all_stock()
    product_found = False
    
    for product in products:
        if product['ชื่อสินค้า'].lower() == product_name.lower():
            # ตรวจสอบสต็อกเพียงพอหรือไม่
            available_quantity = int(product.get('จำนวน', 0))
            if available_quantity < quantity:
                return {
                    'success': False,
                    'error_type': 'insufficient_stock',
                    'message': f"สินค้า **{product_name}** เหลือเพียง {available_quantity} {product.get('หน่วย', 'ชิ้น')}",
                    'available_quantity': available_quantity,
                    'unit': product.get('หน่วย', 'ชิ้น')
                }
            
            price = float(product.get('ราคา', 0))
            unit = product.get('หน่วย', 'ชิ้น')
            user_carts[user_id].add_item(product_name, quantity, price, unit)
            
            # แสดงรายการสินค้าในรถเข็นทั้งหมด
            cart = user_carts[user_id]
            cart_items = cart.get_items()
            total_price = cart.get_total()
            
            # สร้างรายการสินค้าในรถเข็น
            cart_list = ""
            for i, item in enumerate(cart_items, 1):
                item_total = item['price'] * item['quantity']
                cart_list += f"{i}. **{item['product_name']}** x{item['quantity']} {item['unit']} = {item_total:,.0f} บาท\n"
            
            return {
                'success': True,
                'product_name': product_name,
                'quantity': quantity,
                'cart_items': cart_items,
                'cart_list': cart_list,
                'total_price': total_price
            }
    
    # ไม่พบสินค้า
    return {
        'success': False,
        'error_type': 'product_not_found',
        'message': f"ไม่พบสินค้า **{product_name}** ในระบบ"
    }

@bot.command()
async def add_to_cart(ctx, product_name: str, quantity: int):
    """เพิ่มสินค้าเข้ารถเข็นของผู้ใช้"""
    user_id = str(ctx.author.id)
    
    result = await add_item_to_cart_helper(user_id, product_name, quantity)
    
    if result['success']:
        cart_items = result['cart_items']
        total_price = result['total_price']
        
        embed = discord.Embed(
            title="✅ เพิ่มลงรถเข็นสำเร็จ",
            description=f"เพิ่ม **{product_name}** x{quantity} เข้ารถเข็นแล้ว!",
            color=0x2ecc71
        )
        
        # แสดงรายการสินค้าในรถเข็นทั้งหมด
        cart_list = ""
        for i, item in enumerate(cart_items, 1):
            item_total = item['price'] * item['quantity']
            cart_list += f"{i}. **{item['product_name']}** x{item['quantity']} {item['unit']} = {item_total:,.0f} บาท\n"
        
        embed.add_field(
            name="🛒 รถเข็นของคุณ",
            value=cart_list if cart_list else "ไม่มีสินค้า",
            inline=False
        )
        
        embed.add_field(
            name="💰 ยอดรวมทั้งหมด",
            value=f"{total_price:,.0f} บาท",
            inline=True
        )
        
        embed.add_field(
            name="📦 จำนวนรายการ",
            value=f"{len(cart_items)} รายการ",
            inline=True
        )
        
        embed.add_field(
            name="💡 คำแนะนำ",
            value="ใช้คำสั่ง `!checkout` เพื่อชำระเงิน\nใช้คำสั่ง `!cart` เพื่อดูรถเข็น\nใช้คำสั่ง `!clear_cart` เพื่อเคลียร์รถเข็น",
            inline=False
        )
        
        await ctx.send(embed=embed)
    else:
        error_message = result['message']
        
        embed = discord.Embed(
            title="❌ เกิดข้อผิดพลาด",
            description=error_message,
            color=0xe74c3c
        )
        
        if result['error_type'] == 'insufficient_stock':
            available_quantity = result['available_quantity']
            unit = result['unit']
            embed.add_field(
                name="📉 สต็อกไม่เพียงพอ",
                value=f"สินค้า **{product_name}** เหลือเพียง {available_quantity} {unit}",
                inline=False
            )
        
        await ctx.send(embed=embed)

@bot.command()
async def checkout(ctx):
    """ออกใบเสร็จและเคลียร์รถเข็น"""
    user_id = str(ctx.author.id)
    if user_id not in user_carts or not user_carts[user_id].get_items():
        embed = discord.Embed(
            title="❌ รถเข็นว่างเปล่า",
            description="ไม่มีสินค้าในรถเข็นของคุณ",
            color=0xe74c3c
        )
        embed.add_field(
            name="💡 คำแนะนำ",
            value="ใช้คำสั่ง `!add_to_cart [ชื่อสินค้า] [จำนวน]` เพื่อเพิ่มสินค้า",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    cart = user_carts[user_id]
    items = cart.get_items()
    
    try:
        # ตรวจสอบสต็อกก่อนขาย
        stock_errors = []
        for item in items:
            product = stock_manager.check_stock(item['product_name'])
            if product:
                available_quantity = int(product.get('จำนวน', 0))
                if available_quantity < item['quantity']:
                    stock_errors.append(f"❌ {item['product_name']}: สต็อกไม่เพียงพอ (มี {available_quantity} ต้องการ {item['quantity']})")
            else:
                stock_errors.append(f"❌ {item['product_name']}: ไม่พบสินค้าในระบบ")
        
        if stock_errors:
            embed = discord.Embed(
                title="❌ พบข้อผิดพลาด",
                description="ไม่สามารถชำระเงินได้เนื่องจากมีปัญหากับสต็อก",
                color=0xe74c3c
            )
            embed.add_field(
                name="รายการปัญหา",
                value="\n".join(stock_errors),
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        # แปลงข้อมูลสำหรับสร้างใบเสร็จ
        bill_items = []
        for item in items:
            bill_items.append({
                'name': item['product_name'],
                'quantity': item['quantity'],
                'price': item['price'],
                'unit': item['unit']
            })
        
        # สร้างใบเสร็จ
        bill_number, total_amount = stock_manager.create_bill(
            ctx.author,
            bill_items,
            f"ชำระผ่านรถเข็น - {len(items)} รายการ"
        )
        
        if bill_number:
            # สร้าง embed ใบเสร็จ
            embed = discord.Embed(
                title="🧾 ใบเสร็จการขาย",
                description=f"เลขที่ใบเสร็จ: **{bill_number}**",
                color=0x2ecc71
            )
            
            embed.add_field(
                name="👤 ผู้ซื้อ",
                value=f"{ctx.author.mention}",
                inline=True
            )
            
            embed.add_field(
                name="📅 วันที่",
                value=f"<t:{int(ctx.message.created_at.timestamp())}:F>",
                inline=True
            )
            
            embed.add_field(
                name="💰 ยอดรวม",
                value=f"{total_amount:,.0f} บาท",
                inline=True
            )
            
            # รายการสินค้า
            items_text = ""
            for item in items:
                item_total = item['price'] * item['quantity']
                items_text += f"• {item['product_name']} x {item['quantity']} {item['unit']} = {item_total:,.0f} บาท\n"
            
            embed.add_field(
                name="📦 รายการสินค้า",
                value=items_text,
                inline=False
            )
            
            embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
            
            await ctx.send(embed=embed)
            
            # ส่งล็อกไปยังช่องประวัติบิลถ้ามี
            try:
                bill_history_channel = ctx.guild.get_channel(BILL_HISTORY_CHANNEL_ID)
                if bill_history_channel:
                    log_embed = discord.Embed(
                        title="🛒 การขายผ่านรถเข็น",
                        description=f"มีการชำระเงินผ่านรถเข็น",
                        color=0x3498db
                    )
                    log_embed.add_field(
                        name="🧾 เลขที่ใบเสร็จ",
                        value=bill_number,
                        inline=True
                    )
                    log_embed.add_field(
                        name="👤 ผู้ซื้อ",
                        value=f"{ctx.author} ({ctx.author.id})",
                        inline=True
                    )
                    log_embed.add_field(
                        name="💰 ยอดรวม",
                        value=f"{total_amount:,.0f} บาท",
                        inline=True
                    )
                    log_embed.add_field(
                        name="📦 รายการสินค้า",
                        value=items_text,
                        inline=False
                    )
                    log_embed.add_field(
                        name="📍 ช่อง",
                        value=f"{ctx.channel.mention}",
                        inline=True
                    )
                    log_embed.add_field(
                        name="📅 วันที่",
                        value=f"<t:{int(ctx.message.created_at.timestamp())}:F>",
                        inline=True
                    )
                    log_embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
                    
                    await bill_history_channel.send(embed=log_embed)
            except Exception as e:
                print(f"❌ ไม่สามารถส่งล็อกไปยังช่องประวัติบิลได้: {e}")
            
            # ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย
            await remove_seller_permission(ctx, ctx.author)
            
            # เคลียร์รถเข็น
            cart.clear()
            
        else:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description="ไม่สามารถสร้างใบเสร็จได้",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
            
    except Exception as e:
        embed = discord.Embed(
            title="❌ เกิดข้อผิดพลาด",
            description=f"ไม่สามารถชำระเงินได้: {str(e)}",
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

@bot.command()
async def cart(ctx):
    """ดูรถเข็นสินค้าของผู้ใช้"""
    user_id = str(ctx.author.id)
    if user_id not in user_carts or not user_carts[user_id].get_items():
        embed = discord.Embed(
            title="🛒 รถเข็นของคุณ",
            description="รถเข็นว่างเปล่า",
            color=0xff6b6b
        )
        embed.add_field(
            name="💡 คำแนะนำ",
            value="ใช้คำสั่ง `!add_to_cart [ชื่อสินค้า] [จำนวน]` เพื่อเพิ่มสินค้า",
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    cart = user_carts[user_id]
    items = cart.get_items()
    total = cart.get_total()
    
    embed = discord.Embed(
        title="🛒 รถเข็นของคุณ",
        description=f"มีสินค้า {len(items)} รายการ",
        color=0x3498db
    )
    
    for item in items:
        item_total = item['price'] * item['quantity']
        embed.add_field(
            name=f"📦 {item['product_name']}",
            value=f"จำนวน: {item['quantity']} {item['unit']}\nราคา: {item['price']:,.0f} x {item['quantity']} = {item_total:,.0f} บาท",
            inline=True
        )
    
    embed.add_field(
        name="💰 ยอดรวมทั้งหมด",
        value=f"{total:,.0f} บาท",
        inline=False
    )
    
    embed.add_field(
        name="💡 คำแนะนำ",
        value="ใช้คำสั่ง `!checkout` เพื่อชำระเงิน\nใช้คำสั่ง `!clear_cart` เพื่อเคลียร์รถเข็น",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def clear_cart(ctx):
    """เคลียร์รถเข็นสินค้าของผู้ใช้"""
    user_id = str(ctx.author.id)
    if user_id not in user_carts or not user_carts[user_id].get_items():
        embed = discord.Embed(
            title="🛒 รถเข็นของคุณ",
            description="รถเข็นว่างเปล่าอยู่แล้ว",
            color=0xff6b6b
        )
        await ctx.send(embed=embed)
        return
    
    user_carts[user_id].clear()
    embed = discord.Embed(
        title="✅ เคลียร์รถเข็นสำเร็จ",
        description="รถเข็นของคุณถูกล้างแล้ว",
        color=0x2ecc71
    )
    await ctx.send(embed=embed)

# เพิ่มฟังก์ชันรองรับการอัปโหลดรูปจาก Discord message
@bot.event
async def on_message(message):
    # ตรวจสอบว่าไม่ใช่ bot
    if message.author.bot:
        return
    
    # ตรวจสอบว่ามีไฟล์แนบและเป็นรูปภาพ
    if message.attachments:
        for attachment in message.attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                # ตรวจสอบว่าข้อความมีการแก้ไข "upload:" หรือไม่
                if message.content.startswith('upload:'):
                    try:
                        # ดึงชื่อสินค้าจากข้อความ
                        product_name = message.content.replace('upload:', '').strip()
                        
                        if product_name:
                            # ใช้ Discord CDN สำหรับรูปภาพ
                            filename = f"{product_name}_{attachment.filename}"
                            image_url = await stock_manager.upload_image_to_drive(attachment.url, filename)
                            
                            if image_url:
                                # อัปเดตข้อมูลสินค้าด้วย URL รูปภาพ
                                products = stock_manager.get_all_stock()
                                for product in products:
                                    if product['ชื่อสินค้า'].lower() == product_name.lower():
                                        # อัปเดต URL รูปภาพในชีต
                                        stock_sheet = stock_manager.spreadsheet.worksheet('Stock')
                                        existing_products = stock_sheet.get_all_records()
                                        
                                        for i, p in enumerate(existing_products):
                                            if p['ชื่อสินค้า'].lower() == product_name.lower():
                                                stock_sheet.update(f'G{i+2}', image_url)
                                                break
                                        
                                        embed = discord.Embed(
                                            title="✅ อัปโหลดรูปภาพสำเร็จ",
                                            description=f"อัปโหลดรูปภาพสำหรับสินค้า **{product_name}** เรียบร้อยแล้ว",
                                            color=0x2ecc71
                                        )
                                        embed.add_field(
                                            name="ℹ️ ระบบจัดเก็บ",
                                            value="ใช้ Discord CDN สำหรับความเร็วและเสถียรภาพ",
                                            inline=False
                                        )
                                        embed.set_image(url=image_url)
                                        await message.reply(embed=embed)
                                        break
                                else:
                                    embed = discord.Embed(
                                        title="❌ ไม่พบสินค้า",
                                        description=f"ไม่พบสินค้า **{product_name}** ในระบบ",
                                        color=0xe74c3c
                                    )
                                    await message.reply(embed=embed)
                            else:
                                embed = discord.Embed(
                                    title="❌ อัปโหลดรูปภาพไม่สำเร็จ",
                                    description="เกิดข้อผิดพลาดในการอัปโหลดรูปภาพ",
                                    color=0xe74c3c
                                )
                                await message.reply(embed=embed)
                        else:
                            embed = discord.Embed(
                                title="💡 วิธีอัปโหลดรูปภาพ",
                                description="กรุณาใส่ชื่อสินค้าหลังจาก `upload:` เช่น `upload: ชื่อสินค้า`",
                                color=0x3498db
                            )
                            await message.reply(embed=embed)
                    except Exception as e:
                        embed = discord.Embed(
                            title="❌ เกิดข้อผิดพลาด",
                            description=f"เกิดข้อผิดพลาดในการอัปโหลดรูปภาพ: {str(e)}",
                            color=0xe74c3c
                        )
                        await message.reply(embed=embed)
                
                # ตรวจสอบว่าผู้ใช้อยู่ในสถานะรอการอัปโหลดรูปหรือไม่
                elif str(message.author.id) in pending_image_uploads:
                    try:
                        product_data = pending_image_uploads[str(message.author.id)]
                        product_name = product_data['product_name']
                        
                        # ใช้ Discord CDN สำหรับรูปภาพ
                        filename = f"{product_name}_{attachment.filename}"
                        image_url = await stock_manager.upload_image_to_drive(attachment.url, filename)
                        
                        if image_url:
                            # สร้างสินค้าใหม่พร้อมรูปภาพ
                            success = stock_manager.add_stock(
                                product_name,
                                product_data['quantity'],
                                product_data['unit'],
                                message.author,
                                product_data['price'],
                                product_data['description'],
                                image_url
                            )
                            
                            if success:
                                embed = discord.Embed(
                                    title="✅ สร้างสินค้าพร้อมรูปภาพสำเร็จ",
                                    description=f"สร้างสินค้า **{product_name}** พร้อมรูปภาพเรียบร้อยแล้ว",
                                    color=0x2ecc71
                                )
                                embed.add_field(
                                    name="ℹ️ ระบบจัดเก็บ",
                                    value="ใช้ Discord CDN สำหรับความเร็วและเสถียรภาพ",
                                    inline=False
                                )
                                embed.add_field(name="จำนวน", value=f"{product_data['quantity']} {product_data['unit']}", inline=True)
                                if product_data['price'] > 0:
                                    embed.add_field(name="ราคา", value=f"{product_data['price']:,.0f}", inline=True)
                                if product_data['description']:
                                    embed.add_field(name="คำอธิบาย", value=product_data['description'], inline=False)
                                embed.set_image(url=image_url)
                                embed.set_footer(text=f"ดำเนินการโดย {message.author}")
                                await message.reply(embed=embed)
                            else:
                                embed = discord.Embed(
                                    title="❌ เกิดข้อผิดพลาด",
                                    description="ไม่สามารถสร้างสินค้าได้",
                                    color=0xe74c3c
                                )
                                await message.reply(embed=embed)
                        else:
                            embed = discord.Embed(
                                title="❌ อัปโหลดรูปภาพไม่สำเร็จ",
                                description="เกิดข้อผิดพลาดในการอัปโหลดรูปภาพ",
                                color=0xe74c3c
                            )
                            await message.reply(embed=embed)
                        
                        # ลบข้อมูลออกจาก pending_image_uploads
                        del pending_image_uploads[str(message.author.id)]
                        
                    except Exception as e:
                        embed = discord.Embed(
                            title="❌ เกิดข้อผิดพลาด",
                            description=f"เกิดข้อผิดพลาดในการอัปโหลดรูปภาพ: {str(e)}",
                            color=0xe74c3c
                        )
                        await message.reply(embed=embed)
                        
                        # ลบข้อมูลออกจาก pending_image_uploads แม้จะเกิดข้อผิดพลาด
                        if str(message.author.id) in pending_image_uploads:
                            del pending_image_uploads[str(message.author.id)]
                
                # ถ้าไม่ใช่ทั้งสองกรณีข้างต้น แสดงข้อความแนะนำ
                else:
                    # ตรวจสอบว่าข้อความไม่ใช่คำสั่ง
                    if not message.content.startswith('!'):
                        embed = discord.Embed(
                            title="📸 พบรูปภาพ",
                            description="หากต้องการอัปโหลดรูปภาพสำหรับสินค้า กรุณาใช้วิธีใดวิธีหนึ่งต่อไปนี้:",
                            color=0x3498db
                        )
                        embed.add_field(
                            name="🔧 วิธีที่ 1",
                            value="พิมพ์ `upload: ชื่อสินค้า` พร้อมแนบรูปภาพ",
                            inline=False
                        )
                        embed.add_field(
                            name="🆕 วิธีที่ 2",
                            value="ใช้ปุ่ม 'สร้างสินค้าใหม่' จากเมนูหลัก แล้วส่งรูปภาพตามคำแนะนำ",
                            inline=False
                        )
                        embed.add_field(
                            name="💡 คำแนะนำ",
                            value="พิมพ์ `!upload_help` เพื่อดูคำแนะนำเพิ่มเติม",
                            inline=False
                        )
                        await message.reply(embed=embed)
    
    # ดำเนินการคำสั่งปกติ
    await bot.process_commands(message)

# รัน bot
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))
