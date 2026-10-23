# -*- coding: utf-8 -*-
"""
Kho Nhân Vật Cố Định 3D (Google Flow / Veo 3D Character Vault & 7-Point DNA Engine).

Nghiên cứu từ chuẩn cộng đồng Google Flow (Labs Flow / Veo 2 / Veo 3.1):
Để giữ 100% nhân vật đồng nhất xuyên suốt nhiều cảnh (scenes) và nhiều tập (episodes) trên Google Flow,
mỗi prompt gửi vào Veo phải mở đầu bằng khối "7-Point Character DNA Block" cố định tuyệt đối:
  1. [Name & Stylized 3D Archetype] (Tránh từ khóa tuổi trẻ em nhạy cảm như '9-year-old boy' dễ bị bộ lọc Veo chặn)
  2. [Face Shape & Subsurface Skin Shader]
  3. [Eye Color, Size & Specular Catchlights]
  4. [Hair Clump Geometry & Color]
  5. [Primary Wardrobe & Exact Color Palette]
  6. [Signature Accessories & Footwear]
  7. [Strict Preservation Command] ("preserve the exact same 3D facial geometry, hair clumps, wardrobe colors, and body proportions in every scene")
"""

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_VAULT_PATH = ROOT_DIR / "temp" / "character_vault.json"

VEO_PRESERVATION_DIRECTIVE = (
    "preserve the exact same 3D facial geometry, sculpted hair clumps, eye color, "
    "signature wardrobe colors, and body proportions in every scene"
)

BUILTIN_3D_CHARACTER_PRESETS: List[Dict[str, str]] = [
    {
        "id": "leo_explorer",
        "name": "Leo — Nhà Thám Hiểm Rừng Cổ Đại (Pixar 3D)",
        "character_dna": (
            "Leo, a stylized Pixar 3D animated young explorer character, expressive round face with warm freckled cheeks "
            "and subsurface scattering skin shader, oversized glowing amber-brown 3D eyes with crisp catchlights, "
            "tousled chestnut-brown 3D hair sculpted in soft stylized clumps with a signature front curl, "
            "wearing an olive-green explorer jacket with brass buttons over a cream knitted sweater and dark denim trousers, "
            "carrying a brown leather crossbody satchel and a glowing vintage brass compass at his belt; "
            f"{VEO_PRESERVATION_DIRECTIVE}"
        ),
        "environment_dna": (
            "Enchanted ancient clockwork forest sanctuary in 3D CGI animation, volumetric golden-hour god rays filtering "
            "through mossy giant gears and bioluminescent turquoise ferns, rich PBR materials, Pixar RenderMan lighting"
        ),
    },
    {
        "id": "milo_rusty",
        "name": "Milo & Robot Rusty — Đôi Bạn Khoa Học (Pixar 3D)",
        "character_dna": (
            "Milo, a stylized Pixar 3D animated young inventor character with an expressive oval face, bright hazel 3D eyes, "
            "messy curly dark-brown 3D hair clumps with copper steampunk goggles resting on his forehead, wearing a vibrant "
            "teal hoodie with white drawstrings and cargo pants, accompanied by Rusty, a small vintage brushed-brass clockwork "
            "companion robot with glowing cyan optic lenses; "
            f"{VEO_PRESERVATION_DIRECTIVE}"
        ),
        "environment_dna": (
            "Cozy 3D CGI inventor workshop filled with glowing holographic blueprints, warm tungsten Edison bulbs, "
            "polished wooden workbenches, and floating brass gears, cinematic depth of field"
        ),
    },
    {
        "id": "linh_magic",
        "name": "Linh — Cô Gái Ánh Sáng Pha Lê (Pixar / DreamWorks 3D)",
        "character_dna": (
            "Linh, a stylized Pixar 3D animated young heroine character, delicate heart-shaped face with soft subsurface "
            "scattering skin, large sparkling emerald-green 3D eyes, long braided jet-black 3D hair adorned with a glowing "
            "crystal lotus hairpin, wearing a royal-blue velvet cloak with golden constellation embroidery over an ivory tunic "
            "and leather boots; "
            f"{VEO_PRESERVATION_DIRECTIVE}"
        ),
        "environment_dna": (
            "Floating celestial crystal valley in 3D CGI animation, bioluminescent lanterns drifting in twilight mist, "
            "ray-traced reflections on crystalline bridges, magical volumetric atmosphere"
        ),
    },
    {
        "id": "barnaby_bear",
        "name": "Bác Gấu Barnaby — Đầu Bếp Rừng Xanh (Zootopia / Pixar 3D)",
        "character_dna": (
            "Barnaby, a stylized Pixar and Zootopia 3D animated chubby cinnamon-brown bear chef character, detailed groom "
            "3D fur shader, warm friendly brown eyes behind small round brass spectacles on his snout, wearing a tall crisp "
            "white chef hat, a bright red plaid neckerchief, and a flour-dusted navy denim apron over a cream linen shirt; "
            f"{VEO_PRESERVATION_DIRECTIVE}"
        ),
        "environment_dna": (
            "Warm rustic 3D CGI woodland bakery inside a giant hollowed oak tree, golden sunlight streaming through stained-glass "
            "leaf windows,copper pots and glowing stone hearth oven"
        ),
    },
    {
        "id": "bibo_rabbit",
        "name": "Thám Tử Thỏ Bibo — Hành Trình Kỳ Bí (DreamWorks 3D)",
        "character_dna": (
            "Bibo, a stylized Pixar 3D animated snow-white rabbit detective character, long expressive ears with pink inner fur, "
            "big intelligent sapphire-blue 3D eyes, wearing a tailored olive tweed waistcoat, burgundy bow tie, and a miniature "
            "detective cape, holding a brass magnifying glass etched with glowing runes; "
            f"{VEO_PRESERVATION_DIRECTIVE}"
        ),
        "environment_dna": (
            "Miniature 3D CGI lantern-lit cobblestone village beneath giant glowing mushrooms, cinematic mist, "
            "warm amber streetlamps contrasting with cool moonlight, Unreal Engine 5 path-tracing look"
        ),
    },
]


