import sys, os, subprocess
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image, ImageDraw, ImageFont
w, h = 1200, 800
img = Image.new("RGB", (w, h), (255, 255, 255))
d = ImageDraw.Draw(img)
font_path = "C:\\Windows\\Fonts\\msyh.ttc"
try:
    font_title = ImageFont.truetype(font_path, 48)
    font_text = ImageFont.truetype(font_path, 32)
except Exception:
    font_title = ImageFont.load_default()
    font_text = ImageFont.load_default()
d.text((w/2, 60), "增值税电子普通发票", font=font_title, fill=(0, 0, 0), anchor="mm")
fields = [
    ("发票号码", "1234567890"),
    ("开票日期", "2024-11-30"),
    ("金额", "1,234.56"),
    ("税率", "13%"),
    ("税额", "160.49"),
    ("购买方名称", "某某科技有限公司"),
    ("销售方名称", "某某电子有限公司"),
]
x0, y0, dy = 120, 150, 70
for i, (k, v) in enumerate(fields):
    y = y0 + i * dy
    d.text((x0, y), f"{k}：{v}", font=font_text, fill=(0, 0, 0))
d.rectangle((800, 150, 1100, 220), outline=(0, 0, 0), width=2)
d.text((810, 160), "金额：1,234.56", font=font_text, fill=(0, 0, 0))
d.rectangle((800, 230, 1100, 300), outline=(0, 0, 0), width=2)
d.text((810, 240), "税率：13%", font=font_text, fill=(0, 0, 0))
d.rectangle((800, 310, 1100, 380), outline=(0, 0, 0), width=2)
d.text((810, 320), "税额：160.49", font=font_text, fill=(0, 0, 0))
d.text((x0, y0 + len(fields) * dy + 40), "备注：此图片用于模型字段抽取测试", font=font_text, fill=(80, 80, 80))
out = "invoice_test.png"
img.save(out)
print(os.path.abspath(out))