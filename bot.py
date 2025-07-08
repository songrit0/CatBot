import discord
from discord.ext import commands
import gspread
from google.oauth2.service_account import Credentials
import os
from dotenv import load_dotenv
import datetime
import asyncio
import json
from ui_components import AdvancedStockView, StockModal, ProductSelectView, ConfirmationView

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
    
    def setup_sheets(self):
        """สร้างชีตและตั้งค่าหัวตาราง"""
        try:
            # ตรวจสอบและสร้างชีต Stock
            try:
                stock_sheet = self.spreadsheet.worksheet('Stock')
            except gspread.WorksheetNotFound:
                stock_sheet = self.spreadsheet.add_worksheet(title='Stock', rows=1000, cols=5)
                # ตั้งค่าหัวตาราง
                stock_sheet.update(
                    range_name='A1:E1',
                    values=[['ID', 'ชื่อสินค้า', 'จำนวน', 'หน่วย', 'วันที่อัปเดตล่าสุด']]
                )
            
            # ตรวจสอบและสร้างชีต History
            try:
                history_sheet = self.spreadsheet.worksheet('History')
            except gspread.WorksheetNotFound:
                history_sheet = self.spreadsheet.add_worksheet(title='History', rows=1000, cols=6)
                # ตั้งค่าหัวตาราง
                history_sheet.update(
                    range_name='A1:F1',
                    values=[['วันที่', 'ชื่อผู้ใช้', 'การทำรายการ', 'ชื่อสินค้า', 'จำนวน', 'หมายเหตุ']]
                )
                
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการสร้างชีต: {e}")
    
    def add_stock(self, product_name, quantity, unit, user):
        """เพิ่มสินค้าเข้าสต๊อก"""
        try:
            stock_sheet = self.spreadsheet.worksheet('Stock')
            
            # ค้นหาสินค้าที่มีอยู่
            existing_products = stock_sheet.get_all_records()
            product_found = False
            
            for i, product in enumerate(existing_products):
                if product['ชื่อสินค้า'].lower() == product_name.lower():
                    # อัปเดตจำนวนสินค้าที่มีอยู่
                    new_quantity = int(product['จำนวน']) + int(quantity)
                    stock_sheet.update(f'C{i+2}', new_quantity)
                    stock_sheet.update(f'E{i+2}', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    product_found = True
                    break
            
            if not product_found:
                # เพิ่มสินค้าใหม่
                next_row = len(existing_products) + 2
                new_id = len(existing_products) + 1
                stock_sheet.update(
                    range_name=f'A{next_row}:E{next_row}',
                    values=[[
                        new_id,
                        product_name,
                        quantity,
                        unit,
                        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ]]
                )
            
            # บันทึกประวัติ
            self.add_history(user, 'เพิ่มสินค้า', product_name, quantity, f'หน่วย: {unit}')
            
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
                    stock_sheet.update(f'E{i+2}', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    
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
            next_row = len(history_sheet.get_all_records()) + 2
            
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
                                    name=f"🔴 {product['ชื่อสินค้า']}",
                                    value=f"จำนวน: {product['จำนวน']} {product['หน่วย']}",
                                    inline=True
                                )
                            
                            await channel.send(embed=embed)
                            break
                        
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการตรวจสอบสินค้าใกล้หมด: {e}")

@bot.command(name='add')
async def add_stock(ctx, product_name: str, quantity: int, unit: str):
    """เพิ่มสินค้าเข้าสต๊อก"""
    if stock_manager.add_stock(product_name, quantity, unit, ctx.author):
        embed = discord.Embed(
            title="✅ เพิ่มสินค้าสำเร็จ",
            description=f"เพิ่ม **{product_name}** จำนวน **{quantity} {unit}** แล้ว",
            color=0x2ecc71
        )
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
        quantity = int(product['จำนวน'])
        status_emoji = "⚠️" if quantity < LOW_STOCK_THRESHOLD else "✅"
        
        embed = discord.Embed(
            title=f"{status_emoji} {product['ชื่อสินค้า']}",
            color=0xe74c3c if quantity < LOW_STOCK_THRESHOLD else 0x2ecc71
        )
        
        embed.add_field(name="จำนวน", value=f"{quantity} {product['หน่วย']}", inline=True)
        embed.add_field(name="อัปเดตล่าสุด", value=product['วันที่อัปเดตล่าสุด'], inline=True)
        
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
            quantity = int(product['จำนวน'])
            status_emoji = "⚠️" if quantity < LOW_STOCK_THRESHOLD else "✅"
            
            embed.add_field(
                name=f"{status_emoji} {product['ชื่อสินค้า']}",
                value=f"จำนวน: {quantity} {product['หน่วย']}\nอัปเดต: {product['วันที่อัปเดตล่าสุด']}",
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
                name=f"{record['การทำรายการ']} - {record['ชื่อสินค้า']}",
                value=f"ผู้ใช้: {record['ชื่อผู้ใช้']}\nจำนวน: {record['จำนวน']}\nวันที่: {record['วันที่']}\nหมายเหตุ: {record['หมายเหตุ']}",
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
        `!add [ชื่อสินค้า] [จำนวน] [หน่วย]` - เพิ่มสินค้า
        `!remove [ชื่อสินค้า] [จำนวน]` - ลดสินค้า
        `!check [ชื่อสินค้า]` - ตรวจสอบสินค้า
        `!list` - รายการสินค้าทั้งหมด
        `!history` - ประวัติการทำรายการ
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
        `!add [ชื่อสินค้า] [จำนวน] [หน่วย]` - เพิ่มสินค้า
        `!remove [ชื่อสินค้า] [จำนวน]` - ลดสินค้า
        `!check [ชื่อสินค้า]` - ตรวจสอบสินค้า
        `!list` - รายการสินค้าทั้งหมด
        `!history` - ประวัติการทำรายการ
        """,
        inline=False
    )
    
    embed.add_field(
        name="💡 ตัวอย่างการใช้งาน",
        value="""
        `!add ปากกา 10 ด้าม`
        `!remove ปากกา 2`
        `!check ปากกา`
        """,
        inline=False
    )
    
    embed.set_footer(text="ระบบจะแจ้งเตือนอัตโนมัติเมื่อสินค้าเหลือน้อยกว่า 5 ชิ้น")
    
    await ctx.send(embed=embed, view=AdvancedStockView(stock_manager))

# รัน bot
if __name__ == "__main__":
    bot.run(os.getenv('DISCORD_TOKEN'))
