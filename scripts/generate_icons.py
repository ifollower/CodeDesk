#!/usr/bin/env python3
"""Generate raster CodeDesk application icons from the canonical vector geometry."""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
MASTER_SIZE = 2048
SCALE = MASTER_SIZE / 512
RESAMPLE = Image.Resampling.LANCZOS


def px(value: float) -> int:
    return round(value * SCALE)


def gradient_square() -> Image.Image:
    gradient = Image.new("RGBA", (MASTER_SIZE, MASTER_SIZE))
    draw = ImageDraw.Draw(gradient)
    start = (23, 105, 224)
    end = (105, 70, 232)
    for y in range(MASTER_SIZE):
        ratio = y / (MASTER_SIZE - 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(end, start))
        draw.line((0, y, MASTER_SIZE, y), fill=(*color, 255))
    return gradient


def render_mark(opaque: bool = False) -> Image.Image:
    background = (245, 247, 252, 255) if opaque else (0, 0, 0, 0)
    image = Image.new("RGBA", (MASTER_SIZE, MASTER_SIZE), background)

    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (px(24), px(24), px(488), px(488)), radius=px(112), fill=255
    )
    image.alpha_composite(Image.composite(gradient_square(), Image.new("RGBA", image.size), mask))

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (px(82), px(104), px(430), px(354)),
        radius=px(38),
        fill=(16, 27, 58, 255),
        outline=(255, 255, 255, 255),
        width=px(18),
    )
    draw.line(
        [(px(151), px(184)), (px(203), px(224)), (px(151), px(264))],
        fill=(255, 255, 255, 255),
        width=px(24),
        joint="curve",
    )
    draw.line(
        [(px(231), px(273)), (px(329), px(273))],
        fill=(94, 234, 212, 255),
        width=px(24),
    )
    draw.line(
        [(px(256), px(363)), (px(256), px(406))],
        fill=(255, 255, 255, 255),
        width=px(18),
    )
    draw.line(
        [(px(184), px(414)), (px(328), px(414))],
        fill=(255, 255, 255, 255),
        width=px(18),
    )
    return image


def render_monochrome(size: int, color=(255, 255, 255, 255)) -> Image.Image:
    canvas = Image.new("RGBA", (MASTER_SIZE, MASTER_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (px(72), px(94), px(440), px(364)),
        radius=px(42),
        outline=color,
        width=px(28),
    )
    draw.line(
        [(px(145), px(178)), (px(205), px(224)), (px(145), px(270))],
        fill=color,
        width=px(30),
        joint="curve",
    )
    draw.line(
        [(px(235), px(278)), (px(340), px(278))], fill=color, width=px(30)
    )
    draw.line(
        [(px(256), px(374)), (px(256), px(416))], fill=color, width=px(24)
    )
    draw.line(
        [(px(174), px(426)), (px(338), px(426))], fill=color, width=px(24)
    )
    return canvas.resize((size, size), RESAMPLE)


def save_png(path: Path, size: int, opaque: bool = False) -> None:
    image = render_mark(opaque).resize((size, size), RESAMPLE)
    if opaque:
        image = image.convert("RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def save_android_foreground(path: Path, size: int) -> None:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mark_size = round(size * 0.7)
    mark = render_mark().resize((mark_size, mark_size), RESAMPLE)
    offset = (size - mark_size) // 2
    canvas.alpha_composite(mark, (offset, offset))
    canvas.save(path, optimize=True)


def generate() -> None:
    for name, size in {
        "32x32.png": 32,
        "64x64.png": 64,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": 1024,
        "mac-icon.png": 1024,
    }.items():
        save_png(ROOT / "res" / name, size, opaque=name == "mac-icon.png")

    save_png(ROOT / "flutter/assets/icon.png", 512)

    base_ico = render_mark().resize((256, 256), RESAMPLE)
    base_ico.save(
        ROOT / "res/icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    base_ico.save(ROOT / "res/tray-icon.ico", sizes=[(16, 16), (24, 24), (32, 32)])
    base_ico.save(
        ROOT / "flutter/windows/runner/resources/app_icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    render_monochrome(60, (0, 0, 0, 255)).save(ROOT / "res/mac-tray-dark-x2.png")
    render_monochrome(48, (0, 0, 0, 255)).save(ROOT / "res/mac-tray-light-x2.png")

    android_root = ROOT / "flutter/android/app/src/main/res"
    densities = {
        "mipmap-mdpi": (48, 108, 24),
        "mipmap-hdpi": (72, 162, 36),
        "mipmap-xhdpi": (96, 216, 48),
        "mipmap-xxhdpi": (144, 324, 72),
        "mipmap-xxxhdpi": (192, 432, 96),
    }
    for folder, (launcher, foreground, status) in densities.items():
        target = android_root / folder
        save_png(target / "ic_launcher.png", launcher)
        save_png(target / "ic_launcher_round.png", launcher)
        save_android_foreground(target / "ic_launcher_foreground.png", foreground)
        status_icon = render_monochrome(status)
        alpha = status_icon.getchannel("A")
        Image.merge("LA", (Image.new("L", alpha.size, 255), alpha)).save(
            target / "ic_stat_logo.png", optimize=True
        )

    ios_root = ROOT / "flutter/ios/Runner/Assets.xcassets/AppIcon.appiconset"
    for path in ios_root.glob("*.png"):
        with Image.open(path) as current:
            size = current.size[0]
        save_png(path, size, opaque=True)

    mac_icon = render_mark(opaque=True).resize((1024, 1024), RESAMPLE).convert("RGB")
    mac_icon.save(ROOT / "flutter/macos/Runner/AppIcon.icns", format="ICNS")

    server_icons = ROOT / "server/ui/icons"
    for name, size in {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "Square30x30Logo.png": 30,
        "Square44x44Logo.png": 44,
        "StoreLogo.png": 50,
        "Square71x71Logo.png": 71,
        "Square89x89Logo.png": 89,
        "Square107x107Logo.png": 107,
        "Square142x142Logo.png": 142,
        "Square150x150Logo.png": 150,
        "Square284x284Logo.png": 284,
        "Square310x310Logo.png": 310,
        "icon.png": 512,
    }.items():
        save_png(server_icons / name, size, opaque=True)
    base_ico.save(
        server_icons / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    mac_icon.save(server_icons / "icon.icns", format="ICNS")


if __name__ == "__main__":
    generate()
