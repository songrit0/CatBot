import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput, Select
from datetime import datetime
import json
import os
import asyncio
from ui.views.product_card_view import ProductCardView

# ฟังก์ชันช่วยสำหรับการลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย
async def remove_seller_permission(interaction, seller_user):
    """ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย"""
    try:
        # ตรวจสอบว่าเป็นห้องที่สามารถจัดการสิทธิ์ได้
        if isinstance(interaction.channel, discord.TextChannel):
            # ลบสิทธิ์ของผู้ขายออกจากห้องนี้
            overwrite = discord.PermissionOverwrite()
            overwrite.view_channel = False
            overwrite.send_messages = False
            overwrite.read_message_history = False
            
            await interaction.channel.set_permissions(seller_user, overwrite=overwrite)
            
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
                await interaction.followup.send(embed=embed, ephemeral=False)
            except:
                pass  # ถ้าไม่สามารถส่งข้อความได้ก็ข้าม
            
            print(f"✅ ลบสิทธิ์ผู้ขาย {seller_user.name} ({seller_user.id}) ออกจากห้อง {interaction.channel.name} ({interaction.channel.id}) เรียบร้อยแล้ว")
            
        else:
            print(f"❌ ไม่สามารถลบสิทธิ์ได้: ห้องนี้ไม่ใช่ TextChannel")
            
    except discord.Forbidden:
        print(f"❌ ไม่มีสิทธิ์ในการจัดการสิทธิ์ของห้อง {interaction.channel.name}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการลบสิทธิ์: {e}")

class StockModal(discord.ui.Modal):
    def __init__(self, action_type, stock_manager):
        super().__init__(title=f"📦 {action_type}สินค้า")
        self.action_type = action_type
        self.stock_manager = stock_manager
        
        # Product name input
        self.product_name = discord.ui.TextInput(
            label="ชื่อสินค้า",
            placeholder="กรอกชื่อสินค้า...",
            required=True,
            max_length=100
        )
        self.add_item(self.product_name)
        
        # Quantity input
        self.quantity = discord.ui.TextInput(
            label="จำนวน",
            placeholder="กรอกจำนวน...",
            required=True,
            max_length=10
        )
        self.add_item(self.quantity)
        
        # Unit input (only for add action)
        if action_type == "เพิ่ม":
            self.unit = discord.ui.TextInput(
                label="หน่วย",
                placeholder="กรอกหน่วย (เช่น ชิ้น, ก้อน, ถุง)...",
                required=True,
                max_length=50
            )
            self.add_item(self.unit)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            product_name = self.product_name.value.strip()
            quantity = int(self.quantity.value)
            
            if self.action_type == "เพิ่ม":
                unit = self.unit.value.strip()
                success = self.stock_manager.add_stock(product_name, quantity, unit, interaction.user, 0, "", "")
                
                if success:
                    embed = discord.Embed(
                        title="✅ เพิ่มสินค้าสำเร็จ",
                        description=f"เพิ่ม **{product_name}** จำนวน **{quantity} {unit}** แล้ว",
                        color=0x2ecc71
                    )
                    embed.set_footer(text=f"ดำเนินการโดย {interaction.user}")
                    await interaction.followup.send(embed=embed, view=AdvancedStockView(self.stock_manager))
                else:
                    raise Exception("ไม่สามารถเพิ่มสินค้าได้")
            
            elif self.action_type == "ลด":
                success, remaining = self.stock_manager.remove_stock(product_name, quantity, interaction.user)
                
                if success:
                    embed = discord.Embed(
                        title="✅ ลดสินค้าสำเร็จ",
                        description=f"ลด **{product_name}** จำนวน **{quantity}** แล้ว\nคงเหลือ: **{remaining}**",
                        color=0x2ecc71
                    )
                    
                    if remaining < 5:
                        embed.add_field(
                            name="⚠️ แจ้งเตือน",
                            value="สินค้าใกล้หมดแล้ว กรุณาเติมสินค้า",
                            inline=False
                        )
                    
                    embed.set_footer(text=f"ดำเนินการโดย {interaction.user}")
                    await interaction.followup.send(embed=embed, view=AdvancedStockView(self.stock_manager))
                else:
                    raise Exception("ไม่พบสินค้าหรือไม่สามารถลดสินค้าได้")
        
        except ValueError:
            embed = discord.Embed(
                title="❌ ข้อมูลไม่ถูกต้อง",
                description="กรุณาใส่จำนวนเป็นตัวเลข",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=str(e),
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)

