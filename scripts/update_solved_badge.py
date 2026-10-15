"""정상적인 solved.ac 카드만 저장하고, 실패하면 기존 이미지를 유지한다."""

from pathlib import Path
import re
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


HANDLE = "dlwnstndlwld"
URL = f"https://mazassumnida.wtf/api/v2/generate_badge?boj={HANDLE}"
TARGET = Path(__file__).resolve().parents[1] / "assets" / "solved-ac.svg"
MAX_BYTES = 256 * 1024
SVG = "{http://www.w3.org/2000/svg}"


def validate_card(content: bytes) -> bytes:
    if not content or len(content) > MAX_BYTES:
        raise ValueError("카드 크기가 올바르지 않습니다.")
    text = content.decode("utf-8")
    if "<!ENTITY" in text.upper():
        raise ValueError("외부 엔티티가 포함되어 있습니다.")
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"@import\s+url\([^)]*\)\s*;", "", text)
    root = ET.fromstring(text)
    if root.tag != SVG + "svg" or (root.get("width"), root.get("height")) != ("350", "170"):
        raise ValueError("정상적인 카드 SVG가 아닙니다.")
    labels = {
        node.get("class"): "".join(node.itertext()).strip()
        for node in root.iter(SVG + "text")
    }
    if labels.get("boj-handle") != HANDLE:
        raise ValueError("카드의 계정이 일치하지 않습니다.")
    for field in ("rate value", "solved value", "class value"):
        if not labels.get(field, "").isdecimal():
            raise ValueError(f"카드에서 {field} 값을 찾지 못했습니다.")
    for node in root.iter():
        if node.tag in {SVG + "script", SVG + "foreignObject"}:
            raise ValueError("카드에 실행 가능한 내용이 포함되어 있습니다.")
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1].lower().startswith("on"):
                raise ValueError("카드에 이벤트 속성이 포함되어 있습니다.")
            if key.rsplit("}", 1)[-1] == "href" and not value.startswith(("#", "data:image/png;base64,")):
                raise ValueError("카드에 외부 이미지가 포함되어 있습니다.")
    if re.search(r"url\(\s*['\"]?(?!#)[^)]*\)|@import", text, re.IGNORECASE):
        raise ValueError("카드에 외부 스타일이 포함되어 있습니다.")
    return (text.strip() + "\n").encode("utf-8")


def fetch_card() -> bytes:
    request = Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (compatible; easygap-profile-card/1.0)",
        "Accept": "image/svg+xml",
    })
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                if response.headers.get_content_type() != "image/svg+xml":
                    raise ValueError("서버가 SVG 대신 다른 내용을 반환했습니다.")
                return response.read(MAX_BYTES + 1)
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(5)


def update_card(target: Path = TARGET) -> bool:
    content = validate_card(fetch_card())
    if target.exists() and target.read_bytes() == content:
        return False
    temporary = target.with_suffix(".svg.tmp")
    try:
        temporary.write_bytes(content)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main() -> int:
    try:
        changed = update_card()
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"카드를 갱신하지 못해 기존 이미지를 유지합니다: {error}", file=sys.stderr)
        return 1
    print("카드를 갱신했습니다." if changed else "변경된 내용이 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
