"""ClarificationSink — câu hỏi lại do TOOL viết (không phải do model), spec §2.4, §6.3.

`/run` trả đúng chữ trong sink cho người dùng; model không có cơ hội diễn đạt lại.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_ENTRIES = 5
MAX_OPTIONS = 10
MAX_QUESTION = 500
MAX_OPTION = 100


class ClarificationError(ValueError):
    """Câu hỏi không dùng được (rỗng) — model thấy để hỏi lại cho đúng."""


@dataclass(frozen=True)
class Clarification:
    question: str
    options: tuple[str, ...] = ()


@dataclass
class ClarificationSink:
    entries: list[Clarification] = field(default_factory=list)

    def ask(self, question: str, options: list[str] | tuple[str, ...] = ()) -> bool:
        """Ghi một câu hỏi. True = mới; False = trùng hệt hoặc sink đã đầy (chỉ câu đầu được hỏi nên bỏ phần thừa)."""
        q = " ".join(question.split())[:MAX_QUESTION]
        if not q:
            raise ClarificationError("Câu hỏi không được để trống.")
        opts: list[str] = []
        for raw in options:
            o = " ".join(raw.split())[:MAX_OPTION]
            if o and o not in opts:
                opts.append(o)
        entry = Clarification(q, tuple(opts[:MAX_OPTIONS]))
        if entry in self.entries or len(self.entries) >= MAX_ENTRIES:
            return False
        self.entries.append(entry)
        return True

    def first(self) -> Clarification | None:
        return self.entries[0] if self.entries else None

    def is_empty(self) -> bool:
        return not self.entries