def _slugify_id(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(name or "").replace("đ", "d").replace("Đ", "D"))
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_str.lower()).strip("_")
    return slug or f"char_{int(datetime.now().timestamp())}"


def get_builtin_character_presets() -> List[Dict[str, str]]:
    """Trả về danh sách các nhân vật 3D cố định dựng sẵn chuẩn 7-Point DNA."""
    return [dict(item) for item in BUILTIN_3D_CHARACTER_PRESETS]


def build_7_point_character_dna(raw_anchor: str) -> str:
    """
    Chuẩn hóa mọi mô tả nhân vật (ngắn hoặc dài) thành khối '7-Point Character DNA Block' chuẩn Google Flow / Veo:
    1. Chuyển đổi các từ khóa tuổi trẻ em nhạy cảm ('9-year-old boy', '10-year-old girl', 'child', 'kid')
       sang 'stylized Pixar 3D animated young explorer/adventurer character' để không bị bộ lọc an toàn Veo từ chối.
    2. Bổ sung kết cấu 3D Pixar (subsurface scattering skin shader, sculpted 3D hair clumps, expressive 3D eyes) nếu thiếu.
    3. Khóa cứng lệnh bảo toàn ngoại hình (`preserve the exact same 3D facial geometry...`) ở cuối khối DNA.
    """
    txt = str(raw_anchor or "").strip().strip(".;")
    if not txt:
        return BUILTIN_3D_CHARACTER_PRESETS[0]["character_dna"]

    # Làm sạch các từ khóa dễ kích hoạt nhầm bộ lọc trẻ em của Google Veo
    veo_safe_replacements = [
        (r"\b\d{1,2}-year-old\s+(?:boy|girl|child|kid)\b", "stylized Pixar 3D animated young adventurer character"),
        (r"\b(?:young\s+)?(?:little\s+)?(?:boy|girl|child|kid|children|kids)\b", "stylized Pixar 3D animated young character"),
    ]
    for pat, repl in veo_safe_replacements:
        txt = re.sub(pat, repl, txt, flags=re.IGNORECASE)

    low = txt.lower()
    additions: List[str] = []
    if "3d" not in low and "pixar" not in low:
        additions.append("stylized Pixar 3D CGI animated character")
    if "skin" not in low and "fur" not in low and "metal" not in low and "brass" not in low:
        additions.append("subsurface scattering skin shader and expressive 3D facial geometry")
    if "eye" not in low and "optic" not in low:
        additions.append("large expressive 3D eyes with crisp specular catchlights")

    if additions:
        txt = f"{txt}, {', '.join(additions)}"

    if "preserve the exact same" not in txt.lower():
        txt = f"{txt}; {VEO_PRESERVATION_DIRECTIVE}"

    return txt


def load_character_vault(vault_path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Đọc danh sách nhân vật cố định đã lưu trong Vault (kết hợp cả nhân vật người dùng lưu + nhân vật mẫu)."""
    target = Path(vault_path) if vault_path else DEFAULT_VAULT_PATH
    custom_list: List[Dict[str, str]] = []
    if target.exists():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                custom_list = [x for x in raw if isinstance(x, dict) and x.get("character_dna")]
            elif isinstance(raw, dict) and isinstance(raw.get("characters"), list):
                custom_list = [x for x in raw["characters"] if isinstance(x, dict) and x.get("character_dna")]
        except Exception:
            custom_list = []

    seen_ids = {c.get("id") for c in custom_list if c.get("id")}
    merged = list(custom_list)
    for preset in BUILTIN_3D_CHARACTER_PRESETS:
        if preset["id"] not in seen_ids:
            merged.append(dict(preset))
    return merged


def save_character_to_vault(
    name: str,
    character_dna: str,
    environment_dna: str = "",
    character_id: Optional[str] = None,
    vault_path: Optional[Path] = None,
) -> Dict[str, str]:
    """Lưu hoặc cập nhật một nhân vật cố định vào `character_vault.json` để tái sử dụng xuyên suốt các tập/video."""
    target = Path(vault_path) if vault_path else DEFAULT_VAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    cid = character_id or _slugify_id(name)
    locked_dna = build_7_point_character_dna(character_dna)
    entry = {
        "id": cid,
        "name": str(name or cid).strip(),
        "character_dna": locked_dna,
        "environment_dna": str(environment_dna or "").strip(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }

    existing_custom: List[Dict[str, str]] = []
    if target.exists():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing_custom = [x for x in raw if isinstance(x, dict)]
            elif isinstance(raw, dict) and isinstance(raw.get("characters"), list):
                existing_custom = [x for x in raw["characters"] if isinstance(x, dict)]
        except Exception:
            existing_custom = []

    updated = False
    for idx, item in enumerate(existing_custom):
        if item.get("id") == cid:
            existing_custom[idx] = entry
            updated = True
            break
    if not updated:
        existing_custom.insert(0, entry)

    target.write_text(json.dumps({"characters": existing_custom}, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry
