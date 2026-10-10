"""Đổi số tiền người Việt hay viết ("250k", "1tr2", "1,5 triệu", "2 triệu rưỡi"…) thành số nguyên đồng VND.

Làm bằng CODE (không để model tự nhân/chia): sai số tiền là rủi ro lớn nhất của ghi thu chi. Cách viết nhập nhằng
("1,5" không đơn vị, "1.500k") → ToolError để model hỏi lại người dùng, KHÔNG đoán.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from family_agent.harness.deps import ToolError
from family_agent.harness.vocab import fold

MAX_AMOUNT: Final = 10**12  # khớp $defs.amount của hợp đồng

_UNITS: Final = {
    "ty": 10**9, "ti": 10**9,
    "trieu": 10**6, "tr": 10**6, "cu": 10**6,
    "lit": 10**5,
    "nghin": 10**3, "ngan": 10**3, "k": 10**3,
}
# Thứ tự alternation: chuỗi dài trước ("trieu" trước "tr").
_TOKEN: Final = re.compile(r"(?P<num>[0-9]+(?:[.,][0-9]+)*)|(?P<word>trieu|nghin|ngan|ruoi|nua|lit|tr|cu|ty|ti|k)")
_CURRENCY: Final = re.compile(r"(?:vnd|dong|d)$")
_GROUPED: Final = re.compile(r"^[0-9]{1,3}(?:([.,])[0-9]{3})(?:\1[0-9]{3})*$")
_SPACED_GROUPS: Final = re.compile(r"^[0-9]{1,3}(?: [0-9]{3})+$")  # "1 000 000"
MIN_BARE: Final = 1000  # số trần nhỏ hơn thường là "nghìn" nói tắt ("đi chợ hết 150") → hỏi lại
_HINT: Final = 'Hãy hỏi lại người dùng số tiền chính xác (ví dụ "250k", "1tr2", "1.250.000").'


def _bad(text: str) -> ToolError:
    return ToolError(f'Không hiểu số tiền "{text}". {_HINT}')


def _plain(num: str, text: str) -> Decimal:
    """Số không đơn vị: chỉ chữ số, hoặc phân cách nghìn đều đặn ("1.250.000"). "1,5" → nhập nhằng."""
    if num.isdigit():
        return Decimal(num)
    if _GROUPED.match(num):
        return Decimal(num.replace(".", "").replace(",", ""))
    raise _bad(text)


def _with_unit(num: str, text: str) -> Decimal:
    """Số đứng trước đơn vị: "," hoặc "." là dấu thập phân ("1,5 triệu"). Đúng 3 chữ số sau dấu ("1.500k") thì
    không biết là thập phân hay phân cách nghìn → nhập nhằng."""
    if num.isdigit():
        return Decimal(num)
    parts = re.split(r"[.,]", num)
    if len(parts) != 2 or len(parts[1]) == 3:
        raise _bad(text)
    return Decimal(f"{parts[0]}.{parts[1]}")


def _tokens(s: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    pos = 0
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m:
            raise _bad(text)
        out.append(("num", m["num"]) if m["num"] is not None else ("word", m["word"]))
        pos = m.end()
    return out


def _total(toks: list[tuple[str, str]], text: str) -> Decimal:
    if [k for k, _ in toks] == ["num"]:
        bare = _plain(toks[0][1], text)
        if bare < MIN_BARE:
            raise ToolError(f'Số tiền "{text}" không có đơn vị — là {text} nghìn hay {text} đồng? {_HINT}')
        return bare
    if len(toks) == 2 and toks[0] == ("word", "nua") and toks[1][1] in _UNITS:  # "nửa triệu"
        return Decimal(_UNITS[toks[1][1]]) / 2

    total = Decimal(0)
    last_unit: int | None = None
    i = 0
    while i < len(toks):
        kind, val = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if kind == "num" and nxt is not None and nxt[0] == "word" and nxt[1] in _UNITS:
            unit = _UNITS[nxt[1]]
            if last_unit is not None and unit >= last_unit:  # "200k 1tr", "1tr2tr"
                raise _bad(text)
            total += _with_unit(val, text) * unit
            last_unit = unit
            i += 2
        elif kind == "num" and nxt is None and last_unit is not None and val.isdigit() and len(val) in (1, 3):
            # Đuôi sau đơn vị: 1 chữ số = phần mười ("1tr2" = 1,2 triệu; "2k5" = 2,5 nghìn); 3 chữ số = theo vị trí
            # ("1tr250", "1tr050"). 2 chữ số ("1tr50": 1,5 triệu hay 1.050.000?) hoặc dài hơn → nhập nhằng.
            total += Decimal(f"0.{val}") * last_unit
            i += 1
        elif (kind, val) == ("word", "ruoi") and nxt is None and last_unit is not None:
            total += Decimal(last_unit) / 2  # "2 triệu rưỡi"
            i += 1
        else:
            raise _bad(text)
    return total


def parse_vnd(value: str | int | float) -> int:
    """Số tiền → số nguyên đồng trong 1 … 10^12. Không hiểu / nhập nhằng / lẻ đồng → ToolError."""
    if isinstance(value, bool):
        raise ToolError(f"Số tiền phải là số. {_HINT}")
    if isinstance(value, float):
        if not value.is_integer():
            raise ToolError(f"Số tiền phải là số nguyên đồng (nhận {value}). {_HINT}")
        value = int(value)
    if isinstance(value, int):
        amount = Decimal(value)
        text = str(value)
        if amount < MIN_BARE:
            raise ToolError(f'Số tiền {value} đồng nghe nhỏ bất thường — là {value} nghìn? {_HINT}')
    elif isinstance(value, str):
        text = value.strip()
        folded = " ".join(fold(text).split())
        if re.search(r"[0-9] [0-9]", folded) and not _SPACED_GROUPS.match(_CURRENCY.sub("", folded).strip()):
            raise _bad(text)  # "10 20", "100 200k": hai số riêng, không được dính thành một
        s = re.sub(r"\s+", "", folded)
        s = _CURRENCY.sub("", s)
        if not s:
            raise _bad(text)
        amount = _total(_tokens(s, text), text)
    else:
        raise ToolError(f"Số tiền phải là số hoặc chuỗi. {_HINT}")
    if amount != amount.to_integral_value():
        raise ToolError(f'Số tiền "{text}" ra số lẻ đồng. {_HINT}')
    if not 1 <= amount <= MAX_AMOUNT:
        raise ToolError(f'Số tiền "{text}" phải từ 1 đ đến 1.000 tỷ đ.')
    return int(amount)


# ---------------------------------------------------------------------------
# Số tiền phải đến từ lời người dùng (eval phase 9: model tự thêm đơn vị cho "đi chợ hết 150", "ghi chi 1,5")
# ---------------------------------------------------------------------------

# Số trong lời người dùng (đã fold): số + đơn vị (+ "đ") + đuôi ("1tr2", "2 trieu ruoi", "50kd") hoặc số trần
# ("150", "1,5", "1.250.000", "2 000 000"). Đuôi chỉ được có SAU đơn vị: "tháng 9 150" là hai số riêng.
_SPOKEN: Final = re.compile(
    r"(?<![\w.,/:])(?P<num>[0-9]{1,3}(?: [0-9]{3})* 000(?![0-9.,])|[0-9]+(?:[.,][0-9]+)*)"
    r"(?:(?P<unit>\s*(?:trieu|nghin|ngan|lit|tr|cu|ty|ti|k))(?:\s*(?:vnd|dong|d))?(?![a-z])"
    r"(?P<tail>\s*[0-9]+(?![0-9.,]))?(?:\s*ruoi)?)?"
)
# Số trần đứng cạnh từ chỉ ngày/giờ/số lượng không phải số tiền ("tháng 9", "ngày 2", "7h", "2 lần").
_NOT_MONEY_BEFORE: Final = re.compile(r"\b(?:thang|ngay|thu|luc|tuan|nam|so|lop)$")
_NOT_MONEY_AFTER: Final = re.compile(
    r"(?:[/:]|\s*(?:h|g|gio|phut|tuoi|ngay|thang|nam|lan|nguoi|cai|qua|kg|hop|chai|bat|ly|coc)\b)"
)
# Đơn vị đứng một mình (trả lời câu hỏi lại: "nghìn") — không gồm "k" ("không"), "tr", "ngan" ("ngăn"), "ty" ("tí").
_LONE_UNIT: Final = re.compile(r"\b(trieu|nghin)\b")
# Có từ chỉ số tiền viết bằng chữ ("hai trăm k", "trăm rưỡi") → không coi là model bịa số.
_SPELLED: Final = re.compile(r"\b(?:tram|chuc|muoi|nghin|ngan|trieu|ty|ti|cu|lit|k|ruoi|nua)\b")
_UNITLESS: Final = re.compile(r"^[0-9]+(?:[.,][0-9]{1,2})?$")
_SCALES: Final = (10**3, 10**6)


def _vnd(n: Decimal) -> str:
    return f"{int(n):,}đ".replace(",", ".")


def _unit_options(b: Decimal) -> list[str]:
    return [_vnd(b * u) for u in _SCALES if b * u == (b * u).to_integral_value() and b * u >= MIN_BARE]


def _ask_unit(text: str, b: Decimal) -> tuple[str, list[str]]:
    return f'Số tiền "{text}" chưa có đơn vị — ý bạn là bao nhiêu?', _unit_options(b)


@dataclass
class _Said:
    """Số tiền trong MỘT tin nhắn người dùng."""

    stated: set[int] = field(default_factory=set)  # số tiền đã rõ ("250k", "1.250.000")
    bare: dict[str, Decimal] = field(default_factory=dict)  # số trần nhập nhằng {chữ gốc: giá trị} ("150", "1,5")
    units: set[int] = field(default_factory=set)  # đơn vị nói riêng ("nghìn")
    spelled: bool = False


def _scan(raw: str) -> _Said:
    out = _Said()
    text = fold(raw)
    for m in _SPOKEN.finditer(text):
        num = m["num"]
        if m["unit"]:
            for candidate in (m.group(0), num + m["unit"]):  # đuôi có thể là số khác ("50k 3 lần")
                try:
                    out.stated.add(parse_vnd(candidate))
                    break
                except ToolError:
                    continue
            continue
        if _NOT_MONEY_BEFORE.search(text[: m.start()].rstrip()) or _NOT_MONEY_AFTER.match(text, m.end()):
            continue
        plain = num.replace(" ", "")
        if plain.isdigit() or _GROUPED.match(plain):
            n = Decimal(plain.replace(".", "").replace(",", ""))
            if n >= MIN_BARE:
                out.stated.add(int(n))
            else:
                out.bare[num] = n
        elif _UNITLESS.match(num):
            out.bare[num] = Decimal(num.replace(",", "."))
    for m in _LONE_UNIT.finditer(text):
        if not text[: m.start()].rstrip()[-1:].isdigit():
            out.units.add(_UNITS[m[1]])
    out.spelled = bool(_SPELLED.search(text))
    return out


def amount_question(value: int, texts: list[str]) -> tuple[str, list[str]] | None:
    """Câu hỏi lại khi số tiền model đề xuất KHÔNG đến từ lời người dùng; None = cho qua.

    `texts`: tin nhắn người dùng theo thứ tự (history → tin hiện tại).
    - Người dùng nói số không đơn vị ("150", "1,5") mà model tự gắn nghìn/triệu → hỏi lại kèm lựa chọn, trừ khi
      chính tin đó hoặc tin SAU nói rõ ("150 nghìn", chỉ "nghìn", bấm "150.000đ"); tin cũ hơn không tính.
    - Người dùng không nói số/đơn vị/số viết bằng chữ nào (ngày, tháng, giờ không tính) mà model vẫn có số tiền →
      hỏi số tiền.
    Không có lời người dùng (gọi tool trực tiếp) → không kiểm. Số model tự tính ("2 bát phở 60k") cho qua.
    """
    if not texts:
        return None
    said = [_scan(t) for t in texts]
    for i, s in enumerate(said):
        for text, b in s.bare.items():
            if not any(b * u == value for u in _SCALES):
                continue
            later = said[i:]
            if any(value in x.stated or any(b * u == value for u in x.units) for x in later):
                continue
            return _ask_unit(text, b)
    if any(x.stated or x.bare or x.units or x.spelled for x in said):
        return None
    return "Số tiền là bao nhiêu?", []


def unitless_question(raw: object) -> tuple[str, list[str]] | None:
    """Model truyền nguyên văn số không đơn vị ("150", "1,5") → câu hỏi lại kèm lựa chọn; số hợp lệ/khác → None."""
    if isinstance(raw, bool) or not isinstance(raw, int | float | str):
        return None
    text = str(raw).strip()
    try:
        parse_vnd(raw)
        return None
    except ToolError:
        pass
    if not _UNITLESS.match(text):
        return None
    b = Decimal(text.replace(",", "."))
    return _ask_unit(text, b) if b > 0 else None
