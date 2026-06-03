from __future__ import annotations

import re
import secrets
from decimal import Decimal, InvalidOperation

from django.http import HttpRequest

from rabotaem_backend.media_urls import public_url
from special_projects.models import SpecialProjectLetterImage

LANDNAME_PROJECT_SLUG = "landname"
RUSSIAN_ALPHABET = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"

_LETTER_KEYS = {
    "А": "a",
    "Б": "b",
    "В": "v",
    "Г": "g",
    "Д": "d",
    "Е": "e",
    "Ё": "yo",
    "Ж": "zh",
    "З": "z",
    "И": "i",
    "Й": "j",
    "К": "k",
    "Л": "l",
    "М": "m",
    "Н": "n",
    "О": "o",
    "П": "p",
    "Р": "r",
    "С": "s",
    "Т": "t",
    "У": "u",
    "Ф": "f",
    "Х": "h",
    "Ц": "c",
    "Ч": "ch",
    "Ш": "sh",
    "Щ": "sch",
    "Ъ": "hard",
    "Ы": "y",
    "Ь": "soft",
    "Э": "eh",
    "Ю": "yu",
    "Я": "ya",
}

_DEFAULT_LOCATIONS = {
    "А": ("Аральское море", "45.001000", "59.016000"),
    "Б": ("Байкал", "53.558700", "108.165000"),
    "В": ("Волга у Самары", "53.195900", "50.100800"),
    "Г": ("Гижигинская губа", "61.700000", "160.500000"),
    "Д": ("Дельта Лены", "72.000000", "128.500000"),
    "Е": ("Енисейские протоки", "69.430000", "86.180000"),
    "Ё": ("Ёкюльсаурлоун", "64.048000", "-16.180000"),
    "Ж": ("Жигулёвские горы", "53.400000", "49.580000"),
    "З": ("Зейское водохранилище", "53.950000", "127.300000"),
    "И": ("Итуруп", "45.000000", "147.850000"),
    "Й": ("Йоканьгская губа", "68.030000", "39.620000"),
    "К": ("Камчатка", "56.132000", "160.642000"),
    "Л": ("Ладожское озеро", "61.000000", "31.500000"),
    "М": ("Мангышлак", "43.650000", "51.200000"),
    "Н": ("Новая Земля", "73.300000", "54.700000"),
    "О": ("Онежское озеро", "61.650000", "35.550000"),
    "П": ("Патомское нагорье", "59.283000", "116.589000"),
    "Р": ("Рыбинское водохранилище", "58.450000", "38.250000"),
    "С": ("Сахалин", "50.800000", "143.100000"),
    "Т": ("Таймыр", "74.000000", "100.000000"),
    "У": ("Убсу-Нур", "50.300000", "92.700000"),
    "Ф": ("Финский залив", "60.000000", "28.600000"),
    "Х": ("Хибины", "67.650000", "33.700000"),
    "Ц": ("Цимлянское водохранилище", "47.800000", "42.900000"),
    "Ч": ("Чукотка", "66.000000", "170.000000"),
    "Ш": ("Шантарские острова", "54.800000", "137.600000"),
    "Щ": ("Щучья река", "67.450000", "68.600000"),
    "Ъ": ("Подъёмная складка Кавказа", "43.350000", "42.450000"),
    "Ы": ("Ыгыатта", "63.400000", "124.000000"),
    "Ь": ("Ольхон", "53.150000", "107.380000"),
    "Э": ("Эльтон", "49.130000", "46.730000"),
    "Ю": ("Югорский полуостров", "69.750000", "60.400000"),
    "Я": ("Ямал", "70.800000", "70.500000"),
}


