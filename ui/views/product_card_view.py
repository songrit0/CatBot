import discord
from discord.ui import View, Button, Modal, TextInput, Select
from datetime import datetime
import json
import os
import asyncio

# ID ของช่องบันทึกใบเสร็จ
BILL_HISTORY_CHANNEL_ID = 1393184006748635156

# ฟังก์ชันช่วยสำหรับการลบห้องหลังแสดงใบเสร็จการขาย
async def remove_seller_permission(interaction, seller_user):
    """ลบห้องหลังแสดงใบเสร็จการขาย"""
    try:
        # ตรวจสอบว่าเป็นห้องที่สามารถลบได้
        if isinstance(interaction.channel, discord.TextChannel):
            # ตรวจสอบว่าเป็นห้องการขายหรือไม่
            if interaction.channel.name.startswith("การขาย-"):
                # ส่งข้อความแจ้งเตือนก่อนลบห้อง
                try:
                    embed = discord.Embed(
                        title="�️ ห้องจะถูกลบใน 10 วินาที",
                        description=f"ห้องการขายของ {seller_user.mention} จะถูกลบหลังจากการขายเสร็จสิ้น",
                        color=0xff6b6b
                    )
                    embed.add_field(
                        name="📝 หมายเหตุ",
                        value="นี่เป็นการดำเนินการอัตโนมัติหลังจากแสดงใบเสร็จการขาย",
                        inline=False
                    )
                    await interaction.followup.send(embed=embed, ephemeral=False)
                    
                    # รอ 10 วินาที แล้วลบห้อง
                    await asyncio.sleep(10)
                    await interaction.channel.delete(reason="ลบห้องการขายหลังจากการขายเสร็จสิ้น")
                    print(f"✅ ลบห้องการขาย {interaction.channel.name} ({interaction.channel.id}) เรียบร้อยแล้ว")
                    
                except Exception as e:
                    print(f"❌ ไม่สามารถลบห้องได้: {e}")
            else:
                print(f"❌ ห้องนี้ไม่ใช่ห้องการขาย: {interaction.channel.name}")
            
        else:
            print(f"❌ ไม่สามารถลบห้องได้: ห้องนี้ไม่ใช่ TextChannel")
            
    except discord.Forbidden:
        print(f"❌ ไม่มีสิทธิ์ในการลบห้อง {interaction.channel.name}")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการลบห้อง: {e}")

