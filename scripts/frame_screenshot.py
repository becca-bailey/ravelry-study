"""Frame a screenshot in a consistent 'browser card' treatment for the essay.

Usage: python3 frame_screenshot.py <input.png> <output.png> "<label text>"

Output: fixed 1456px-wide canvas (Substack's 2x retina width) with a
TRANSPARENT background, white browser-chrome card with traffic lights +
address pill, rounded corners, soft alpha shadow. Works on light and dark
reader themes. Same treatment for every screenshot = consistency.
"""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CANVAS_W = 1456
CHROME = (255, 255, 255)       # browser bar
PILL = (240, 239, 236)         # address pill
PILL_TEXT = (110, 108, 104)
BORDER = (224, 222, 218)
RADIUS = 24
PAD = 56                       # mat padding around the card
BAR_H = 88
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]

def rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, *im.size], radius, fill=255)
    out = Image.new("RGBA", im.size)
    out.paste(im, (0, 0), mask)
    return out

def main(inp, outp, label):
    shot = Image.open(inp).convert("RGB")
    card_w = CANVAS_W - 2 * PAD
    scale = card_w / shot.width
    shot = shot.resize((card_w, round(shot.height * scale)), Image.LANCZOS)

    card_h = BAR_H + shot.height
    card = Image.new("RGB", (card_w, card_h), CHROME)
    card.paste(shot, (0, BAR_H))
    d = ImageDraw.Draw(card)
    # traffic lights
    for i, c in enumerate(DOTS):
        x = 36 + i * 40
        d.ellipse([x, BAR_H // 2 - 11, x + 22, BAR_H // 2 + 11], fill=c)
    # address pill with label
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    tw = d.textlength(label, font=font)
    pw = tw + 64
    px0 = (card_w - pw) / 2
    d.rounded_rectangle([px0, 20, px0 + pw, BAR_H - 20], (BAR_H - 40) / 2, fill=PILL)
    d.text((px0 + 32, BAR_H / 2), label, font=font, fill=PILL_TEXT, anchor="lm")
    d.line([(0, BAR_H - 1), (card_w, BAR_H - 1)], fill=BORDER, width=1)

    card = rounded(card.convert("RGBA"), RADIUS)
    # thin border on top of the rounding
    ImageDraw.Draw(card).rounded_rectangle([0, 0, card_w - 1, card_h - 1], RADIUS, outline=BORDER, width=2)

    canvas = Image.new("RGBA", (CANVAS_W, card_h + 2 * PAD), (0, 0, 0, 0))
    # soft alpha shadow: neutral black so it darkens whatever theme is behind it
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([PAD, PAD + 10, PAD + card_w, PAD + card_h + 10], RADIUS, fill=(0, 0, 0, 80))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(sh)
    canvas.alpha_composite(card, (PAD, PAD))
    canvas.save(outp)
    print("wrote", outp, canvas.size)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