def normalize_landname_text(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").upper().replace("Ё", "Ё")).strip()
    return "".join(ch for ch in normalized if ch in RUSSIAN_ALPHABET or ch == " ")[:32]


def normalize_letter(value: str) -> str:
    normalized = (value or "").strip().upper()
    if len(normalized) != 1 or normalized not in RUSSIAN_ALPHABET:
        raise ValueError("Укажите одну русскую букву.")
    return normalized


def parse_coordinates(value: str) -> tuple[Decimal | None, Decimal | None]:
    matches = re.findall(r"[-+]?\d{1,3}(?:[.,]\d+)?", value or "")
    for index in range(0, max(len(matches) - 1, 0)):
        try:
            lat = Decimal(matches[index].replace(",", "."))
            lng = Decimal(matches[index + 1].replace(",", "."))
        except InvalidOperation:
            continue
        if Decimal("-90") <= lat <= Decimal("90") and Decimal("-180") <= lng <= Decimal("180"):
            return lat.quantize(Decimal("0.000001")), lng.quantize(Decimal("0.000001"))
    return None, None


def tile_url_for_letter(request: HttpRequest, letter: str) -> str:
    key = _LETTER_KEYS[letter]
    return request.build_absolute_uri(f"/api/special-projects/landname/tiles/{key}.svg")


def map_url_for_coordinates(lat: Decimal | str, lng: Decimal | str) -> str:
    return f"https://www.google.com/maps?q={lat},{lng}"


def _serialize_default_letter(request: HttpRequest, letter: str) -> dict:
    location, lat, lng = _DEFAULT_LOCATIONS[letter]
    return {
        "id": f"default-{letter}",
        "letter": letter,
        "title": f"Буква {letter}",
        "location_name": location,
        "image_url": tile_url_for_letter(request, letter),
        "map_url": map_url_for_coordinates(lat, lng),
        "latitude": lat,
        "longitude": lng,
        "source_name": "Тамбур Landsat",
        "source_url": "",
        "is_default": True,
    }


def serialize_letter_image(request: HttpRequest, image: SpecialProjectLetterImage) -> dict:
    image_url = image.image_url or tile_url_for_letter(request, image.letter)
    return {
        "id": image.id,
        "letter": image.letter,
        "title": image.title,
        "location_name": image.location_name,
        "image_url": public_url(image_url, request=request),
        "map_url": image.map_url or (
            map_url_for_coordinates(image.latitude, image.longitude)
            if image.latitude is not None and image.longitude is not None
            else ""
        ),
        "latitude": str(image.latitude) if image.latitude is not None else "",
        "longitude": str(image.longitude) if image.longitude is not None else "",
        "source_name": image.source_name,
        "source_url": image.source_url,
        "is_default": False,
    }


def letter_pool(request: HttpRequest, letter: str) -> list[dict]:
    images = SpecialProjectLetterImage.objects.filter(
        project_slug=LANDNAME_PROJECT_SLUG,
        letter=letter,
        is_active=True,
    ).order_by("sort_order", "id")
    serialized = [serialize_letter_image(request, image) for image in images]
    if not serialized:
        serialized.append(_serialize_default_letter(request, letter))
    return serialized


def render_landname(request: HttpRequest, raw_text: str) -> dict:
    text = normalize_landname_text(raw_text)
    letters = []
    for position, ch in enumerate(text):
        if ch == " ":
            letters.append({"type": "space", "position": position})
            continue
        pool = letter_pool(request, ch)
        letters.append({"type": "letter", "position": position, "item": secrets.choice(pool)})
    return {
        "ok": True,
        "project": LANDNAME_PROJECT_SLUG,
        "text": text,
        "letters": letters,
        "share_query": text,
    }


def alphabet_payload(request: HttpRequest) -> dict:
    return {
        "ok": True,
        "project": LANDNAME_PROJECT_SLUG,
        "letters": [letter_pool(request, letter)[0] for letter in RUSSIAN_ALPHABET],
    }


def tile_svg(key: str) -> str | None:
    reverse = {value: letter for letter, value in _LETTER_KEYS.items()}
    letter = reverse.get(key)
    if not letter:
        return None
    index = RUSSIAN_ALPHABET.index(letter)
    hue = (index * 47) % 360
    hue2 = (hue + 58) % 360
    hue3 = (hue + 132) % 360
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 900" role="img" aria-label="Буква {letter}">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="hsl({hue}, 64%, 28%)"/>
      <stop offset=".52" stop-color="hsl({hue2}, 58%, 38%)"/>
      <stop offset="1" stop-color="hsl({hue3}, 54%, 24%)"/>
    </linearGradient>
    <filter id="grain">
      <feTurbulence type="fractalNoise" baseFrequency=".013 .041" numOctaves="5" seed="{index + 7}"/>
      <feColorMatrix type="saturate" values="1.55"/>
      <feBlend mode="overlay" in2="SourceGraphic"/>
    </filter>
  </defs>
  <rect width="900" height="900" fill="url(#g)"/>
  <g filter="url(#grain)" opacity=".78">
    <path d="M0 610 C190 480 310 710 510 560 C680 430 745 540 900 410 V900 H0Z" fill="hsl({hue2}, 70%, 45%)"/>
    <path d="M0 220 C210 300 290 115 460 210 C650 315 705 130 900 220 V0 H0Z" fill="hsl({hue3}, 60%, 36%)"/>
    <path d="M-40 760 C190 675 360 815 540 700 C690 604 765 655 940 572" fill="none" stroke="rgba(255,255,255,.28)" stroke-width="22"/>
    <path d="M90 90 L820 810" stroke="rgba(255,255,255,.16)" stroke-width="16"/>
  </g>
  <text x="450" y="555" text-anchor="middle" font-family="Arial, sans-serif" font-size="360" font-weight="800" fill="rgba(255,255,255,.86)">{letter}</text>
</svg>"""
