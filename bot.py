import discord
from discord.ext import commands
import gspread
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv
import datetime
import asyncio
from ui_components import AdvancedStockView, StockModal, ProductSelectView, ConfirmationView, ImageUploadView

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
                        stock_sheet.update(f'H{row_number}', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                        
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
                            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
                    stock_sheet.update(f'H{i+2}', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
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
                    datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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

# สร้าง instance ของ StockManager
stock_manager = StockManager()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user} เชื่อมต่อสำเร็จ!')
    print(f'🔗 เชื่อมต่อกับ Google Sheets: {os.getenv("GOOGLE_SHEET_NAME")}')
    
    # ตรวจสอบสินค้าใกล้หมดทุก 30 นาที
    bot.loop.create_task(low_stock_checker())

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
        name="💡 ตัวอย่างการใช้งาน",
        value="""
        `!add ปากกา 10 ด้าม 15` - เพิ่มปากกา 10 ด้าม ราคา 15 บาท
        `!remove ปากกา 2` - ลดปากกา 2 ด้าม
        `!check ปากกา` - ตรวจสอบปากกา
        `upload: ปากกา` + แนบรูปภาพ - อัปโหลดรูปปากกา
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
