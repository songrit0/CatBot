import discord
from discord.ext import commands
import asyncio

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
                success = self.stock_manager.add_stock(product_name, quantity, unit, interaction.user)
                
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
                quantity = int(product['จำนวน'])
                emoji = "⚠️" if quantity < 5 else "✅"
                options.append(
                    discord.SelectOption(
                        label=f"{product['ชื่อสินค้า']} ({quantity} {product['หน่วย']})",
                        value=product['ชื่อสินค้า'],
                        emoji=emoji,
                        description=f"อัปเดต: {product['วันที่อัปเดตล่าสุด']}"
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
                quantity = int(product['จำนวน'])
                status_emoji = "⚠️" if quantity < 5 else "✅"
                
                embed = discord.Embed(
                    title=f"{status_emoji} {product['ชื่อสินค้า']}",
                    color=0xe74c3c if quantity < 5 else 0x2ecc71
                )
                
                embed.add_field(name="จำนวน", value=f"{quantity} {product['หน่วย']}", inline=True)
                embed.add_field(name="อัปเดตล่าสุด", value=product['วันที่อัปเดตล่าสุด'], inline=True)
                
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
        else:
            # For add/remove actions, show quantity input modal
            modal = StockModal(self.action_type, self.stock_manager)
            modal.product_name.default = selected_product
            await interaction.response.send_modal(modal)

class AdvancedStockView(discord.ui.View):
    def __init__(self, stock_manager):
        super().__init__(timeout=300)
        self.stock_manager = stock_manager
    
    @discord.ui.button(label='เพิ่มสินค้า', style=discord.ButtonStyle.success, emoji='➕')
    async def add_stock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StockModal("เพิ่ม", self.stock_manager)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='ลดสินค้า', style=discord.ButtonStyle.danger, emoji='➖')
    async def remove_stock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "เลือกสินค้าที่ต้องการลด:",
            view=ProductSelectView(self.stock_manager, "ลด"),
            ephemeral=True
        )
    
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
        
        products = self.stock_manager.get_all_stock()
        
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
            
            # Split products into pages if too many
            products_per_page = 10
            if len(products) > products_per_page:
                products = products[:products_per_page]
                embed.set_footer(text=f"แสดง {products_per_page} รายการแรก จากทั้งหมด {len(self.stock_manager.get_all_stock())} รายการ")
            
            for product in products:
                quantity = int(product['จำนวน'])
                status_emoji = "⚠️" if quantity < 5 else "✅"
                
                embed.add_field(
                    name=f"{status_emoji} {product['ชื่อสินค้า']}",
                    value=f"จำนวน: {quantity} {product['หน่วย']}\nอัปเดต: {product['วันที่อัปเดตล่าสุด']}",
                    inline=True
                )
        
        await interaction.followup.send(embed=embed, view=AdvancedStockView(self.stock_manager))
    
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
                    name=f"{record['การทำรายการ']} - {record['ชื่อสินค้า']}",
                    value=f"ผู้ใช้: {record['ชื่อผู้ใช้']}\nจำนวน: {record['จำนวน']}\nวันที่: {record['วันที่']}\nหมายเหตุ: {record['หมายเหตุ']}",
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
                    name=f"🔴 {product['ชื่อสินค้า']}",
                    value=f"จำนวน: {product['จำนวน']} {product['หน่วย']}\nอัปเดต: {product['วันที่อัปเดตล่าสุด']}",
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
