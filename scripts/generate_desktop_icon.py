from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ICON_SIZE = 1024


def render_icon(size: int = ICON_SIZE) -> Image.Image:
    image = Image.new("RGBA", (size, size), (3, 10, 20, 255))
    draw = ImageDraw.Draw(image)

    for inset, alpha in ((0, 255), (18, 255), (42, 220)):
        draw.rounded_rectangle(
            (inset, inset, size - inset, size - inset),
            radius=220 - inset // 4,
            fill=(4 + inset // 4, 16 + inset // 3, 30 + inset // 2, alpha),
        )

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (110, 120, 700, 710),
        fill=(109, 255, 214, 115),
    )
    glow_draw.ellipse(
        (360, 220, 930, 790),
        fill=(0, 124, 240, 120),
    )
    image = Image.alpha_composite(image, glow.filter(ImageFilter.GaussianBlur(48)))

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (140, 160, 884, 864),
        radius=180,
        outline=(255, 255, 255, 30),
        width=3,
        fill=(8, 24, 39, 165),
    )
    draw.rounded_rectangle(
        (208, 228, 816, 796),
        radius=146,
        outline=(255, 255, 255, 28),
        width=2,
        fill=(5, 15, 26, 168),
    )

    accent = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    accent_draw = ImageDraw.Draw(accent)
    accent_draw.rounded_rectangle(
        (250, 270, 774, 754),
        radius=128,
        outline=(120, 255, 214, 210),
        width=28,
    )
    accent_draw.rounded_rectangle(
        (324, 344, 700, 680),
        radius=94,
        outline=(0, 124, 240, 215),
        width=22,
    )
    accent_draw.line(
        (352, 512, 678, 512),
        fill=(255, 255, 255, 230),
        width=26,
        joint="curve",
    )
    accent_draw.line(
        (512, 350, 512, 674),
        fill=(255, 255, 255, 230),
        width=26,
        joint="curve",
    )
    accent = accent.filter(ImageFilter.GaussianBlur(1))
    image = Image.alpha_composite(image, accent)

    slash = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    slash_draw = ImageDraw.Draw(slash)
    slash_draw.rounded_rectangle(
        (452, 258, 572, 766),
        radius=60,
        fill=(255, 152, 101, 235),
    )
    slash = slash.rotate(34, center=(512, 512), resample=Image.Resampling.BICUBIC)
    image = Image.alpha_composite(image, slash.filter(ImageFilter.GaussianBlur(0.5)))

    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the ESE desktop app icon.")
    parser.add_argument("--output", required=True, help="Output PNG path")
    args = parser.parse_args()

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    render_icon().save(output_path, format="PNG")


if __name__ == "__main__":
    main()
