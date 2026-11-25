"""生成桌面快捷方式图标与网页 favicon。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZE = 512
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

# 斜向渐变底色
background = Image.new("RGB", (SIZE, SIZE), (14, 124, 134))
pixels = background.load()
for y in range(SIZE):
    for x in range(SIZE):
        t = (x / SIZE * 0.35 + y / SIZE * 0.65)
        r = int(11 + (14 - 11) * t)
        g = int(42 + (124 - 42) * t)
        b = int(62 + (134 - 62) * t)
        pixels[x, y] = (r, g, b)

mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=112, fill=255)
image.paste(background, (0, 0), mask)

draw = ImageDraw.Draw(image)
# 内描边
draw.rounded_rectangle((26, 26, SIZE - 26, SIZE - 26), radius=102, outline=(255, 255, 255, 42), width=3)

font_path = Path("C:/Windows/Fonts/msyhbd.ttc")
if not font_path.exists():
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
font = ImageFont.truetype(str(font_path), 210)
text = "债"
center = (SIZE // 2, 240)
# 阴影 + 白字
draw.text((center[0] + 4, center[1] + 7), text, font=font, fill=(4, 39, 58, 110), anchor="mm")
draw.text(center, text, font=font, fill=(255, 255, 255, 255), anchor="mm")

# 底部一条细金线，呼应“净额结清”
draw.rounded_rectangle((196, 396, 316, 408), radius=6, fill=(255, 209, 102, 220))

assets = ROOT / "assets"
assets.mkdir(exist_ok=True)
icon_path = assets / "app.ico"
image.save(
    icon_path,
    format="ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
image.resize((256, 256), Image.LANCZOS).save(assets / "app.png")
image.resize((64, 64), Image.LANCZOS).save(ROOT / "web" / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print(icon_path)
