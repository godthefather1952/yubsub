"""Create the Windows version of the existing matte-black/yellow YUBSUB icon."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path("build")
out.mkdir(exist_ok=True)
image = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((46, 46, 978, 978), radius=220,
                       fill="#111112", outline="#F5D343", width=36)
draw.rounded_rectangle((95, 95, 929, 929), radius=180,
                       outline="#292929", width=12)
try:
    font = ImageFont.truetype("arialbd.ttf", 650)
except OSError:
    font = ImageFont.load_default()
bounds = draw.textbbox((0, 0), "Y", font=font, stroke_width=2)
width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
draw.text(((1024-width)/2-bounds[0], (1024-height)/2-bounds[1]-35),
          "Y", font=font, fill="#F5D343",
          stroke_width=2, stroke_fill="#F5D343")
draw.rounded_rectangle((340, 812, 684, 835), radius=10, fill="#F5D343")
image.save(out/"YUBSUB.ico", sizes=[(16,16),(24,24),(32,32),(48,48),
                                   (64,64),(128,128),(256,256)])
