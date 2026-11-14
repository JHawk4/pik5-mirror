"""Small inline SVG icons: consoles, video hosts, Pikmin 2 egg stages.

All drawn here (no third-party artwork). Tooltips come from the title
attribute on the wrapping <span>/<a>.
"""

from html import escape
from urllib.parse import urlparse

# pik5 console codes. The controller is implied by the platform on pik5
# (it records one value per run), so the tooltip names both.
CONSOLES = {
    1: ("GC", "#6a5acd", "#fff",
        {"en": "GameCube · GameCube Controller", "ja": "ゲームキューブ・GCコントローラー"}),
    2: ("Wii", "#ffffff", "#333",
        {"en": "Wii · Wii Remote + Nunchuk", "ja": "Wii・Wiiリモコン＋ヌンチャク"}),
    3: ("WiiU", "#0096c8", "#fff",
        {"en": "Wii U · GamePad / Pro Controller", "ja": "Wii U・GamePad/Proコントローラー"}),
    4: ("NS", None, "#fff",
        {"en": "Nintendo Switch", "ja": "Nintendo Switch"}),
    5: ("NS2", None, "#fff",
        {"en": "Nintendo Switch 2", "ja": "Nintendo Switch 2"}),
    7: ("3DS", "#d1001f", "#fff",
        {"en": "Nintendo 3DS", "ja": "ニンテンドー3DS"}),
    12: ("VC", "#0096c8", "#fff",
         {"en": "Wii U Virtual Console", "ja": "Wii U バーチャルコンソール"}),
}


def _badge(text, bg, fg, w=30):
    if bg is None:  # Switch: blue/red Joy-Con split
        left, right = ("#00a9e0", "#ff4f4f")
        return (f'<svg class="ic" viewBox="0 0 {w} 14" width="{w}" height="14" aria-hidden="true">'
                f'<rect x="0" y="0" width="{w / 2}" height="14" rx="3" fill="{left}"/>'
                f'<rect x="{w / 2}" y="0" width="{w / 2}" height="14" rx="3" fill="{right}"/>'
                f'<rect x="{w / 2 - 3}" y="0" width="6" height="14" fill="#555"/>'
                f'<text x="{w / 2}" y="10.5" font-size="8.5" font-weight="700" text-anchor="middle" '
                f'fill="{fg}" font-family="Verdana,sans-serif">{text}</text></svg>')
    stroke = ' stroke="#999"' if bg == "#ffffff" else ""
    return (f'<svg class="ic" viewBox="0 0 {w} 14" width="{w}" height="14" aria-hidden="true">'
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="13" rx="3" fill="{bg}"{stroke}/>'
            f'<text x="{w / 2}" y="10.5" font-size="8.5" font-weight="700" text-anchor="middle" '
            f'fill="{fg}" font-family="Verdana,sans-serif">{text}</text></svg>')


def console_icon(code, lang):
    c = CONSOLES.get(code)
    if not c:
        return ""
    text, bg, fg, names = c
    return f'<span class="ico" title="{escape(names[lang])}">{_badge(text, bg, fg)}</span>'


_YT = ('<svg class="ic" viewBox="0 0 20 14" width="20" height="14" aria-hidden="true">'
       '<rect width="20" height="14" rx="4" fill="#e62117"/><path d="M8 4l5 3-5 3z" fill="#fff"/></svg>')
_TWITCH = ('<svg class="ic" viewBox="0 0 14 16" width="14" height="16" aria-hidden="true">'
           '<path d="M1 0h12v9l-4 4H6l-2 3H2v-3H0V3z" fill="#9146ff"/>'
           '<path d="M5 4h1.6v4H5zM8.5 4h1.6v4H8.5z" fill="#fff"/></svg>')
_NICO = ('<svg class="ic" viewBox="0 0 18 15" width="18" height="15" aria-hidden="true">'
         '<rect y="3" width="18" height="12" rx="3" fill="#252525"/>'
         '<path d="M5 0l4 3 4-3" stroke="#252525" stroke-width="1.6" fill="none"/>'
         '<path d="M7.5 6.5l4 2.5-4 2.5z" fill="#fff"/></svg>')
_X = ('<svg class="ic" viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">'
      '<rect width="14" height="14" rx="3" fill="#000"/>'
      '<path d="M3.5 3.5l7 7M10.5 3.5l-7 7" stroke="#fff" stroke-width="1.6"/></svg>')
_PLAY = ('<svg class="ic" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">'
         '<circle cx="8" cy="8" r="7.5" fill="#0077ff"/><path d="M6.3 4.8l5 3.2-5 3.2z" fill="#fff"/></svg>')


