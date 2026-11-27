"""Create the same YUBSUB matte-black/yellow branding for ChromeOS Linux."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

output = Path("build/yubsub.png")
output.parent.mkdir(parents=True, exist_ok=True)
im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.rounded_rectangle((46, 46, 978, 978), radius=220,
                    fill="#111112", outline="#F5D343", width=36)
d.rounded_rectangle((95, 95, 929, 929), radius=180,
                    outline="#292929", width=12)
fonts = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
)
font = next((ImageFont.truetype(path, 650) for path in fonts if Path(path).is_file()),
            ImageFont.load_default())
bounds = d.textbbox((0, 0), "Y", font=font, stroke_width=2)
width, height = bounds[2]-bounds[0], bounds[3]-bounds[1]
d.text(((1024-width)/2-bounds[0], (1024-height)/2-bounds[1]-35),
       "Y", font=font, fill="#F5D343", stroke_width=2, stroke_fill="#F5D343")
d.rounded_rectangle((340, 812, 684, 835), radius=10, fill="#F5D343")
im.resize((256, 256), Image.Resampling.LANCZOS).save(output)
print(output)