class ProductSelectView(discord.ui.View):
    def __init__(self, stock_manager, action_type):
        super().__init__(timeout=300)
        self.stock_manager = stock_manager
        self.action_type = action_type
        
        # Get product list for dropdown
        products = stock_manager.get_all_stock()
        
        if products:
            options = []
            for product in products[:25]:  # Discord limit is 25 options
                quantity = int(product.get('จำนวน', 0))
                emoji = "⚠️" if quantity < 5 else "✅"
                options.append(
                    discord.SelectOption(
                        label=f"{product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')} ({quantity} {product.get('หน่วย', 'ชิ้น')})",
                        value=product.get('ชื่อสินค้า', ''),
                        emoji=emoji,
                        description=f"อัปเดต: {product.get('วันที่อัปเดตล่าสุด', 'ไม่ระบุ')}"
                    )
                )
            
            self.product_select = discord.ui.Select(
                placeholder=f"เลือกสินค้าที่ต้องการ{action_type}...",
                options=options
            )
            self.product_select.callback = self.product_selected
            self.add_item(self.product_select)
        else:
            # No products available
            self.add_item(discord.ui.Button(label="ไม่มีสินค้าในระบบ", disabled=True))
    
    async def product_selected(self, interaction: discord.Interaction):
        selected_product = self.product_select.values[0]
        
        if self.action_type == "ตรวจสอบ":
            product = self.stock_manager.check_stock(selected_product)
            
            if product:
                quantity = int(product.get('จำนวน', 0))
                status_emoji = "⚠️" if quantity < 5 else "✅"
                price = float(product.get('ราคา', 0)) if product.get('ราคา') else 0
                
                embed = discord.Embed(
                    title=f"{status_emoji} {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
                    color=0xe74c3c if quantity < 5 else 0x2ecc71
                )
                
                embed.add_field(name="จำนวน", value=f"{quantity} {product.get('หน่วย', 'ชิ้น')}", inline=True)
                if price > 0:
                    embed.add_field(name="ราคา", value=f"{price:,.0f}", inline=True)
                embed.add_field(name="อัปเดตล่าสุด", value=product.get('วันที่อัปเดตล่าสุด', 'ไม่ระบุ'), inline=True)
                
                if product.get('คำอธิบาย'):
                    embed.add_field(name="คำอธิบาย", value=product.get('คำอธิบาย'), inline=False)
                
                if product.get('รูปภาพURL'):
                    embed.set_image(url=product.get('รูปภาพURL'))
                
                if quantity < 5:
                    embed.add_field(
                        name="⚠️ แจ้งเตือน",
                        value="สินค้าใกล้หมดแล้ว",
                        inline=False
                    )
                
                await interaction.response.send_message(embed=embed, view=AdvancedStockView(self.stock_manager))
            else:
                embed = discord.Embed(
                    title="❌ ไม่พบสินค้า",
                    description="เกิดข้อผิดพลาดในการค้นหาสินค้า",
                    color=0xe74c3c
                )
                await interaction.response.send_message(embed=embed)
        
        elif self.action_type == "เพิ่มรูปภาพ":
            # สร้าง view สำหรับเพิ่มรูปภาพ
            image_view = ImageUploadView(self.stock_manager, selected_product)
            
            embed = discord.Embed(
                title="📸 เพิ่มรูปภาพสินค้า",
                description=f"เลือกวิธีเพิ่มรูปภาพสำหรับ **{selected_product}**",
                color=0x3498db
            )
            embed.add_field(
                name="🔧 วิธีที่ 1: ใช้รูปภาพล่าสุด",
                value=
                "อัพรูปภาพล่าสุดใน channel นี้ แล้วคลิกปุ่ม 'ใช้รูปภาพล่าสุด' เพื่อใช้รูปภาพที่ส่งล่าสุดใน channel นี้",
                inline=False
            )
            embed.add_field(
                name="🔧 วิธีที่ 2: ส่งรูปภาพใหม่",
                value="ส่งรูปภาพใหม่ในช่องนี้ พร้อมข้อความ `upload: " + selected_product + "`",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=image_view)
        
        else:
            # For add/remove actions, show quantity input modal
            modal = StockModal(self.action_type, self.stock_manager)
            modal.product_name.default = selected_product
            await interaction.response.send_modal(modal)

class AdvancedStockView(discord.ui.View):
    def __init__(self, stock_manager):
        super().__init__(timeout=300)
        self.stock_manager = stock_manager
    
    # @discord.ui.button(label='เพิ่มสินค้า', style=discord.ButtonStyle.success, emoji='➕')
    # async def add_stock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     modal = StockModal("เพิ่ม", self.stock_manager)
    #     await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='สร้างสินค้าใหม่', style=discord.ButtonStyle.primary, emoji='🆕')
    async def create_new_product_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NewProductModal(self.stock_manager)
        await interaction.response.send_modal(modal)
    
    # @discord.ui.button(label='ลดสินค้า', style=discord.ButtonStyle.danger, emoji='➖')
    # async def remove_stock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     await interaction.response.send_message(
    #         "เลือกสินค้าที่ต้องการลด:",
    #         view=ProductSelectView(self.stock_manager, "ลด"),
    #         ephemeral=True
    #     )
    
    @discord.ui.button(label='ตรวจสอบสินค้า', style=discord.ButtonStyle.secondary, emoji='🔍')
    async def check_stock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "เลือกสินค้าที่ต้องการตรวจสอบ:",
            view=ProductSelectView(self.stock_manager, "ตรวจสอบ"),
            ephemeral=True
        )
    
    @discord.ui.button(label='รายการสินค้า', style=discord.ButtonStyle.primary, emoji='📦')
    async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # ใช้คำสั่ง !products เพื่อแสดงสินค้าเป็น card
        embed = discord.Embed(
            title="🏪 รายการสินค้าทั้งหมด",
            description="กำลังแสดงสินค้าทั้งหมดในรูปแบบ Product Card",
            color=0x4ecdc4
        )
        embed.add_field(
            name="💡 คำแนะนำ",
            value="• สินค้าจะถูกแสดงเป็น card แยกต่างหาก\n• แต่ละ card จะมีปุ่มสำหรับการซื้อ\n• คุณสามารถเลือกซื้อทันทีหรือเพิ่มเข้ารถเข็น",
            inline=False
        )
        await interaction.followup.send(embed=embed)
        
        # เรียกใช้ฟังก์ชัน products
        products = self.stock_manager.get_all_stock()
        
        if not products:
            no_products_embed = discord.Embed(
                title="📦 ไม่มีสินค้าในระบบ",
                description="ยังไม่มีสินค้าในระบบ กรุณาเพิ่มสินค้าก่อน",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=no_products_embed)
            return
        
        # แสดงสินค้าแต่ละรายการเป็น card พร้อมปุ่ม
        from ui.views.product_card_view import ProductCardView
        
        for product in products:
            quantity = int(product.get('จำนวน', 0))
            status_emoji = "⚠️" if quantity < 5 else "✅"
            price = float(product.get('ราคา', 0)) if product.get('ราคา') else 0
            
            embed = discord.Embed(
                title=f"{status_emoji} {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
                color=0xe74c3c if quantity < 5 else 0x2ecc71
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
            if quantity < 5:
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
            await interaction.followup.send(embed=embed, view=ProductCardView(product, self.stock_manager))
            
            # รอเล็กน้อยเพื่อไม่ให้ spam
            await asyncio.sleep(0.5)
    
    @discord.ui.button(label='เพิ่มรูปภาพ', style=discord.ButtonStyle.secondary, emoji='📸')
    async def add_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "เลือกสินค้าที่ต้องการเพิ่มรูปภาพ:",
            view=ProductSelectView(self.stock_manager, "เพิ่มรูปภาพ"),
            ephemeral=True
        )
    
    @discord.ui.button(label='ประวัติ', style=discord.ButtonStyle.secondary, emoji='📋')
    async def history_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        history = self.stock_manager.get_history(10)
        
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
        
        await interaction.followup.send(embed=embed, view=AdvancedStockView(self.stock_manager))
    
    @discord.ui.button(label='สินค้าใกล้หมด', style=discord.ButtonStyle.danger, emoji='⚠️')
    async def low_stock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        low_stock_items = self.stock_manager.check_low_stock()
        
        if not low_stock_items:
            embed = discord.Embed(
                title="⚠️ สินค้าใกล้หมด",
                description="ไม่มีสินค้าที่ใกล้หมด",
                color=0x2ecc71
            )
        else:
            embed = discord.Embed(
                title="⚠️ สินค้าใกล้หมด (น้อยกว่า 5 ชิ้น)",
                description="รายการสินค้าที่ควรเติมเพิ่ม",
                color=0xe74c3c
            )
            
            for product in low_stock_items:
                embed.add_field(
                    name=f"🔴 {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
                    value=f"จำนวน: {product.get('จำนวน', 0)} {product.get('หน่วย', 'ชิ้น')}\nอัปเดต: {product.get('วันที่อัปเดตล่าสุด', 'ไม่ระบุ')}",
                    inline=True
                )
        
        await interaction.followup.send(embed=embed, view=AdvancedStockView(self.stock_manager))

