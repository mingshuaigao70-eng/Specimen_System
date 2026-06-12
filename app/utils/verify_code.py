from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import string
import io
import os

def generate_captcha():
    """
    生成一个随机验证码图片，返回 (验证码字符串, 图片字节流)
    """
    width, height = 120, 40
    # 随机生成4个字符（数字+大写字母）
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    # 创建白底图片
    image = Image.new('RGB', (width, height), (255, 255, 255))

    # 字体文件路径 — 多级回退确保跨平台兼容
    font_path = os.path.join(os.path.dirname(__file__), "arial.ttf")
    if not os.path.exists(font_path):
        # Windows 系统字体目录
        font_path = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', 'arial.ttf')
    if not os.path.exists(font_path):
        # Linux / macOS 回退
        for candidate in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                          '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
                          '/System/Library/Fonts/Supplemental/Arial.ttf'):
            if os.path.exists(candidate):
                font_path = candidate
                break
    if not os.path.exists(font_path):
        raise RuntimeError(
            '无法找到验证码字体文件。请安装 arial.ttf 或 DejaVuSans.ttf。'
            f'搜索路径: {font_path}'
        )

    font = ImageFont.truetype(font_path, 25)
    draw = ImageDraw.Draw(image)

    # 绘制验证码字符
    for i, c in enumerate(chars):
        draw.text((5 + i * 28, 5), c, font=font, fill=random_color())

    # 添加干扰线
    for _ in range(5):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line(((x1, y1), (x2, y2)), fill=random_color(), width=1)

    # 模糊处理
    image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)

    # 保存到字节流
    buf = io.BytesIO()
    image.save(buf, 'PNG')
    buf.seek(0)

    return chars, buf

def random_color():
    """生成随机颜色"""
    return (random.randint(0, 150), random.randint(0, 150), random.randint(0, 150))