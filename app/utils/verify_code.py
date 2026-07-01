from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random
import string
import io
import os


def generate_captcha():
    """
    鐢熸垚涓€涓殢鏈洪獙璇佺爜鍥剧墖锛岃繑鍥?(楠岃瘉鐮佸瓧绗︿覆, 鍥剧墖瀛楄妭娴?
    """
    width, height = 120, 40
    chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))

    image = Image.new('RGB', (width, height), (255, 255, 255))

    font_path = os.path.join(os.path.dirname(__file__), "arial.ttf")
    if not os.path.exists(font_path):
        font_path = os.path.join(os.environ.get('WINDIR', 'C:/Windows'), 'Fonts', 'arial.ttf')
    if not os.path.exists(font_path):
        for candidate in (
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/System/Library/Fonts/Supplemental/Arial.ttf',
        ):
            if os.path.exists(candidate):
                font_path = candidate
                break

    if os.path.exists(font_path):
        font = ImageFont.truetype(font_path, 25)
    else:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(image)

    for i, c in enumerate(chars):
        draw.text((5 + i * 28, 5), c, font=font, fill=random_color())

    for _ in range(5):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line(((x1, y1), (x2, y2)), fill=random_color(), width=1)

    image = image.filter(ImageFilter.EDGE_ENHANCE_MORE)

    buf = io.BytesIO()
    image.save(buf, 'PNG')
    buf.seek(0)

    return chars, buf


def random_color():
    """鐢熸垚闅忔満棰滆壊"""
    return (random.randint(0, 150), random.randint(0, 150), random.randint(0, 150))
