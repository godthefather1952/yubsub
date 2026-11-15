"""Generate a YUBSUB yellow/black Mac icon during the native build."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess

out = Path("build/YUBSUB.iconset")
out.mkdir(parents=True, exist_ok=True)
size = 1024
im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(im)

# Solid matte black squircle with gold 2.wav accent.
d.rounded_rectangle((46, 46, 978, 978), radius=220,
                    fill="#111112", outline="#F5D343", width=36)
d.rounded_rectangle((95, 95, 929, 929), radius=180, outline="#292929", width=12)

font_paths = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Impact.ttf",
]
for candidate in font_paths:
    if Path(candidate).exists():
        font = ImageFont.truetype(candidate, 650)
        break
else:
    font = ImageFont.load_default()

text = "Y"
bounds = d.textbbox((0, 0), text, font=font, stroke_width=2)
width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
d.text(((1024-width)/2 - bounds[0], (1024-height)/2 - bounds[1] - 35),
       text, font=font, fill="#F5D343", stroke_width=2, stroke_fill="#F5D343")
d.rounded_rectangle((340, 812, 684, 835), radius=10, fill="#F5D343")

source = Path("build/YUBSUB.png")
source.parent.mkdir(exist_ok=True)
im.save(source)
for points in (16, 32, 128, 256, 512):
    subprocess.run(["sips", "-z", str(points), str(points), str(source),
                    "--out", str(out / f"icon_{points}x{points}.png")],
                   check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["sips", "-z", str(points*2), str(points*2), str(source),
                    "--out", str(out / f"icon_{points}x{points}@2x.png")],
                   check=True, stdout=subprocess.DEVNULL)
subprocess.run(["iconutil", "-c", "icns", str(out), "-o", "build/YUBSUB.icns"],
               check=True)
print("Created build/YUBSUB.icns")