class ConfirmationView(discord.ui.View):
    def __init__(self, action, product_name, quantity, stock_manager, user):
        super().__init__(timeout=30)
        self.action = action
        self.product_name = product_name
        self.quantity = quantity
        self.stock_manager = stock_manager
        self.user = user
        self.result = None
    
    @discord.ui.button(label='✅ ยืนยัน', style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("คุณไม่มีสิทธิ์ยืนยันการทำรายการนี้", ephemeral=True)
            return
        
        self.result = True
        self.stop()
        await interaction.response.send_message("✅ ยืนยันการทำรายการแล้ว", ephemeral=True)
    
    @discord.ui.button(label='❌ ยกเลิก', style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message("คุณไม่มีสิทธิ์ยกเลิกการทำรายการนี้", ephemeral=True)
            return
        
        self.result = False
        self.stop()
        await interaction.response.send_message("❌ ยกเลิกการทำรายการแล้ว", ephemeral=True)

class NewProductModal(discord.ui.Modal):
    def __init__(self, stock_manager):
        super().__init__(title="🆕 สร้างสินค้าใหม่")
        self.stock_manager = stock_manager
        
        # Product name input
        self.product_name = discord.ui.TextInput(
            label="ชื่อสินค้า",
            placeholder="กรอกชื่อสินค้า...",
            required=True,
            max_length=100
        )
        self.add_item(self.product_name)
        
        # Quantity input
        self.quantity = discord.ui.TextInput(
            label="จำนวน",
            placeholder="กรอกจำนวน...",
            required=True,
            max_length=10
        )
        self.add_item(self.quantity)
        
        # Unit input
        self.unit = discord.ui.TextInput(
            label="หน่วย",
            placeholder="กรอกหน่วย (เช่น ชิ้น, ก้อน, ถุง)...",
            required=True,
            max_length=50
        )
        self.add_item(self.unit)
        
        # Price input
        self.price = discord.ui.TextInput(
            label="ราคา",
            placeholder="กรอกราคา (ไม่บังคับ)...",
            required=False,
            max_length=10
        )
        self.add_item(self.price)
        
        # Description input
        self.description = discord.ui.TextInput(
            label="คำอธิบาย",
            placeholder="กรอกคำอธิบายสินค้า (ไม่บังคับ)...",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.description)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            product_name = self.product_name.value.strip()
            quantity = int(self.quantity.value)
            unit = self.unit.value.strip()
            price = float(self.price.value) if self.price.value.strip() else 0
            description = self.description.value.strip() if self.description.value else ""
            
            # ส่งข้อความให้ผู้ใช้อัปโหลดรูปภาพ
            embed = discord.Embed(
                title="📸 อัปโหลดรูปภาพสินค้า",
                description=f"กรุณาส่งรูปภาพสำหรับสินค้า **{product_name}**\n\n💡 คุณสามารถแนบรูปภาพในข้อความถัดไปได้",
                color=0x3498db
            )
            embed.add_field(name="ชื่อสินค้า", value=product_name, inline=True)
            embed.add_field(name="จำนวน", value=f"{quantity} {unit}", inline=True)
            embed.add_field(name="ราคา", value=f"{price:,.0f}" if price > 0 else "ไม่ระบุ", inline=True)
            if description:
                embed.add_field(name="คำอธิบาย", value=description, inline=False)
            
            # เก็บข้อมูลสินค้าไว้ใน pending_image_uploads
            import bot
            bot.pending_image_uploads[str(interaction.user.id)] = {
                'product_name': product_name,
                'quantity': quantity,
                'unit': unit,
                'price': price,
                'description': description
            }
            
            # สร้าง view สำหรับรอการอัปโหลดรูป
            view = ImageUploadView(self.stock_manager, product_name, quantity, unit, price, description)
            
            await interaction.followup.send(embed=embed, view=view)
            
        except ValueError:
            embed = discord.Embed(
                title="❌ ข้อมูลไม่ถูกต้อง",
                description="กรุณาใส่จำนวนและราคาเป็นตัวเลข",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=str(e),
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)

class ImageUploadView(discord.ui.View):
    def __init__(self, stock_manager, product_name, quantity=None, unit=None, price=None, description=None):
        super().__init__(timeout=300)
        self.stock_manager = stock_manager
        self.product_name = product_name
        self.quantity = quantity
        self.unit = unit
        self.price = price
        self.description = description
        self.is_new_product = quantity is not None  # ถ้ามี quantity แสดงว่าเป็นการสร้างสินค้าใหม่
    
    @discord.ui.button(label='ใช้รูปภาพล่าสุด', style=discord.ButtonStyle.primary, emoji='📸')
    async def use_latest_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # ค้นหารูปภาพล่าสุดใน channel
        latest_image = await self.find_latest_image_in_channel(interaction.channel)
        
        if latest_image:
            # อัปโหลดรูปภาพด้วย Discord CDN
            filename = f"{self.product_name}_{latest_image.filename}"
            image_url = await self.stock_manager.upload_image_to_drive(latest_image.url, filename)
            
            if image_url:
                if self.is_new_product:
                    # สร้างสินค้าใหม่พร้อมรูปภาพ
                    import bot
                    if str(interaction.user.id) in bot.pending_image_uploads:
                        del bot.pending_image_uploads[str(interaction.user.id)]
                    
                    success = self.stock_manager.add_stock(
                        self.product_name, 
                        self.quantity, 
                        self.unit, 
                        interaction.user, 
                        self.price, 
                        self.description, 
                        image_url
                    )
                    
                    if success:
                        embed = discord.Embed(
                            title="✅ สร้างสินค้าสำเร็จ",
                            description=f"สร้างสินค้า **{self.product_name}** พร้อมรูปภาพเรียบร้อยแล้ว",
                            color=0x2ecc71
                        )
                        embed.set_footer(text=f"ดำเนินการโดย {interaction.user}")
                        embed.set_image(url=image_url)
                        await interaction.followup.send(embed=embed, view=AdvancedStockView(self.stock_manager))
                    else:
                        embed = discord.Embed(
                            title="❌ เกิดข้อผิดพลาด",
                            description="ไม่สามารถสร้างสินค้าได้",
                            color=0xe74c3c
                        )
                        await interaction.followup.send(embed=embed)
                else:
                    # อัปเดตรูปภาพสินค้าเดิม
                    products = self.stock_manager.get_all_stock()
                    for product in products:
                        if product['ชื่อสินค้า'].lower() == self.product_name.lower():
                            # อัปเดต URL รูปภาพในชีต
                            stock_sheet = self.stock_manager.spreadsheet.worksheet('Stock')
                            existing_products = stock_sheet.get_all_records()
                            
                            for i, p in enumerate(existing_products):
                                if p['ชื่อสินค้า'].lower() == self.product_name.lower():
                                    stock_sheet.update(f'G{i+2}', image_url)
                                    break
                            
                            embed = discord.Embed(
                                title="✅ เพิ่มรูปภาพสำเร็จ",
                                description=f"เพิ่มรูปภาพสำหรับสินค้า **{self.product_name}** เรียบร้อยแล้ว",
                                color=0x2ecc71
                            )
                            embed.add_field(
                                name="ℹ️ ระบบจัดเก็บ",
                                value="ใช้ Discord CDN สำหรับความเร็วและเสถียรภาพ",
                                inline=False
                            )
                            embed.add_field(
                                name="📸 รูปภาพที่เพิ่ม",
                                value=f"ใช้รูปภาพล่าสุดจาก {latest_image.filename}",
                                inline=False
                            )
                            embed.set_image(url=image_url)
                            await interaction.followup.send(embed=embed)
                            return
                            
                    embed = discord.Embed(
                        title="❌ ไม่พบสินค้า",
                        description=f"ไม่พบสินค้า **{self.product_name}** ในระบบ",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ อัปโหลดรูปภาพไม่สำเร็จ",
                    description="เกิดข้อผิดพลาดในการอัปโหลดรูปภาพ",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ ไม่พบรูปภาพ",
                description="ไม่พบรูปภาพล่าสุดใน channel นี้",
                color=0xe74c3c
            )
            embed.add_field(
                name="💡 คำแนะนำ",
                value="กรุณาส่งรูปภาพในช่องนี้ก่อน หรือใช้ปุ่ม 'คำแนะนำการอัปโหลด'",
                inline=False
            )
            await interaction.followup.send(embed=embed)
    
    @discord.ui.button(label='คำแนะนำการอัปโหลด', style=discord.ButtonStyle.secondary, emoji='💡')
    async def upload_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📸 วิธีเพิ่มรูปภาพสินค้า",
            description=f"วิธีเพิ่มรูปภาพสำหรับสินค้า **{self.product_name}**",
            color=0x3498db
        )
        
        embed.add_field(
            name="🔧 วิธีที่ 1: ใช้รูปภาพล่าสุด",
            value="อัพรูปภาพล่าสุดใน channel นี้ แล้วคลิกปุ่ม 'ใช้รูปภาพล่าสุด' เพื่อใช้รูปภาพที่ส่งล่าสุดใน channel นี้",
            inline=False
        )
        
        embed.add_field(
            name="🔧 วิธีที่ 2: ส่งรูปภาพใหม่",
            value=f"ส่งรูปภาพใหม่ในช่องนี้ พร้อมข้อความ `upload: {self.product_name}`",
            inline=False
        )
        
        embed.add_field(
            name="📁 รองรับไฟล์",
            value="JPG, PNG, GIF, WEBP",
            inline=True
        )
        
        embed.add_field(
            name="🔗 ระบบจัดเก็บ",
            value="Discord CDN",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='สร้างสินค้าโดยไม่มีรูป', style=discord.ButtonStyle.secondary, emoji='📦')
    async def create_without_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_new_product:
            embed = discord.Embed(
                title="❌ ไม่สามารถทำรายการได้",
                description="ฟังก์ชันนี้ใช้สำหรับสร้างสินค้าใหม่เท่านั้น",
                color=0xe74c3c
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # ลบข้อมูลออกจาก pending_image_uploads
        import bot
        if str(interaction.user.id) in bot.pending_image_uploads:
            del bot.pending_image_uploads[str(interaction.user.id)]
        
        success = self.stock_manager.add_stock(
            self.product_name, 
            self.quantity, 
            self.unit, 
            interaction.user, 
            self.price, 
            self.description, 
            ""
        )
        
        if success:
            embed = discord.Embed(
                title="✅ สร้างสินค้าสำเร็จ",
                description=f"สร้างสินค้า **{self.product_name}** เรียบร้อยแล้ว",
                color=0x2ecc71
            )
            embed.set_footer(text=f"ดำเนินการโดย {interaction.user}")
            await interaction.followup.send(embed=embed, view=AdvancedStockView(self.stock_manager))
        else:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description="ไม่สามารถสร้างสินค้าได้",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed)
    
    @discord.ui.button(label='ยกเลิก', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.is_new_product:
            # ลบข้อมูลออกจาก pending_image_uploads
            import bot
            if str(interaction.user.id) in bot.pending_image_uploads:
                del bot.pending_image_uploads[str(interaction.user.id)]
            
            embed = discord.Embed(
                title="❌ ยกเลิกการสร้างสินค้า",
                description="การสร้างสินค้าถูกยกเลิก",
                color=0xe74c3c
            )
        else:
            embed = discord.Embed(
                title="❌ ยกเลิกการเพิ่มรูปภาพ",
                description="การเพิ่มรูปภาพถูกยกเลิก",
                color=0xe74c3c
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        self.stop()
    
    async def find_latest_image_in_channel(self, channel, limit=50):
        """ค้นหารูปภาพล่าสุดใน channel"""
        try:
            async for message in channel.history(limit=limit):
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            return attachment
            return None
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการค้นหารูปภาพ: {e}")
            return None

class ProductCardView(discord.ui.View):
    def __init__(self, stock_manager, product_name):
        super().__init__(timeout=300)
        self.stock_manager = stock_manager
        self.product_name = product_name
    
    @discord.ui.button(label='Buy Now', style=discord.ButtonStyle.success, emoji='💰')
    async def buy_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="🛒 การซื้อสินค้า",
            description=f"คุณต้องการซื้อ **{self.product_name}** หรือไม่?",
            color=0x2ecc71
        )
        embed.add_field(
            name="💡 วิธีซื้อ",
            value=f"ใช้คำสั่ง `!buy {self.product_name}` เพื่อซื้อสินค้า",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='Add to cart', style=discord.ButtonStyle.primary, emoji='🛒')
    async def add_to_cart(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Defer the interaction immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        try:
            # ดึงข้อมูลสินค้าจากสต็อก
            product = self.stock_manager.check_stock(self.product_name)
            
            if product:
                # Import user_carts from bot.py
                from bot import user_carts, Cart
                
                user_id = str(interaction.user.id)
                if user_id not in user_carts:
                    user_carts[user_id] = Cart()
                
                # เพิ่มสินค้าลงรถเข็น (จำนวน 1 ชิ้น)
                price = float(product.get('ราคา', 0))
                unit = product.get('หน่วย', 'ชิ้น')
                quantity = 1
                
                # ตรวจสอบสต็อกเพียงพอหรือไม่
                available_quantity = int(product.get('จำนวน', 0))
                if available_quantity < quantity:
                    embed = discord.Embed(
                        title="❌ สต็อกไม่เพียงพอ",
                        description=f"สินค้า **{self.product_name}** เหลือเพียง {available_quantity} {unit}",
                        color=0xe74c3c
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                
                user_carts[user_id].add_item(self.product_name, quantity, price, unit)
                
                # แสดงรายการสินค้าในรถเข็นทั้งหมด
                cart = user_carts[user_id]
                cart_items = cart.get_items()
                total_price = cart.get_total()
                
                embed = discord.Embed(
                    title="✅ เพิ่มลงรถเข็นสำเร็จ",
                    description=f"เพิ่ม **{self.product_name}** x{quantity} ลงรถเข็นแล้ว!",
                    color=0x2ecc71
                )
                
                # แสดงรายการสินค้าในรถเข็นทั้งหมด
                cart_list = ""
                for i, item in enumerate(cart_items, 1):
                    item_total = item['price'] * item['quantity']
                    cart_list += f"{i}. **{item['product_name']}** x{item['quantity']} {item['unit']} = {item_total:,.0f} บาท\n"
                
                embed.add_field(
                    name="� รถเข็นของคุณ",
                    value=cart_list if cart_list else "ไม่มีสินค้า",
                    inline=False
                )
                
                embed.add_field(
                    name="💰 ยอดรวมทั้งหมด",
                    value=f"{total_price:,.0f} บาท",
                    inline=True
                )
                
                embed.add_field(
                    name="� จำนวนรายการ",
                    value=f"{len(cart_items)} รายการ",
                    inline=True
                )
                
                embed.add_field(
                    name="💡 คำแนะนำ",
                    value="ใช้คำสั่ง `!checkout` เพื่อชำระเงิน\nใช้คำสั่ง `!cart` เพื่อดูรถเข็น\nใช้คำสั่ง `!clear_cart` เพื่อเคลียร์รถเข็น",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ ไม่พบสินค้า",
                    description=f"ไม่พบสินค้า **{self.product_name}** ในระบบ",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"ไม่สามารถเพิ่มสินค้าลงรถเข็นได้: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # @discord.ui.button(label='เพิ่มรูปภาพ', style=discord.ButtonStyle.secondary, emoji='📸')
    # async def add_image(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     await interaction.response.defer()
        
    #     # ค้นหารูปภาพล่าสุดใน channel
    #     latest_image = await self.find_latest_image_in_channel(interaction.channel)
        
    #     if latest_image:
    #         # อัปโหลดรูปภาพด้วย Discord CDN
    #         filename = f"{self.product_name}_{latest_image.filename}"
    #         image_url = await self.stock_manager.upload_image_to_drive(latest_image.url, filename)
            
    #         if image_url:
    #             # อัปเดตข้อมูลสินค้าด้วย URL รูปภาพ
    #             products = self.stock_manager.get_all_stock()
    #             for product in products:
    #                 if product['ชื่อสินค้า'].lower() == self.product_name.lower():
    #                     # อัปเดต URL รูปภาพในชีต
    #                     stock_sheet = self.stock_manager.spreadsheet.worksheet('Stock')
    #                     existing_products = stock_sheet.get_all_records()
                        
    #                     for i, p in enumerate(existing_products):
    #                         if p['ชื่อสินค้า'].lower() == self.product_name.lower():
    #                             stock_sheet.update(f'G{i+2}', image_url)
    #                             break
                        
    #                     embed = discord.Embed(
    #                         title="✅ เพิ่มรูปภาพสำเร็จ",
    #                         description=f"เพิ่มรูปภาพสำหรับสินค้า **{self.product_name}** เรียบร้อยแล้ว",
    #                         color=0x2ecc71
    #                     )
    #                     embed.add_field(
    #                         name="ℹ️ ระบบจัดเก็บ",
    #                         value="ใช้ Discord CDN สำหรับความเร็วและเสถียรภาพ",
    #                         inline=False
    #                     )
    #                     embed.add_field(
    #                         name="📸 รูปภาพที่เพิ่ม",
    #                         value=f"ใช้รูปภาพล่าสุดจาก {latest_image.filename}",
    #                         inline=False
    #                     )
    #                     embed.set_image(url=image_url)
    #                     await interaction.followup.send(embed=embed)
    #                     return
                        
    #             embed = discord.Embed(
    #                 title="❌ ไม่พบสินค้า",
    #                 description=f"ไม่พบสินค้า **{self.product_name}** ในระบบ",
    #                 color=0xe74c3c
    #             )
    #             await interaction.followup.send(embed=embed)
    #         else:
    #             embed = discord.Embed(
    #                 title="❌ อัปโหลดรูปภาพไม่สำเร็จ",
    #                 description="เกิดข้อผิดพลาดในการอัปโหลดรูปภาพ",
    #                 color=0xe74c3c
    #             )
    #             await interaction.followup.send(embed=embed)
    #     else:
    #         embed = discord.Embed(
    #             title="❌ ไม่พบรูปภาพ",
    #             description="ไม่พบรูปภาพล่าสุดใน channel นี้",
    #             color=0xe74c3c
    #         )
    #         embed.add_field(
    #             name="💡 คำแนะนำ",
    #             value="กรุณาส่งรูปภาพในช่องนี้ก่อน หรือใช้คำสั่ง `upload: ชื่อสินค้า` พร้อมแนบรูปภาพ",
    #             inline=False
    #         )
    #         await interaction.followup.send(embed=embed)
    
    async def find_latest_image_in_channel(self, channel, limit=50):
        """ค้นหารูปภาพล่าสุดใน channel"""
        try:
            async for message in channel.history(limit=limit):
                if message.attachments:
                    for attachment in message.attachments:
                        if attachment.content_type and attachment.content_type.startswith('image/'):
                            return attachment
            return None
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการค้นหารูปภาพ: {e}")
            return None
    
    @discord.ui.button(label='Checkout', style=discord.ButtonStyle.secondary, emoji='💳')
    async def checkout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="💳 ชำระเงิน",
            description=f"กำลังดำเนินการชำระเงินสำหรับ **{self.product_name}**",
            color=0x9b59b6
        )
        embed.add_field(
            name="💡 การชำระเงิน",
            value="ระบบการชำระเงินจะเปิดให้บริการในเร็วๆ นี้",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label='เพิ่มรูปภาพ', style=discord.ButtonStyle.secondary, emoji='📸', row=1)
    async def add_image_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        await interaction.followup.send(
            "เลือกสินค้าที่ต้องการเพิ่มรูปภาพ:",
            view=ProductSelectView(self.stock_manager, "เพิ่มรูปภาพ"),
            ephemeral=True
        )

class SalesModal(discord.ui.Modal):
    def __init__(self, stock_manager):
        super().__init__(title="🛒 สร้างการขาย")
        self.stock_manager = stock_manager
        
        # รายการสินค้าที่ต้องการขาย
        self.items_input = discord.ui.TextInput(
            label="รายการสินค้า",
            placeholder="รูปแบบ: ชื่อสินค้า:จำนวน, ชื่อสินค้า:จำนวน\nตัวอย่าง: ปากกา:5, ยางลบ:3",
            required=True,
            max_length=2000,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.items_input)
        
        # หมายเหตุ
        self.notes = discord.ui.TextInput(
            label="หมายเหตุ (ไม่บังคับ)",
            placeholder="หมายเหตุเพิ่มเติม...",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            # แยกรายการสินค้า
            items_text = self.items_input.value.strip()
            items = []
            errors = []
            
            for item_text in items_text.split(','):
                item_text = item_text.strip()
                if ':' in item_text:
                    parts = item_text.split(':')
                    if len(parts) == 2:
                        product_name = parts[0].strip()
                        try:
                            quantity = int(parts[1].strip())
                            
                            # ตรวจสอบสินค้าในสต็อก
                            product = self.stock_manager.check_stock(product_name)
                            if product:
                                available_quantity = int(product['จำนวน'])
                                if available_quantity >= quantity:
                                    items.append({
                                        'name': product_name,
                                        'quantity': quantity,
                                        'price': float(product.get('ราคา', 0)),
                                        'unit': product.get('หน่วย', 'ชิ้น')
                                    })
                                else:
                                    errors.append(f"❌ {product_name}: สต็อกไม่เพียงพอ (มี {available_quantity} ต้องการ {quantity})")
                            else:
                                errors.append(f"❌ {product_name}: ไม่พบสินค้าในระบบ")
                        except ValueError:
                            errors.append(f"❌ {product_name}: จำนวนไม่ถูกต้อง")
                    else:
                        errors.append(f"❌ รูปแบบไม่ถูกต้อง: {item_text}")
                else:
                    errors.append(f"❌ รูปแบบไม่ถูกต้อง: {item_text}")
            
            if errors:
                embed = discord.Embed(
                    title="❌ พบข้อผิดพลาด",
                    description="\n".join(errors),
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            if not items:
                embed = discord.Embed(
                    title="❌ ไม่พบรายการสินค้า",
                    description="กรุณาใส่รายการสินค้าที่ต้องการขาย",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # แสดงรายการสินค้าที่จะขาย
            embed = discord.Embed(
                title="🛒 ยืนยันการขาย",
                description="กรุณาตรวจสอบรายการสินค้าที่จะขาย",
                color=0x3498db
            )
            
            total_amount = 0
            for item in items:
                item_total = item['quantity'] * item['price']
                total_amount += item_total
                
                embed.add_field(
                    name=f"📦 {item['name']}",
                    value=f"จำนวน: {item['quantity']} {item['unit']}\nราคา: {item['price']:,.0f} x {item['quantity']} = {item_total:,.0f}",
                    inline=True
                )
            
            embed.add_field(
                name="💰 ยอดรวมทั้งหมด",
                value=f"{total_amount:,.0f} บาท",
                inline=False
            )
            
            if self.notes.value:
                embed.add_field(
                    name="📝 หมายเหตุ",
                    value=self.notes.value,
                    inline=False
                )
            
            view = SalesConfirmView(self.stock_manager, items, self.notes.value)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"ไม่สามารถสร้างการขายได้: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class SalesConfirmView(discord.ui.View):
    def __init__(self, stock_manager, items, notes):
        super().__init__(timeout=300)
        self.stock_manager = stock_manager
        self.items = items
        self.notes = notes
    
    @discord.ui.button(label='ยืนยันการขาย', style=discord.ButtonStyle.success, emoji='✅')
    async def confirm_sale(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            # สร้างใบเสร็จ
            bill_number, total_amount = self.stock_manager.create_bill(
                interaction.user,
                self.items,
                self.notes
            )
            
            if bill_number:
                # สร้าง embed ใบเสร็จ
                embed = discord.Embed(
                    title="🧾 ใบเสร็จการขาย",
                    description=f"เลขที่ใบเสร็จ: **{bill_number}**",
                    color=0x2ecc71
                )
                
                embed.add_field(
                    name="👤 ผู้ขาย",
                    value=f"{interaction.user.mention}",
                    inline=True
                )
                
                embed.add_field(
                    name="📅 วันที่",
                    value=f"<t:{int(interaction.created_at.timestamp())}:F>",
                    inline=True
                )
                
                embed.add_field(
                    name="💰 ยอดรวม",
                    value=f"{total_amount:,.0f} บาท",
                    inline=True
                )
                
                # รายการสินค้า
                items_text = ""
                for item in self.items:
                    item_total = item['quantity'] * item['price']
                    items_text += f"• {item['name']} x {item['quantity']} {item['unit']} = {item_total:,.0f} บาท\n"
                
                embed.add_field(
                    name="📦 รายการสินค้า",
                    value=items_text,
                    inline=False
                )
                
                if self.notes:
                    embed.add_field(
                        name="📝 หมายเหตุ",
                        value=self.notes,
                        inline=False
                    )
                
                embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
                
                # ส่งใบเสร็จในช่องแชทปัจจุบัน
                await interaction.followup.send(embed=embed)
                
                # ส่งล็อกไปยังช่องประวัติบิล
                try:
                    bill_history_channel = interaction.guild.get_channel(1393184006748635156)
                    if bill_history_channel:
                        log_embed = discord.Embed(
                            title="📋 ล็อกการขาย",
                            description=f"มีการขายใหม่ในเซิร์ฟเวอร์",
                            color=0x3498db
                        )
                        log_embed.add_field(
                            name="🧾 เลขที่ใบเสร็จ",
                            value=bill_number,
                            inline=True
                        )
                        log_embed.add_field(
                            name="👤 ผู้ขาย",
                            value=f"{interaction.user} ({interaction.user.id})",
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
                            value=f"{interaction.channel.mention}",
                            inline=True
                        )
                        log_embed.add_field(
                            name="📅 วันที่",
                            value=f"<t:{int(interaction.created_at.timestamp())}:F>",
                            inline=True
                        )
                        if self.notes:
                            log_embed.add_field(
                                name="📝 หมายเหตุ",
                                value=self.notes,
                                inline=False
                            )
                        log_embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
                        
                        await bill_history_channel.send(embed=log_embed)
                except Exception as e:
                    print(f"❌ ไม่สามารถส่งล็อกไปยังช่องประวัติบิลได้: {e}")
                
                # ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย
                await remove_seller_permission(interaction, interaction.user)
                
                # ปิดการใช้งานปุ่ม
                for item in self.children:
                    item.disabled = True
                await interaction.edit_original_response(view=self)
                
                # ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย
                await remove_seller_permission(interaction, interaction.user)
                
            else:
                embed = discord.Embed(
                    title="❌ เกิดข้อผิดพลาด",
                    description="ไม่สามารถสร้างใบเสร็จได้",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"ไม่สามารถดำเนินการขายได้: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='ยกเลิก', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel_sale(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ ยกเลิกการขาย",
            description="การขายถูกยกเลิกแล้ว",
            color=0xe74c3c
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # ปิดการใช้งานปุ่ม
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(view=self)

class SalesChannelView(discord.ui.View):
    def __init__(self, stock_manager):
        super().__init__(timeout=None)
        self.stock_manager = stock_manager
    
    @discord.ui.button(label='🛒 สร้างการขาย', style=discord.ButtonStyle.success, emoji='🛒')
    async def create_sale(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SalesModal(self.stock_manager)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='📋 ดูประวัติการขาย', style=discord.ButtonStyle.secondary, emoji='📋')
    async def view_sales_history(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # ดึงประวัติการขายจากชีต Bills
            bills_sheet = self.stock_manager.spreadsheet.worksheet('Bills')
            records = bills_sheet.get_all_records()
            
            # กรองเฉพาะใบเสร็จของผู้ใช้นี้
            user_bills = {}
            for record in records:
                if record['ผู้ขาย'] == str(interaction.user):
                    bill_number = record['เลขที่ใบเสร็จ']
                    if bill_number not in user_bills:
                        user_bills[bill_number] = []
                    user_bills[bill_number].append(record)
            
            if not user_bills:
                embed = discord.Embed(
                    title="📋 ประวัติการขาย",
                    description="ไม่มีประวัติการขาย",
                    color=0xff6b6b
                )
            else:
                embed = discord.Embed(
                    title="📋 ประวัติการขาย",
                    description=f"ประวัติการขายของ {interaction.user.mention}",
                    color=0x3498db
                )
                
                # แสดงใบเสร็จล่าสุด 5 ใบ
                recent_bills = list(user_bills.items())[-5:]
                
                for bill_number, items in recent_bills:
                    total_amount = 0
                    items_text = ""
                    
                    for item in items:
                        if item['ราคารวม']:
                            total_amount += float(item['ราคารวม'])
                        items_text += f"• {item['ชื่อสินค้า']} x {item['จำนวน']} {item['หน่วย']}\n"
                    
                    embed.add_field(
                        name=f"🧾 {bill_number}",
                        value=f"{items_text}💰 ยอดรวม: {total_amount:,.0f} บาท\n📅 {items[0]['วันที่']}",
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"ไม่สามารถดึงประวัติการขายได้: {str(e)}",
                color=0xe74c3c
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label='📦 รายการสินค้า', style=discord.ButtonStyle.primary, emoji='📦', row=1)
    async def list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        # ใช้คำสั่ง !products เพื่อแสดงสินค้าเป็น card
        embed = discord.Embed(
            title="🏪 รายการสินค้าทั้งหมด",
            description="กำลังแสดงสินค้าทั้งหมดในรูปแบบ Product Card",
            color=0x4ecdc4
        )
        embed.add_field(
            name="💡 คำแนะนำ",
            value="• สินค้าจะถูกแสดงเป็น card แยกต่างหาก\n• แต่ละ card จะมีปุ่มสำหรับการซื้อ\n• คุณสามารถเลือกซื้อทันทีหรือเพิ่มเข้ารถเข็น",
            inline=False
        )
        await interaction.followup.send(embed=embed)
        
        # เรียกใช้ฟังก์ชัน products
        products = self.stock_manager.get_all_stock()
        
        if not products:
            no_products_embed = discord.Embed(
                title="📦 ไม่มีสินค้าในระบบ",
                description="ยังไม่มีสินค้าในระบบ กรุณาเพิ่มสินค้าก่อน",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=no_products_embed)
            return
        
        # แสดงสินค้าแต่ละรายการเป็น card พร้อมปุ่ม
        from ui.views.product_card_view import ProductCardView
        
        for product in products:
            quantity = int(product.get('จำนวน', 0))
            status_emoji = "⚠️" if quantity < 5 else "✅"
            price = float(product.get('ราคา', 0)) if product.get('ราคา') else 0
            
            embed = discord.Embed(
                title=f"{status_emoji} {product.get('ชื่อสินค้า', 'ไม่ระบุชื่อ')}",
                color=0xe74c3c if quantity < 5 else 0x2ecc71
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
            if quantity < 5:
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
            
            # ส่งเป็น card พร้อมปุ่ม (ใช้ ProductCardView ใหม่)
            await interaction.followup.send(embed=embed, view=ProductCardView(product, self.stock_manager))
            
            # รอเล็กน้อยเพื่อไม่ให้ spam
            await asyncio.sleep(0.5)
    
    @discord.ui.button(label='🛒 สร้างการขาย', style=discord.ButtonStyle.success, emoji='🛒', row=1)
    async def create_sales_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        try:
            # สร้างช่องแชทการขายส่วนตัว
            from bot import create_sales_channel
            
            sales_channel = await create_sales_channel(interaction.guild, interaction.user)
            
            if sales_channel:
                embed = discord.Embed(
                    title="✅ สร้างห้องการขายสำเร็จ",
                    description=f"ห้องการขายส่วนตัวของคุณ: {sales_channel.mention}",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="📋 คำแนะนำ",
                    value="""
                    • ห้องนี้เป็นส่วนตัวเฉพาะคุณเท่านั้น
                    • ใช้สำหรับสร้างการขายและจัดการใบเสร็จ
                    • ห้องจะถูกลบหลังจาก 24 ชั่วโมงหากไม่มีการใช้งาน
                    """,
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