def video_icon(url):
    host = urlparse(url).netloc.lower()
    if "youtu" in host:
        return _YT, "YouTube"
    if "twitch" in host:
        return _TWITCH, "Twitch"
    if "nicovideo" in host or "nico.ms" in host:
        return _NICO, "niconico"
    if "twitter" in host or host.endswith("x.com"):
        return _X, "X"
    return _PLAY, host.replace("www.", "") or "video"


EGG = ('<span class="ico egg" title="Egg stage: eggs can hatch mitites / タマゴあり（タマゴムシが出現）">'
       '<svg class="ic" viewBox="0 0 12 15" width="11" height="14" aria-hidden="true">'
       '<path d="M6 .7C2.9.7.7 5.6.7 9.1a5.3 5.3 0 0 0 10.6 0C11.3 5.6 9.1.7 6 .7z" '
       'fill="#fff6d8" stroke="#b9952f" stroke-width="1.1"/>'
       '<circle cx="4.3" cy="7" r="1" fill="#e2b93b"/><circle cx="7.6" cy="10" r="1.1" fill="#e2b93b"/>'
       '</svg></span>')


CAMERA = ('<svg class="ic" viewBox="0 0 18 14" width="18" height="14" aria-hidden="true">'
          '<path d="M6 1h6l1.3 2H16a1.5 1.5 0 0 1 1.5 1.5v7A1.5 1.5 0 0 1 16 13H2a1.5 1.5 0 0 1-1.5-1.5v-7'
          'A1.5 1.5 0 0 1 2 3h2.7z" fill="#5a6b7d"/>'
          '<circle cx="9" cy="8" r="3.2" fill="#fff"/><circle cx="9" cy="8" r="1.8" fill="#5a6b7d"/></svg>')


# pik5 difficulty codes (labels from pik5: おだやか / ふつう / きょうぼう)
DIFFICULTY = {
    1: ("E", "#3aa25a", {"en": "Easy (おだやか)", "ja": "おだやか"}),
    2: ("N", "#8a8f98", {"en": "Normal (ふつう)", "ja": "ふつう"}),
    3: ("H", "#d8423a", {"en": "Hard (きょうぼう)", "ja": "きょうぼう"}),
}


def difficulty_icon(code, lang):
    d = DIFFICULTY.get(code)
    if not d:
        return ""
    letter, color, names = d
    return (f'<span class="ico" title="{escape(names[lang])}">'
            f'<svg class="ic" viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">'
            f'<rect x="0" y="0" width="14" height="14" rx="3" fill="{color}"/>'
            f'<text x="7" y="10.5" font-size="9.5" font-weight="700" text-anchor="middle" fill="#fff" '
            f'font-family="Verdana,sans-serif">{letter}</text></svg></span>')


# Site logo: a white five-petal flower on a stem with one leaf (generic flower art,
# drawn here; evokes the flower a Pikmin grows without using Nintendo's characters).
SPROUT = ('<svg viewBox="0 0 24 34" width="26" height="37" aria-hidden="true">'
          '<path d="M12 33 C12 26 11.6 20 12 13" stroke="#3c8531" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
          '<path d="M12 25 C8.5 25.5 5 23.5 3.6 20.6 C7.4 19.6 10.6 21.5 12 25 Z" fill="#5fb447" stroke="#3c8531" stroke-width="1"/>'
          '<ellipse cx="12.00" cy="4.40" rx="3.1" ry="4.3" transform="rotate(0 12.00 4.40)" fill="#ffffff" stroke="#c9c2d6" stroke-width="0.8"/><ellipse cx="16.37" cy="7.58" rx="3.1" ry="4.3" transform="rotate(72 16.37 7.58)" fill="#ffffff" stroke="#c9c2d6" stroke-width="0.8"/><ellipse cx="14.70" cy="12.72" rx="3.1" ry="4.3" transform="rotate(144 14.70 12.72)" fill="#ffffff" stroke="#c9c2d6" stroke-width="0.8"/><ellipse cx="9.30" cy="12.72" rx="3.1" ry="4.3" transform="rotate(216 9.30 12.72)" fill="#ffffff" stroke="#c9c2d6" stroke-width="0.8"/><ellipse cx="7.63" cy="7.58" rx="3.1" ry="4.3" transform="rotate(288 7.63 7.58)" fill="#ffffff" stroke="#c9c2d6" stroke-width="0.8"/>'
          '<circle cx="12" cy="9" r="3.1" fill="#f2c230" stroke="#d39a12" stroke-width="0.9"/></svg>')