class ProductCardView(discord.ui.View):
    def __init__(self, product, stock_manager, timeout=300):
        super().__init__(timeout=timeout)
        self.product = product
        self.stock_manager = stock_manager
        
    @discord.ui.button(label="🛒 เพิ่มเข้ารถเข็น", style=discord.ButtonStyle.primary, emoji="🛒")
    async def add_to_cart(self, interaction: discord.Interaction, button: discord.ui.Button):
        """เพิ่มสินค้าเข้ารถเข็น"""
        await interaction.response.send_modal(AddToCartModal(self.product, self.stock_manager))
    
    @discord.ui.button(label="💳 ชำระเงิน", style=discord.ButtonStyle.success, emoji="💳")
    async def quick_buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ซื้อสินค้าทันที"""
        await interaction.response.send_modal(QuickBuyModal(self.product, self.stock_manager))
    
    @discord.ui.button(label="🛒 ดูรถเข็น", style=discord.ButtonStyle.secondary, emoji="🛒")
    async def view_cart(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ดูรถเข็นสินค้า"""
        await interaction.response.defer()
        
        # Import ที่นี่เพื่อหลีกเลี่ยง circular import
        from bot import user_carts, Cart
        
        user_id = str(interaction.user.id)
        if user_id not in user_carts or not user_carts[user_id].get_items():
            embed = discord.Embed(
                title="🛒 รถเข็นของคุณ",
                description="รถเข็นว่างเปล่า",
                color=0xff6b6b
            )
            embed.add_field(
                name="💡 คำแนะนำ",
                value="ใช้ปุ่ม \"🛒 เพิ่มเข้ารถเข็น\" เพื่อเพิ่มสินค้า",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        cart = user_carts[user_id]
        items = cart.get_items()
        total = cart.get_total()
        
        embed = discord.Embed(
            title="🛒 รถเข็นของคุณ",
            description=f"มีสินค้า {len(items)} รายการ",
            color=0x3498db
        )
        
        cart_text = ""
        for i, item in enumerate(items, 1):
            item_total = item['price'] * item['quantity']
            cart_text += f"{i}. **{item['product_name']}** x{item['quantity']} {item['unit']} = {item_total:,.0f} บาท\n"
        
        embed.add_field(
            name="📦 รายการสินค้า",
            value=cart_text,
            inline=False
        )
        
        embed.add_field(
            name="💰 ยอดรวมทั้งหมด",
            value=f"{total:,.0f} บาท",
            inline=False
        )
        
        # สร้าง View สำหรับการจัดการรถเข็น
        cart_view = CartManageView(user_id)
        
        await interaction.followup.send(embed=embed, view=cart_view, ephemeral=True)
    
    @discord.ui.button(label="🗑️ เคลียร์รถเข็น", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def clear_cart(self, interaction: discord.Interaction, button: discord.ui.Button):
        """เคลียร์รถเข็นสินค้า"""
        await interaction.response.defer()
        
        # Import ที่นี่เพื่อหลีกเลี่ยง circular import
        from bot import user_carts, Cart
        
        user_id = str(interaction.user.id)
        if user_id not in user_carts or not user_carts[user_id].get_items():
            embed = discord.Embed(
                title="🛒 รถเข็นของคุณ",
                description="รถเข็นว่างเปล่าอยู่แล้ว",
                color=0xff6b6b
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # แสดงยืนยันก่อนเคลียร์
        embed = discord.Embed(
            title="⚠️ ยืนยันการเคลียร์รถเข็น",
            description="คุณต้องการเคลียร์รถเข็นทั้งหมดหรือไม่?",
            color=0xf39c12
        )
        
        view = ClearCartConfirmView(user_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class AddToCartModal(discord.ui.Modal):
    def __init__(self, product, stock_manager):
        super().__init__(title=f"เพิ่ม {product.get('ชื่อสินค้า', 'สินค้า')} เข้ารถเข็น")
        self.product = product
        self.stock_manager = stock_manager
        
        # ตั้งค่าจำนวนเริ่มต้น
        max_stock = int(product.get('จำนวน', 0))
        
        self.quantity = discord.ui.TextInput(
            label="จำนวนที่ต้องการ",
            placeholder=f"ใส่จำนวน (มีสต็อก {max_stock} {product.get('หน่วย', 'ชิ้น')})",
            min_length=1,
            max_length=10,
            default="1"
        )
        self.add_item(self.quantity)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0:
                embed = discord.Embed(
                    title="❌ จำนวนไม่ถูกต้อง",
                    description="จำนวนต้องมากกว่า 0",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Import ที่นี่เพื่อหลีกเลี่ยง circular import
            from bot import add_item_to_cart_helper
            
            user_id = str(interaction.user.id)
            product_name = self.product.get('ชื่อสินค้า', '')
            
            result = await add_item_to_cart_helper(user_id, product_name, quantity)
            
            if result['success']:
                embed = discord.Embed(
                    title="✅ เพิ่มลงรถเข็นสำเร็จ",
                    description=f"เพิ่ม **{product_name}** x{quantity} เข้ารถเข็นแล้ว!",
                    color=0x2ecc71
                )
                
                embed.add_field(
                    name="💰 ยอดรวมในรถเข็น",
                    value=f"{result['total_price']:,.0f} บาท",
                    inline=True
                )
                
                embed.add_field(
                    name="📦 รายการทั้งหมด",
                    value=f"{len(result['cart_items'])} รายการ",
                    inline=True
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ เกิดข้อผิดพลาด",
                    description=result['message'],
                    color=0xe74c3c
                )
                
                if result['error_type'] == 'insufficient_stock':
                    embed.add_field(
                        name="📉 สต็อกไม่เพียงพอ",
                        value=f"มีสต็อกเพียง {result['available_quantity']} {result['unit']}",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except ValueError:
            embed = discord.Embed(
                title="❌ จำนวนไม่ถูกต้อง",
                description="กรุณาใส่ตัวเลขที่ถูกต้อง",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"เกิดข้อผิดพลาด: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class QuickBuyModal(discord.ui.Modal):
    def __init__(self, product, stock_manager):
        super().__init__(title=f"ซื้อ {product.get('ชื่อสินค้า', 'สินค้า')} ทันที")
        self.product = product
        self.stock_manager = stock_manager
        
        # ตั้งค่าจำนวนเริ่มต้น
        max_stock = int(product.get('จำนวน', 0))
        
        self.quantity = discord.ui.TextInput(
            label="จำนวนที่ต้องการซื้อ",
            placeholder=f"ใส่จำนวน (มีสต็อก {max_stock} {product.get('หน่วย', 'ชิ้น')})",
            min_length=1,
            max_length=10,
            default="1"
        )
        self.add_item(self.quantity)
        
        self.notes = discord.ui.TextInput(
            label="หมายเหตุ (ถ้ามี)",
            placeholder="ใส่หมายเหตุสำหรับการซื้อ (ไม่จำเป็น)",
            required=False,
            max_length=200
        )
        self.add_item(self.notes)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            quantity = int(self.quantity.value)
            if quantity <= 0:
                embed = discord.Embed(
                    title="❌ จำนวนไม่ถูกต้อง",
                    description="จำนวนต้องมากกว่า 0",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # ตรวจสอบสต็อก
            available_quantity = int(self.product.get('จำนวน', 0))
            if available_quantity < quantity:
                embed = discord.Embed(
                    title="❌ สต็อกไม่เพียงพอ",
                    description=f"สินค้า **{self.product.get('ชื่อสินค้า', '')}** เหลือเพียง {available_quantity} {self.product.get('หน่วย', 'ชิ้น')}",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # สร้างรายการสินค้าสำหรับใบเสร็จ
            bill_items = [{
                'name': self.product.get('ชื่อสินค้า', ''),
                'quantity': quantity,
                'price': float(self.product.get('ราคา', 0)),
                'unit': self.product.get('หน่วย', 'ชิ้น')
            }]
            
            # สร้างใบเสร็จ
            bill_number, total_amount = self.stock_manager.create_bill(
                interaction.user,
                bill_items,
                self.notes.value or "ซื้อทันที (Quick Buy)"
            )
            
            if bill_number:
                # สร้าง embed ใบเสร็จ
                embed = discord.Embed(
                    title="🧾 ใบเสร็จการซื้อ",
                    description=f"เลขที่ใบเสร็จ: **{bill_number}**",
                    color=0x2ecc71
                )
                
                embed.add_field(
                    name="👤 ผู้ซื้อ",
                    value=f"{interaction.user.mention}",
                    inline=True
                )
                
                embed.add_field(
                    name="📦 สินค้า",
                    value=f"{self.product.get('ชื่อสินค้า', '')} x {quantity} {self.product.get('หน่วย', 'ชิ้น')}",
                    inline=True
                )
                
                embed.add_field(
                    name="💰 ยอดรวม",
                    value=f"{total_amount:,.0f} บาท",
                    inline=True
                )
                
                if self.notes.value:
                    embed.add_field(
                        name="📝 หมายเหตุ",
                        value=self.notes.value,
                        inline=False
                    )
                
                embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # ส่งล็อกไปยังช่องบันทึกใบเสร็จ
                try:
                    # ส่งไปยังช่องบันทึกใบเสร็จ (ID: 1393184006748635156)
                    bill_channel = interaction.client.get_channel(BILL_HISTORY_CHANNEL_ID)
                    if bill_channel:
                        log_embed = discord.Embed(
                            title="🛒 การซื้อทันที (Quick Buy)",
                            description=f"มีการซื้อสินค้าทันทีผ่านระบบ Product Card",
                            color=0x3498db
                        )
                        log_embed.add_field(
                            name="🧾 เลขที่ใบเสร็จ",
                            value=bill_number,
                            inline=True
                        )
                        log_embed.add_field(
                            name="👤 ผู้ซื้อ",
                            value=f"{interaction.user} ({interaction.user.id})",
                            inline=True
                        )
                        log_embed.add_field(
                            name="📦 สินค้า",
                            value=f"{self.product.get('ชื่อสินค้า', '')} x {quantity} {self.product.get('หน่วย', 'ชิ้น')}",
                            inline=True
                        )
                        log_embed.add_field(
                            name="💰 ยอดรวม",
                            value=f"{total_amount:,.0f} บาท",
                            inline=True
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
                        
                        if self.notes.value:
                            log_embed.add_field(
                                name="📝 หมายเหตุ",
                                value=self.notes.value,
                                inline=False
                            )
                        
                        log_embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
                        
                        await bill_channel.send(embed=log_embed)
                        print(f"✅ ส่งล็อกใบเสร็จ {bill_number} ไปยังช่องบันทึกแล้ว")
                    else:
                        print(f"❌ ไม่พบช่องบันทึกใบเสร็จ (ID: 1393184006748635156)")
                    
                except Exception as e:
                    print(f"❌ ไม่สามารถส่งล็อกไปยังช่องบันทึกใบเสร็จได้: {e}")
                
                # ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย (Quick Buy)
                await remove_seller_permission(interaction, interaction.user)
                
            else:
                embed = discord.Embed(
                    title="❌ เกิดข้อผิดพลาด",
                    description="ไม่สามารถสร้างใบเสร็จได้",
                    color=0xe74c3c
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except ValueError:
            embed = discord.Embed(
                title="❌ จำนวนไม่ถูกต้อง",
                description="กรุณาใส่ตัวเลขที่ถูกต้อง",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                title="❌ เกิดข้อผิดพลาด",
                description=f"เกิดข้อผิดพลาด: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class CartManageView(discord.ui.View):
    def __init__(self, user_id, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    @discord.ui.button(label="💳 ชำระเงิน", style=discord.ButtonStyle.success, emoji="💳")
    async def checkout(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ชำระเงิน"""
        await interaction.response.defer()
        
        # Import ที่นี่เพื่อหลีกเลี่ยง circular import
        from bot import user_carts, stock_manager, BILL_HISTORY_CHANNEL_ID
        import datetime
        
        if self.user_id not in user_carts or not user_carts[self.user_id].get_items():
            embed = discord.Embed(
                title="❌ รถเข็นว่างเปล่า",
                description="ไม่มีสินค้าในรถเข็นของคุณ",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        cart = user_carts[self.user_id]
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
                await interaction.followup.send(embed=embed, ephemeral=True)
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
                interaction.user,
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
                    value=f"{interaction.user.mention}",
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
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # เคลียร์รถเข็น
                cart.clear()
                
                # ส่งล็อกไปยังช่องบันทึกใบเสร็จ
                try:
                    # ส่งไปยังช่องบันทึกใบเสร็จ
                    bill_channel = interaction.client.get_channel(BILL_HISTORY_CHANNEL_ID)
                    if bill_channel:
                        log_embed = discord.Embed(
                            title="🛒 การขายผ่านรถเข็น (Shopping Cart)",
                            description=f"มีการชำระเงินผ่านระบบรถเข็น",
                            color=0x3498db
                        )
                        log_embed.add_field(
                            name="🧾 เลขที่ใบเสร็จ",
                            value=bill_number,
                            inline=True
                        )
                        log_embed.add_field(
                            name="👤 ผู้ซื้อ",
                            value=f"{interaction.user} ({interaction.user.id})",
                            inline=True
                        )
                        log_embed.add_field(
                            name="💰 ยอดรวม",
                            value=f"{total_amount:,.0f} บาท",
                            inline=True
                        )
                        log_embed.add_field(
                            name="📦 จำนวนรายการ",
                            value=f"{len(items)} รายการ",
                            inline=True
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
                        log_embed.add_field(
                            name="📦 รายการสินค้า",
                            value=items_text,
                            inline=False
                        )
                        log_embed.set_footer(text=f"ใบเสร็จเลขที่: {bill_number}")
                        
                        await bill_channel.send(embed=log_embed)
                        print(f"✅ ส่งล็อกใบเสร็จ {bill_number} ไปยังช่องบันทึกแล้ว")
                    else:
                        print(f"❌ ไม่พบช่องบันทึกใบเสร็จ (ID: {BILL_HISTORY_CHANNEL_ID})")
                    
                except Exception as e:
                    print(f"❌ ไม่สามารถส่งล็อกไปยังช่องบันทึกใบเสร็จได้: {e}")
                
                # ลบสิทธิ์ผู้ขายออกจากห้องหลังแสดงใบเสร็จการขาย (Cart Checkout)
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
                description=f"เกิดข้อผิดพลาด: {str(e)}",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class ClearCartConfirmView(discord.ui.View):
    def __init__(self, user_id, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
    
    @discord.ui.button(label="✅ ยืนยันเคลียร์", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ยืนยันเคลียร์รถเข็น"""
        await interaction.response.defer()
        
        # Import ที่นี่เพื่อหลีกเลี่ยง circular import
        from bot import user_carts
        
        if self.user_id in user_carts:
            user_carts[self.user_id].clear()
            embed = discord.Embed(
                title="✅ เคลียร์รถเข็นสำเร็จ",
                description="รถเข็นของคุณถูกเคลียร์แล้ว",
                color=0x2ecc71
            )
        else:
            embed = discord.Embed(
                title="🛒 รถเข็นว่างเปล่า",
                description="รถเข็นของคุณว่างเปล่าอยู่แล้ว",
                color=0xff6b6b
            )
        
        # ปิดการใช้งานปุ่ม
        for item in self.children:
            item.disabled = True
        
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="❌ ยกเลิก", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """ยกเลิกการเคลียร์รถเข็น"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="❌ ยกเลิกการเคลียร์รถเข็น",
            description="รถเข็นของคุณยังคงเหมือนเดิม",
            color=0x95a5a6
        )
        
        # ปิดการใช้งานปุ่ม
        for item in self.children:
            item.disabled = True
        
        await interaction.edit_original_response(embed=embed, view=self)
