"""
Генерация QR-кода с красивой карточкой
"""
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


def generate_key_qr(access_url: str, server_name: str = "", flag: str = "🌍") -> BytesIO:
    """
    Генерирует QR-код ключа с красивой карточкой
    
    :param access_url: ss:// ссылка
    :param server_name: Название сервера
    :param flag: Эмодзи флага
    :return: BytesIO с PNG изображением
    """
    # Создаём QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=2,
    )
    qr.add_data(access_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_size = qr_img.size[0]
    
    # Размеры карточки
    card_width = qr_size + 40
    card_height = qr_size + 100
    
    # Создаём карточку с градиентом
    card = Image.new('RGB', (card_width, card_height), '#1a1a2e')
    draw = ImageDraw.Draw(card)
    
    # Заголовок
    title = f"{flag} {server_name}" if server_name else "🔐 VPN Key"
    try:
        font = ImageFont.truetype("arial.ttf", 20)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
        small_font = font
    
    # Текст заголовка
    draw.text((20, 15), title, fill='#ffffff', font=font)
    
    # Вставляем QR
    card.paste(qr_img, (20, 50))
    
    # Подпись
    draw.text((20, qr_size + 60), "Сканируй в Outline", fill='#888888', font=small_font)
    
    # Сохраняем в буфер
    buffer = BytesIO()
    card.save(buffer, format='PNG')
    buffer.seek(0)
    
    return buffer
