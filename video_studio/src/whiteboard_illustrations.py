"""Colored educational whiteboard artwork and a safe project-local image registry.

Adds reusable browser/clock/book/phone/plant/chart/idea illustrations alongside
the generated study-desk vignette. Original vector-style drawings use Pillow.
"""
from pathlib import Path
from PIL import Image, ImageDraw

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets" / "whiteboard"
ILLUSTRATIONS = {"study_desk", "browser", "clock", "book", "phone", "plant", "chart", "idea", "brain", "building"}
PALETTE = {"ink": "#41434b", "blue": "#42add1", "sky": "#d8eff5", "peach": "#ffd6ac",
           "orange": "#ffb56f", "green": "#79b799", "cream": "#fff4df", "purple": "#8d80bc"}


def custom_illustration_files():
    """Expose only importable drawings, never the photographic hand or its variants."""
    if not ASSET_DIR.is_dir():
        return []
    return sorted(p.name for p in ASSET_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in {".png", ".webp"}
                  and not p.stem.lower().startswith(("hand", "mask", "preview", "study_desk"))
                  and p.resolve().is_relative_to(ASSET_DIR.resolve()))[:200]


def local_image_path(filename: str) -> Path:
    target = (ASSET_DIR / filename).resolve()
    if not target.is_relative_to(ASSET_DIR.resolve()) or target.suffix.lower() not in {".png", ".webp"}:
        raise ValueError("Minh họa phải là PNG/WebP trong thư mục assets/whiteboard.")
    if not target.is_file():
        raise FileNotFoundError(f"Không tìm thấy minh họa: {target.name}")
    return target


def illustration_image(asset: str) -> Image.Image:
    if asset == "study_desk":
        with Image.open(local_image_path("study_desk_v1.png")) as im:
            return im.convert("RGBA")
    if asset not in ILLUSTRATIONS:
        raise ValueError(f"Chưa có minh họa '{asset}'.")
    im = Image.new("RGBA", (640, 480))
    d = ImageDraw.Draw(im)
    c = PALETTE
    ink, lw = c["ink"], 5

    def line(points, fill=ink, width=lw):
        d.line(points, fill=fill, width=width, joint="curve")

    def box(bounds, fill, radius=20):
        d.rounded_rectangle(bounds, radius=radius, fill=fill, outline=ink, width=lw)

    if asset == "browser":
        box((55, 65, 585, 410), "#ffffff")
        d.rounded_rectangle((58, 68, 582, 122), radius=18, fill=c["peach"])
        line([(57, 125), (583, 125)])
        for x in (87, 110, 133):
            d.ellipse((x - 5, 91, x + 5, 101), fill="#e28a69")
        box((91, 163, 300, 345), c["sky"], 12)
        d.polygon([(164, 204), (164, 305), (239, 255)], fill=c["orange"])
        for y, width in ((177, 204), (223, 165), (269, 189), (315, 130)):
            d.rounded_rectangle((333, y, 333 + width, y + 18), radius=8, fill=c["sky"])
    elif asset == "clock":
        d.ellipse((133, 55, 507, 429), fill=c["cream"], outline=ink, width=lw)
        d.ellipse((151, 73, 489, 411), fill="white", outline=c["orange"], width=10)
        for x, y in ((320, 98), (463, 242), (320, 384), (177, 242)):
            d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=ink)
        line([(320, 135), (320, 242), (403, 279)], width=9)
        d.ellipse((311, 233, 329, 251), fill=c["orange"])
    elif asset == "book":
        d.polygon([(71, 110), (289, 72), (320, 106), (353, 72), (570, 110), (570, 390), (343, 356), (320, 384), (297, 356), (71, 390)], fill=c["sky"], outline=ink, width=lw)
        d.polygon([(91, 95), (296, 62), (320, 92), (344, 62), (550, 95), (550, 366), (346, 335), (320, 365), (294, 335), (91, 366)], fill=c["cream"], outline=ink, width=lw)
        line([(320, 93), (320, 362)])
        for y in (146, 194, 242, 290):
            line([(122, y), (270, y - 22)], fill="#b4c3cb", width=8)
            line([(370, y - 22), (519, y)], fill="#b4c3cb", width=8)
        d.polygon([(390, 70), (421, 75), (421, 183), (405, 168), (390, 181)], fill=c["orange"], outline=ink, width=3)
    elif asset == "phone":
        box((207, 35, 433, 445), c["blue"], 35)
        box((222, 65, 418, 402), "white", 18)
        d.rounded_rectangle((285, 49, 355, 57), radius=4, fill=ink)
        d.ellipse((308, 413, 332, 437), fill=c["sky"], outline=ink, width=3)
        for y in (105, 180, 255):
            box((245, y, 391, y + 48), c["sky"] if y != 180 else c["peach"], 10)
    elif asset == "plant":
        line([(319, 343), (324, 105)], fill=ink, width=7)
        for bounds, color in [((160, 135, 320, 256), c["blue"]), ((321, 82, 460, 229), c["green"]), ((158, 247, 322, 338), c["green"]), ((320, 223, 480, 326), c["blue"])]:
            d.ellipse(bounds, fill=color, outline=ink, width=lw)
        d.polygon([(230, 325), (415, 325), (389, 441), (257, 441)], fill=c["cream"], outline=ink, width=lw)
        box((221, 318, 425, 350), c["peach"], 8)
    elif asset == "chart":
        for x, top, color in ((145, 285, c["sky"]), (255, 215, c["blue"]), (365, 145, c["orange"]), (475, 84, c["green"])):
            box((x, top, x + 65, 395), color, 8)
        line([(85, 72), (85, 397), (582, 397)])
        line([(150, 242), (278, 162), (399, 95), (531, 42)], fill=c["purple"], width=8)
        line([(502, 40), (534, 40), (527, 72)], fill=c["purple"], width=8)
    elif asset == "idea":
        d.ellipse((211, 64, 429, 282), fill=c["cream"], outline=ink, width=lw)
        d.polygon([(246, 240), (394, 240), (369, 345), (271, 345)], fill=c["orange"], outline=ink, width=lw)
        box((267, 333, 373, 390), c["sky"], 10)
        line([(286, 407), (354, 407)])
        for a, b in [((320, 13), (320, 40)), ((150, 93), (183, 111)), ((457, 110), (490, 90)), ((137, 213), (174, 213)), ((467, 213), (507, 213))]:
            line([a, b], fill=c["orange"], width=8)
    elif asset == "brain":
        for bounds in [(150, 141, 300, 298), (202, 72, 355, 240), (304, 76, 450, 247), (370, 137, 508, 302), (193, 217, 349, 373), (300, 211, 467, 374)]:
            d.ellipse(bounds, fill=c["peach"], outline=ink, width=lw)
        line([(326, 99), (312, 158), (337, 211), (314, 270), (330, 343)], fill=c["purple"], width=6)
    elif asset == "building":
        box((143, 132, 499, 419), c["cream"], 4)
        d.polygon([(105, 136), (321, 38), (537, 136)], fill=c["peach"], outline=ink, width=lw)
        box((283, 309, 360, 419), c["blue"], 4)
        for x in (183, 281, 379):
            for y in (172, 245):
                box((x, y, x + 64, y + 47), c["sky"], 4)
        line([(111, 424), (532, 424)], width=7)
    return im
