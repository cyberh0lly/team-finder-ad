from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


def generate_avatar(name):
    image = Image.new(
        'RGB',
        (200, 200),
        color=(100, 120, 140),
    )

    draw = ImageDraw.Draw(image)
    letter = name[0].upper()
    font = ImageFont.load_default(size=100)

    bbox = draw.textbbox((0, 0), letter, font=font)
    x = (200 - (bbox[2] - bbox[0])) / 2
    y = (200 - (bbox[3] - bbox[1])) / 2 - bbox[1]

    draw.text(
        (x, y),
        letter,
        fill='white',
        font=font,
    )

    buffer = BytesIO()
    image.save(buffer, format='PNG')

    return ContentFile(
        buffer.getvalue(),
        name='avatar.png',
    )