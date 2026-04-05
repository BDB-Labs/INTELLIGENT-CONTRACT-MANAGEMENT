from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ICON_SIZE = 1024


def render_icon(size: int = ICON_SIZE) -> Image.Image:
    image = Image.new("RGBA", (size, size), (15, 20, 22, 255))
    draw = ImageDraw.Draw(image)

    for inset, alpha in ((0, 255), (18, 255), (42, 220)):
        draw.rounded_rectangle(
            (inset, inset, size - inset, size - inset),
            radius=220 - inset // 4,
            fill=(18 + inset // 5, 23 + inset // 5, 28 + inset // 4, alpha),
        )

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (70, 90, 640, 680),
        fill=(184, 216, 150, 120),
    )
    glow_draw.ellipse(
        (350, 200, 940, 820),
        fill=(197, 106, 45, 120),
    )
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(48)))

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (138, 140, 888, 884),
        radius=186,
        outline=(255, 255, 255, 30),
        width=3,
        fill=(26, 33, 36, 172),
    )
    draw.rounded_rectangle(
        (250, 176, 770, 846),
        radius=34,
        outline=(255, 255, 255, 34),
        width=2,
        fill=(248, 244, 236, 225),
    )

    accent = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    accent_draw = ImageDraw.Draw(accent)
    accent_draw.rounded_rectangle(
        (304, 142, 848, 730),
        radius=34,
        outline=(255, 255, 255, 44),
        width=2,
        fill=(242, 236, 226, 155),
    )
    for top in (278, 338, 398, 458, 518):
        accent_draw.rounded_rectangle(
            (320, top, 690, top + 18),
            radius=9,
            fill=(90, 101, 97, 178),
        )
    accent_draw.rounded_rectangle(
        (320, 578, 580, 596),
        radius=9,
        fill=(197, 106, 45, 225),
    )
    accent_draw.rounded_rectangle(
        (320, 628, 540, 646),
        radius=9,
        fill=(184, 216, 150, 225),
    )
    accent = accent.filter(ImageFilter.GaussianBlur(1))
    image = Image.alpha_composite(image, accent)

    seal = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    seal_draw = ImageDraw.Draw(seal)
    seal_draw.ellipse(
        (596, 556, 860, 820),
        fill=(197, 106, 45, 236),
        outline=(255, 224, 202, 180),
        width=8,
    )
    seal_draw.line(
        (668, 692, 724, 746),
        fill=(255, 249, 240, 245),
        width=24,
        joint="curve",
    )
    seal_draw.line(
        (724, 746, 792, 640),
        fill=(255, 249, 240, 245),
        width=24,
        joint="curve",
    )
    image = Image.alpha_composite(image, seal.filter(ImageFilter.GaussianBlur(0.4)))

    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the ICM desktop app icon.")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    render_icon().save(output_path, format="PNG")


if __name__ == "__main__":
    main()
