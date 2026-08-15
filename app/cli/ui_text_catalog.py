# ruff: noqa: E501

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "ui-texts-catalog.html"

FEEDBACK_PATTERN = re.compile(
    r"(?:обратн\w*\s+связ|(?:^|[\s(«\"'])ОС(?:$|[\s).,!?:;»\"'])|feedback)",
    re.IGNORECASE,
)
CYRILLIC_PATTERN = re.compile(r"[А-Яа-яЁё]")
LETTER_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё]")
URL_PATTERN = re.compile(r"^(?:https?://|mailto:|tel:)", re.IGNORECASE)
TECHNICAL_LITERAL_PATTERN = re.compile(
    r"^(?:[#.][\w-]+|/?(?:api|miniapp|static)/|[\w.-]+\.(?:py|js|css|html|json)|"
    r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)$",
    re.IGNORECASE,
)

SYSTEM_CALL_PREFIXES = (
    "logger.",
    "logging.",
    "print",
    "parser.",
    "argparse.",
)
EXCLUDED_PYTHON_CONTEXTS = {
    "format_backend_error",
    "parse_args",
    "simulate_command",
    "simulate_callback",
    "main",
}
VISIBLE_LONG_POLLING_CONTEXTS = {
    "main_menu_response",
    "role_help_text",
    "first_entry_response",
    "restart_onboarding_response",
    "cancel_onboarding_response",
    "staff_invite_start_response",
    "staff_request_text",
    "submit_staff_request",
    "decide_staff_request",
    "staff_join_callback_response",
    "knowledge_menu_response",
    "knowledge_section_response",
    "miniapp_response",
    "contact_entry_text",
    "handle_contact_payload_response",
    "handle_student_invitation_response",
    "handle_role_selection_response",
    "handle_message_created",
    "handle_message_callback",
}
EXCLUDED_JAVASCRIPT_CONTEXTS = {
    "canonicalImportField",
}

SOURCE_SPECS = (
    ("app/web/static/miniapp/index.html", "Приложение", "html"),
    ("app/web/static/miniapp/app-core.js", "Приложение", "javascript"),
    ("app/web/static/miniapp/app-shell.js", "Приложение", "javascript"),
    ("app/web/static/miniapp/app-store.js", "Приложение", "javascript"),
    ("app/web/static/miniapp/app-admin.js", "Приложение", "javascript"),
    ("app/web/static/miniapp/app-communications.js", "Приложение", "javascript"),
    ("app/web/static/miniapp/app.js", "Приложение", "javascript"),
    ("app/bot/keyboards.py", "MAX-бот", "python"),
    ("app/bot/max_long_polling.py", "MAX-бот", "python"),
    ("app/services/max_notifications.py", "Уведомления", "python"),
    ("data/knowledge_base.json", "База знаний", "json"),
)


@dataclass(frozen=True)
class Occurrence:
    source: str
    line: int
    context: str
    snippet: str
    surface: str
    kind: str
    audience: str


@dataclass(frozen=True)
class Candidate:
    text: str
    occurrence: Occurrence


@dataclass(frozen=True)
class JsLiteral:
    value: str
    offset: int
    quote: str


def normalize_fragment(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def text_fragments(value: str) -> Iterable[str]:
    for part in re.split(r"[\r\n]+", value):
        normalized = normalize_fragment(part)
        if normalized:
            yield normalized


def is_user_facing_text(value: str, *, trusted_source: bool = False) -> bool:
    visible_value = re.sub(r"\{[^{}]*\}", "", value)
    if len(value) < 2 or not LETTER_PATTERN.search(visible_value):
        return False
    if URL_PATTERN.match(visible_value) or TECHNICAL_LITERAL_PATTERN.match(visible_value):
        return False
    if value.startswith("data:image/") or value.startswith("application/"):
        return False
    if not trusted_source and not CYRILLIC_PATTERN.search(visible_value):
        return False
    return True


def is_feedback_text(value: str) -> bool:
    return bool(FEEDBACK_PATTERN.search(value))


def short_snippet(lines: list[str], line: int) -> str:
    if not lines:
        return ""
    safe_line = min(max(line, 1), len(lines))
    snippet = lines[safe_line - 1].strip()
    return snippet if len(snippet) <= 220 else f"{snippet[:217]}..."


def infer_issues(value: str) -> list[str]:
    visible_value = re.sub(r"\{[^{}]*\}", "", value)
    issues: list[str] = []
    if len(visible_value) > 140:
        issues.append("Длинный текст")
    if "!" in visible_value:
        issues.append("Восклицание")
    if re.search(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", visible_value):
        issues.append("Эмодзи")
    if re.search(
        r"\b(?:волшеб\w*|космич\w*|зв[её]зд\w*|приключ\w*|супер\w*|"
        r"ура|пораду\w*|невероят\w*|удивитель\w*)\b",
        visible_value,
        re.IGNORECASE,
    ):
        issues.append("Рекламный тон")
    if re.search(
        r"\b(?:tenant|slug|backend|frontend|active|inactive|MAX ID|URL)\b",
        visible_value,
        re.IGNORECASE,
    ):
        issues.append("Технический термин")
    latin_words = re.findall(r"\b[A-Za-z][A-Za-z0-9.+-]*\b", visible_value)
    allowed_latin = {
        "AC",
        "Algo",
        "MAX",
        "CRM",
        "QR",
        "SKU",
        "Python",
        "Roblox",
        "Google",
        "LMS",
        "VK",
        "Excel",
        "CSV",
        "XLSX",
    }
    if any(word not in allowed_latin for word in latin_words):
        issues.append("Английское слово")
    return issues


def audience_from_context(context: str, *, surface: str) -> str:
    normalized = context.lower()
    if surface == "Уведомления":
        if "low_stock" in normalized:
            return "Администраторы"
        return "Ученики и родители"
    if surface == "База знаний":
        return "Сотрудники"
    if any(
        marker in normalized
        for marker in (
            "admin",
            "staff",
            "warehouse",
            "inventory",
            "accrual",
            "report",
            "broadcast",
            "crm",
            "tenant",
        )
    ):
        return "Сотрудники"
    if any(
        marker in normalized
        for marker in ("cart", "wallet", "family", "invitation", "parent", "student")
    ):
        return "Ученики и родители"
    return "Все пользователи"


def python_call_name(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, ast.Call):
            function = current.func
            try:
                return ast.unparse(function)
            except Exception:  # noqa: BLE001
                return type(function).__name__
        current = parents.get(current)
    return ""


def python_has_ancestor(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
    ancestor_types: tuple[type[ast.AST], ...],
) -> bool:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ancestor_types):
            return True
        current = parents.get(current)
    return False


def render_joined_string(node: ast.JoinedStr) -> str:
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
            continue
        if isinstance(value, ast.FormattedValue):
            try:
                expression = ast.unparse(value.value)
            except Exception:  # noqa: BLE001
                expression = "значение"
            parts.append(f"{{{expression}}}")
    return "".join(parts)


class PythonExtractor(ast.NodeVisitor):
    def __init__(self, *, path: Path, surface: str) -> None:
        self.path = path
        self.relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        self.surface = surface
        self.source = path.read_text(encoding="utf-8")
        self.lines = self.source.splitlines()
        self.tree = ast.parse(self.source, filename=str(path))
        self.parents = {
            child: parent
            for parent in ast.walk(self.tree)
            for child in ast.iter_child_nodes(parent)
        }
        self.docstrings = self._docstring_node_ids()
        self.context_stack: list[str] = []
        self.candidates: list[Candidate] = []

    def _docstring_node_ids(self) -> set[int]:
        result: set[int] = set()
        for node in ast.walk(self.tree):
            if not isinstance(
                node,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                continue
            if not node.body:
                continue
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                result.add(id(first.value))
        return result

    def _visit_named_context(self, node: ast.AST, name: str) -> None:
        self.context_stack.append(name)
        self.generic_visit(node)
        self.context_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_named_context(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_named_context(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_named_context(node, node.name)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self._add(render_joined_string(node), node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, str) or id(node) in self.docstrings:
            return
        if isinstance(self.parents.get(node), ast.JoinedStr):
            return
        self._add(node.value, node)

    def _add(self, value: str, node: ast.AST) -> None:
        if any(
            "feedback" in part.lower() or part in EXCLUDED_PYTHON_CONTEXTS
            for part in self.context_stack
        ):
            return
        call_name = python_call_name(node, self.parents)
        if call_name.startswith(SYSTEM_CALL_PREFIXES):
            return
        if python_has_ancestor(node, self.parents, (ast.Raise, ast.Assert)):
            return
        if self.path.name == "max_long_polling.py":
            function_contexts = [
                part
                for part in self.context_stack
                if part != "LongPollingBot"
            ]
            if not function_contexts or function_contexts[-1] not in VISIBLE_LONG_POLLING_CONTEXTS:
                return

        context_parts = [*self.context_stack]
        if call_name:
            context_parts.append(call_name)
        context = " > ".join(context_parts) or "module"
        line = int(getattr(node, "lineno", 1) or 1)

        for fragment in text_fragments(value):
            if is_feedback_text(fragment):
                continue
            if not is_user_facing_text(fragment):
                continue
            kind = self._kind(call_name, context)
            audience = audience_from_context(context, surface=self.surface)
            self.candidates.append(
                Candidate(
                    text=fragment,
                    occurrence=Occurrence(
                        source=self.relative_path,
                        line=line,
                        context=context,
                        snippet=short_snippet(self.lines, line),
                        surface=self.surface,
                        kind=kind,
                        audience=audience,
                    ),
                )
            )

    def _kind(self, call_name: str, context: str) -> str:
        normalized = f"{call_name} {context}".lower()
        if self.surface == "Уведомления":
            return "Уведомление"
        if "button" in normalized or self.path.name == "keyboards.py":
            return "Кнопка бота"
        return "Сообщение бота"

    def extract(self) -> list[Candidate]:
        self.visit(self.tree)
        return self.candidates


class HtmlExtractor(HTMLParser):
    VISIBLE_ATTRIBUTES = {"aria-label", "title", "placeholder", "alt"}
    SKIPPED_TAGS = {"script", "style", "template"}

    def __init__(
        self,
        *,
        source_label: str,
        surface: str,
        source_lines: list[str],
        line_offset: int = 0,
        base_context: str = "",
    ) -> None:
        super().__init__(convert_charrefs=True)
        self.source_label = source_label
        self.surface = surface
        self.source_lines = source_lines
        self.line_offset = line_offset
        self.base_context = base_context
        self.stack: list[dict[str, str | bool]] = []
        self.candidates: list[Candidate] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {name: value or "" for name, value in attrs}
        marker = " ".join(
            [tag, values.get("id", ""), values.get("class", ""), self.base_context]
        )
        excluded = (
            bool(self.stack and self.stack[-1]["excluded"])
            or tag in self.SKIPPED_TAGS
            or is_feedback_text(marker)
        )
        context = values.get("id") or values.get("class") or tag
        self.stack.append({"tag": tag, "context": context, "excluded": excluded})
        if excluded:
            return
        for name, value in attrs:
            if name in self.VISIBLE_ATTRIBUTES and value:
                self._add(
                    value,
                    kind="Подсказка" if name != "placeholder" else "Поле ввода",
                    context=f"{context} [{name}]",
                )

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                return

    def handle_data(self, data: str) -> None:
        if not self.stack or bool(self.stack[-1]["excluded"]):
            return
        tag = str(self.stack[-1]["tag"])
        context = self._context()
        self._add(data, kind=self._kind_for_tag(tag), context=context)

    def _context(self) -> str:
        contexts = [
            str(item["context"])
            for item in self.stack
            if str(item["context"]) not in {"html", "body", "main", "section", "div", "span"}
        ]
        if self.base_context:
            contexts.insert(0, self.base_context)
        return " > ".join(contexts[-4:]) or self.base_context or "HTML"

    @staticmethod
    def _kind_for_tag(tag: str) -> str:
        if tag == "button":
            return "Кнопка"
        if tag == "option":
            return "Вариант выбора"
        if tag == "label":
            return "Подпись поля"
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "legend"}:
            return "Заголовок"
        if tag in {"a"}:
            return "Ссылка"
        return "Текст интерфейса"

    def _add(self, value: str, *, kind: str, context: str) -> None:
        line = self.line_offset + self.getpos()[0]
        for fragment in text_fragments(value):
            if is_feedback_text(fragment):
                continue
            if not is_user_facing_text(fragment, trusted_source=True):
                continue
            audience = audience_from_context(context, surface=self.surface)
            self.candidates.append(
                Candidate(
                    text=fragment,
                    occurrence=Occurrence(
                        source=self.source_label,
                        line=line,
                        context=context,
                        snippet=short_snippet(self.source_lines, line),
                        surface=self.surface,
                        kind=kind,
                        audience=audience,
                    ),
                )
            )


def extract_html(path: Path, surface: str) -> list[Candidate]:
    source = path.read_text(encoding="utf-8")
    parser = HtmlExtractor(
        source_label=path.relative_to(PROJECT_ROOT).as_posix(),
        surface=surface,
        source_lines=source.splitlines(),
    )
    parser.feed(source)
    return parser.candidates


def _consume_quoted_js(source: str, start: int, quote: str) -> tuple[int, str]:
    index = start + 1
    value: list[str] = []
    while index < len(source):
        char = source[index]
        if char == "\\" and index + 1 < len(source):
            escape = source[index + 1]
            replacements = {"n": "\n", "r": "\r", "t": "\t"}
            value.append(replacements.get(escape, escape))
            index += 2
            continue
        if char == quote:
            return index + 1, "".join(value)
        value.append(char)
        index += 1
    return len(source), "".join(value)


def _consume_line_comment(source: str, start: int) -> int:
    newline = source.find("\n", start + 2)
    return len(source) if newline < 0 else newline + 1


def _consume_block_comment(source: str, start: int) -> int:
    end = source.find("*/", start + 2)
    return len(source) if end < 0 else end + 2


def _template_placeholder(expression: str) -> str:
    normalized = re.sub(r"\s+", " ", expression).strip()
    if normalized and len(normalized) <= 48 and not re.search(r"[\"'{};]", normalized):
        return f"{{{normalized}}}"
    return "{…}"


def _find_template_expression_end(source: str, start: int) -> int:
    depth = 1
    index = start
    while index < len(source):
        if source.startswith("//", index):
            index = _consume_line_comment(source, index)
            continue
        if source.startswith("/*", index):
            index = _consume_block_comment(source, index)
            continue
        char = source[index]
        if char in {"'", '"'}:
            index, _ = _consume_quoted_js(source, index, char)
            continue
        if char == "`":
            index, _, _ = _consume_template_js(source, index)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(source)


def _consume_template_js(source: str, start: int) -> tuple[int, str, list[tuple[int, int]]]:
    index = start + 1
    parts: list[str] = []
    expression_ranges: list[tuple[int, int]] = []
    while index < len(source):
        char = source[index]
        if char == "\\" and index + 1 < len(source):
            escape = source[index + 1]
            replacements = {"n": "\n", "r": "\r", "t": "\t"}
            parts.append(replacements.get(escape, escape))
            index += 2
            continue
        if char == "`":
            return index + 1, "".join(parts), expression_ranges
        if source.startswith("${", index):
            expression_start = index + 2
            expression_end = _find_template_expression_end(source, expression_start)
            expression_ranges.append((expression_start, expression_end))
            parts.append(_template_placeholder(source[expression_start:expression_end]))
            index = min(expression_end + 1, len(source))
            continue
        parts.append(char)
        index += 1
    return len(source), "".join(parts), expression_ranges


def iter_js_literals(
    source: str,
    *,
    start: int = 0,
    end: int | None = None,
) -> Iterable[JsLiteral]:
    limit = len(source) if end is None else min(end, len(source))
    index = start
    while index < limit:
        if source.startswith("//", index):
            index = _consume_line_comment(source, index)
            continue
        if source.startswith("/*", index):
            index = _consume_block_comment(source, index)
            continue
        char = source[index]
        if char in {"'", '"'}:
            literal_end, value = _consume_quoted_js(source, index, char)
            yield JsLiteral(value=value, offset=index, quote=char)
            index = literal_end
            continue
        if char == "`":
            literal_end, value, expression_ranges = _consume_template_js(source, index)
            yield JsLiteral(value=value, offset=index, quote=char)
            for expression_start, expression_end in expression_ranges:
                yield from iter_js_literals(
                    source,
                    start=expression_start,
                    end=expression_end,
                )
            index = literal_end
            continue
        index += 1


def line_number_for_offset(newlines: list[int], offset: int) -> int:
    return bisect_right(newlines, offset) + 1


def _find_matching_brace(source: str, start: int) -> int:
    depth = 0
    index = start
    while index < len(source):
        if source.startswith("//", index):
            index = _consume_line_comment(source, index)
            continue
        if source.startswith("/*", index):
            index = _consume_block_comment(source, index)
            continue
        char = source[index]
        if char in {"'", '"'}:
            index, _ = _consume_quoted_js(source, index, char)
            continue
        if char == "`":
            index, _, _ = _consume_template_js(source, index)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return len(source) - 1


def javascript_function_ranges(source: str) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    function_pattern = re.compile(
        r"(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"
    )
    for match in function_pattern.finditer(source):
        opening_brace = source.find("{", match.start(), match.end())
        if opening_brace < 0:
            continue
        ranges.append((match.start(), _find_matching_brace(source, opening_brace), match.group(1)))
    return ranges


def javascript_excluded_ranges(source: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    declarations = (
        "let students =",
        "let accessLinks =",
        "let staffAssignments =",
        "let products =",
        "let orders =",
        "let ledger =",
        "const warehouses =",
        "let catalogWarehouses =",
    )
    for declaration in declarations:
        start = source.find(declaration)
        if start < 0:
            continue
        opening_positions = [
            position
            for position in (source.find("{", start), source.find("[", start))
            if position >= 0
        ]
        if not opening_positions:
            continue
        opening = min(opening_positions)
        opening_char = source[opening]
        closing_char = "}" if opening_char == "{" else "]"
        depth = 0
        index = opening
        while index < len(source):
            if source.startswith("//", index):
                index = _consume_line_comment(source, index)
                continue
            if source.startswith("/*", index):
                index = _consume_block_comment(source, index)
                continue
            char = source[index]
            if char in {"'", '"'}:
                index, _ = _consume_quoted_js(source, index, char)
                continue
            if char == "`":
                index, _, _ = _consume_template_js(source, index)
                continue
            if char == opening_char:
                depth += 1
            elif char == closing_char:
                depth -= 1
                if depth == 0:
                    ranges.append((start, index))
                    break
            index += 1
    return ranges


def offset_in_ranges(offset: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= offset <= end for start, end in ranges)


def javascript_context(
    offset: int,
    function_ranges: list[tuple[int, int, str]],
) -> str:
    matches = [
        (end - start, name)
        for start, end, name in function_ranges
        if start <= offset <= end
    ]
    return min(matches)[1] if matches else "module"


def javascript_kind(context: str, snippet: str, *, is_markup: bool) -> str:
    normalized = f"{context} {snippet}".lower()
    if "shownotice" in normalized or "toast" in normalized:
        return "Сообщение интерфейса"
    if "placeholder" in normalized:
        return "Поле ввода"
    if "aria-label" in normalized or "title=" in normalized:
        return "Подсказка"
    if "button" in normalized:
        return "Кнопка"
    if is_markup:
        return "Текст интерфейса"
    return "Динамический текст"


def extract_javascript(path: Path, surface: str) -> list[Candidate]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
    newlines = [match.start() for match in re.finditer("\n", source)]
    function_ranges = javascript_function_ranges(source)
    excluded_ranges = javascript_excluded_ranges(source)
    candidates: list[Candidate] = []

    for literal in iter_js_literals(source):
        if offset_in_ranges(literal.offset, excluded_ranges):
            continue
        context = javascript_context(literal.offset, function_ranges)
        if "feedback" in context.lower() or context in EXCLUDED_JAVASCRIPT_CONTEXTS:
            continue
        line = line_number_for_offset(newlines, literal.offset)
        snippet = short_snippet(lines, line)
        is_markup = "<" in literal.value and ">" in literal.value

        if is_markup:
            parser = HtmlExtractor(
                source_label=relative_path,
                surface=surface,
                source_lines=lines,
                line_offset=line - 1,
                base_context=context,
            )
            try:
                parser.feed(literal.value)
            except Exception:  # noqa: BLE001
                parser.candidates.clear()
            candidates.extend(parser.candidates)
            continue

        for fragment in text_fragments(literal.value):
            if is_feedback_text(fragment):
                continue
            if not is_user_facing_text(fragment):
                continue
            kind = javascript_kind(context, snippet, is_markup=False)
            audience = audience_from_context(context, surface=surface)
            candidates.append(
                Candidate(
                    text=fragment,
                    occurrence=Occurrence(
                        source=relative_path,
                        line=line,
                        context=context,
                        snippet=snippet,
                        surface=surface,
                        kind=kind,
                        audience=audience,
                    ),
                )
            )
    return candidates


def extract_json(path: Path, surface: str) -> list[Candidate]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    payload = json.loads(source)
    relative_path = path.relative_to(PROJECT_ROOT).as_posix()
    candidates: list[Candidate] = []
    search_offset = 0

    def walk(value: object, context: str = "root") -> None:
        nonlocal search_offset
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"url", "callback", "id"}:
                    continue
                walk(child, f"{context}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{context}[{index}]")
            return
        if not isinstance(value, str):
            return

        encoded = json.dumps(value, ensure_ascii=False)
        position = source.find(encoded, search_offset)
        if position < 0:
            position = source.find(encoded)
        if position >= 0:
            search_offset = position + len(encoded)
            line = source.count("\n", 0, position) + 1
        else:
            line = 1

        for fragment in text_fragments(value):
            if is_feedback_text(fragment):
                continue
            if not is_user_facing_text(fragment, trusted_source=True):
                continue
            candidates.append(
                Candidate(
                    text=fragment,
                    occurrence=Occurrence(
                        source=relative_path,
                        line=line,
                        context=context,
                        snippet=short_snippet(lines, line),
                        surface=surface,
                        kind="Материал базы знаний",
                        audience="Сотрудники",
                    ),
                )
            )

    walk(payload)
    return candidates


def extract_candidates() -> list[Candidate]:
    candidates: list[Candidate] = []
    for relative_path, surface, parser_name in SOURCE_SPECS:
        path = PROJECT_ROOT / relative_path
        if not path.exists():
            continue
        if parser_name == "html":
            candidates.extend(extract_html(path, surface))
        elif parser_name == "javascript":
            candidates.extend(extract_javascript(path, surface))
        elif parser_name == "python":
            candidates.extend(PythonExtractor(path=path, surface=surface).extract())
        elif parser_name == "json":
            candidates.extend(extract_json(path, surface))
    return candidates


def build_catalog(candidates: list[Candidate]) -> dict[str, object]:
    grouped: dict[str, list[Occurrence]] = defaultdict(list)
    for candidate in candidates:
        if candidate.occurrence not in grouped[candidate.text]:
            grouped[candidate.text].append(candidate.occurrence)

    items: list[dict[str, object]] = []
    for text, occurrences in grouped.items():
        item_id = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        items.append(
            {
                "id": item_id,
                "text": text,
                "surfaces": sorted({item.surface for item in occurrences}),
                "kinds": sorted({item.kind for item in occurrences}),
                "audiences": sorted({item.audience for item in occurrences}),
                "issues": infer_issues(text),
                "occurrences": [asdict(item) for item in occurrences],
            }
        )

    surface_order = {name: index for index, name in enumerate(
        ("Приложение", "MAX-бот", "Уведомления", "База знаний")
    )}
    items.sort(
        key=lambda item: (
            min(surface_order.get(surface, 99) for surface in item["surfaces"]),
            str(item["occurrences"][0]["source"]),
            int(item["occurrences"][0]["line"]),
            str(item["text"]).casefold(),
        )
    )
    return {
        "version": 1,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "scope": "Тексты приложения, MAX-бота, пользовательских уведомлений и базы знаний",
        "items": items,
        "stats": {
            "uniqueTexts": len(items),
            "occurrences": sum(len(item["occurrences"]) for item in items),
            "sources": len({item.occurrence.source for item in candidates}),
        },
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Каталог текстов Algo MAX</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='10' fill='%236f35d5'/%3E%3Ctext x='32' y='44' text-anchor='middle' font-family='Arial' font-size='40' font-weight='700' fill='white'%3EA%3C/text%3E%3C/svg%3E">
  <style>
    :root {
      color-scheme: light;
      --ink: #171326;
      --muted: #69647a;
      --line: #dedbe6;
      --surface: #ffffff;
      --canvas: #f6f5f8;
      --purple: #6f35d5;
      --purple-soft: #efe7ff;
      --yellow: #ffd43b;
      --yellow-soft: #fff5bf;
      --teal: #087e78;
      --teal-soft: #dcf5f1;
      --red: #c9324d;
      --red-soft: #ffe4e9;
      --shadow: 0 8px 22px rgba(23, 19, 38, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--canvas);
      color: var(--ink);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      font-size: 15px;
      line-height: 1.45;
      letter-spacing: 0;
    }
    button, input, select, textarea { font: inherit; letter-spacing: 0; }
    button, select { cursor: pointer; }
    button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
      outline: 3px solid rgba(111, 53, 213, 0.24);
      outline-offset: 2px;
    }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      min-height: 78px;
      padding: 14px 28px;
      background: rgba(255, 255, 255, 0.97);
      border-bottom: 1px solid var(--line);
    }
    .brand { display: flex; align-items: center; gap: 13px; min-width: 0; }
    .brand-mark {
      display: grid;
      place-items: center;
      width: 44px;
      height: 44px;
      flex: 0 0 44px;
      border-radius: 8px;
      background: var(--purple);
      color: white;
      font-weight: 800;
      font-size: 22px;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 21px; line-height: 1.2; }
    .subtitle { margin-top: 3px; color: var(--muted); font-size: 13px; }
    .header-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .button {
      min-height: 40px;
      padding: 8px 14px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: white;
      color: var(--ink);
      font-weight: 700;
    }
    .button:hover { border-color: #bdb7ca; background: #faf9fc; }
    .button.primary { border-color: var(--purple); background: var(--purple); color: white; }
    .button.danger { color: var(--red); }
    .button.icon {
      width: 40px;
      padding: 0;
      font-size: 20px;
      line-height: 1;
    }
    .summary {
      display: grid;
      grid-template-columns: minmax(260px, 1.6fr) repeat(4, minmax(120px, 0.7fr));
      border-bottom: 1px solid var(--line);
      background: var(--surface);
    }
    .summary-cell {
      min-height: 88px;
      padding: 17px 22px;
      border-right: 1px solid var(--line);
    }
    .summary-cell:last-child { border-right: 0; }
    .summary-label {
      display: block;
      margin-bottom: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .summary-value { font-size: 25px; font-weight: 800; }
    .progress-track {
      height: 8px;
      margin-top: 12px;
      overflow: hidden;
      border-radius: 4px;
      background: #e9e6ee;
    }
    .progress-value { width: 0; height: 100%; background: var(--teal); transition: width 160ms ease; }
    .layout {
      display: grid;
      grid-template-columns: 270px minmax(0, 1fr);
      min-height: calc(100vh - 167px);
    }
    .filters {
      padding: 22px 18px;
      border-right: 1px solid var(--line);
      background: #fbfafc;
    }
    .filters h2 { margin-bottom: 18px; font-size: 16px; }
    .filter-group { margin-bottom: 17px; }
    .filter-label {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .field {
      width: 100%;
      min-height: 40px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--ink);
    }
    .checkbox-line { display: flex; align-items: flex-start; gap: 9px; font-size: 13px; }
    .checkbox-line input { width: 17px; height: 17px; margin: 1px 0 0; accent-color: var(--purple); }
    .filter-reset { width: 100%; }
    .content { min-width: 0; padding: 22px 24px 36px; }
    .toolbar {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) 190px auto;
      gap: 10px;
      align-items: center;
      margin-bottom: 12px;
    }
    .search { min-height: 44px; padding-left: 13px; }
    .result-line {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 13px;
    }
    .saved-indicator { color: var(--teal); font-weight: 700; }
    .text-list { display: grid; gap: 10px; }
    .text-item {
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: 0 2px 8px rgba(23, 19, 38, 0.035);
    }
    .text-item[data-decision="keep"] { border-left: 4px solid var(--teal); }
    .text-item[data-decision="change"] { border-left: 4px solid var(--yellow); }
    .text-item[data-decision="delete"] { border-left: 4px solid var(--red); }
    .item-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 11px 14px;
      border-bottom: 1px solid #ece9f0;
      background: #fcfbfd;
    }
    .meta, .tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-width: 0; }
    .tag {
      display: inline-flex;
      align-items: center;
      min-height: 25px;
      padding: 3px 8px;
      border-radius: 5px;
      background: #ece9f0;
      color: #514b60;
      font-size: 11px;
      font-weight: 700;
    }
    .tag.surface { background: var(--purple-soft); color: #5927ae; }
    .tag.issue { background: var(--yellow-soft); color: #6f5700; }
    .tag.count { background: var(--teal-soft); color: #076c67; }
    .decision {
      flex: 0 0 158px;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      font-weight: 700;
    }
    .item-body { padding: 16px 17px; }
    .current-text {
      max-width: 1050px;
      font-size: 17px;
      font-weight: 650;
      line-height: 1.48;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }
    .item-context { margin-top: 10px; color: var(--muted); font-size: 12px; }
    .edit-fields {
      display: none;
      grid-template-columns: minmax(0, 1.4fr) minmax(220px, 0.8fr);
      gap: 12px;
      margin-top: 15px;
      padding-top: 15px;
      border-top: 1px solid var(--line);
    }
    .text-item[data-decision="change"] .edit-fields,
    .text-item[data-has-note="true"] .edit-fields { display: grid; }
    .field-label { display: block; margin-bottom: 6px; color: var(--muted); font-size: 12px; font-weight: 700; }
    textarea.field { min-height: 84px; resize: vertical; }
    .occurrences {
      margin-top: 13px;
      border-top: 1px solid var(--line);
      padding-top: 12px;
    }
    .occurrences summary {
      cursor: pointer;
      color: #514b60;
      font-size: 13px;
      font-weight: 700;
    }
    .source-list { display: grid; gap: 8px; margin-top: 10px; }
    .source-row {
      display: grid;
      grid-template-columns: minmax(210px, 0.7fr) minmax(260px, 1.3fr);
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid #f0edf3;
      font-size: 12px;
    }
    .source-row:last-child { border-bottom: 0; }
    .source-path { color: #5927ae; font-family: Consolas, "Courier New", monospace; overflow-wrap: anywhere; }
    .source-snippet { color: var(--muted); font-family: Consolas, "Courier New", monospace; overflow-wrap: anywhere; }
    .empty {
      padding: 64px 24px;
      border: 1px dashed #c9c3d1;
      border-radius: 8px;
      background: white;
      text-align: center;
      color: var(--muted);
    }
    .pagination {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 9px;
      margin-top: 18px;
    }
    .page-label { min-width: 110px; text-align: center; color: var(--muted); font-size: 13px; }
    .mobile-filter-toggle { display: none; }
    .file-input { display: none; }
    @media (max-width: 980px) {
      .topbar { position: static; align-items: flex-start; padding: 14px 16px; }
      .header-actions { justify-content: flex-end; }
      .summary { grid-template-columns: repeat(2, 1fr); }
      .summary-cell:first-child { grid-column: 1 / -1; }
      .layout { display: block; }
      .filters { display: none; border-right: 0; border-bottom: 1px solid var(--line); }
      .filters.is-open { display: block; }
      .mobile-filter-toggle { display: inline-flex; }
      .content { padding: 16px 12px 30px; }
      .toolbar { grid-template-columns: minmax(0, 1fr) auto; }
      .toolbar .sort-field { grid-column: 1 / -1; }
    }
    @media (max-width: 640px) {
      .topbar { display: block; }
      .brand { margin-bottom: 12px; }
      .header-actions { display: grid; grid-template-columns: 1fr 1fr; }
      .header-actions .button { width: 100%; }
      .summary { grid-template-columns: 1fr 1fr; }
      .summary-cell { min-height: 74px; padding: 13px 14px; }
      .summary-value { font-size: 21px; }
      .item-head { display: block; }
      .decision { width: 100%; margin-top: 10px; }
      .edit-fields { grid-template-columns: 1fr; }
      .source-row { grid-template-columns: 1fr; gap: 4px; }
      .result-line { display: block; }
    }
    @media print {
      .topbar, .filters, .toolbar, .pagination, .header-actions { display: none !important; }
      .layout { display: block; }
      .content { padding: 0; }
      .text-item { break-inside: avoid; box-shadow: none; }
      .edit-fields { display: grid; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <span class="brand-mark" aria-hidden="true">A</span>
      <div>
        <h1>Каталог пользовательских текстов</h1>
        <p class="subtitle">Приложение, MAX-бот, уведомления и база знаний</p>
      </div>
    </div>
    <div class="header-actions">
      <button id="copyButton" class="button" type="button">Скопировать правки</button>
      <button id="importButton" class="button" type="button">Загрузить проверку</button>
      <button id="exportButton" class="button primary" type="button">Скачать результат</button>
      <input id="importInput" class="file-input" type="file" accept="application/json,.json">
    </div>
  </header>

  <section class="summary" aria-label="Ход проверки">
    <div class="summary-cell">
      <span class="summary-label">Проверено</span>
      <strong id="progressText" class="summary-value">0%</strong>
      <div class="progress-track"><div id="progressValue" class="progress-value"></div></div>
    </div>
    <div class="summary-cell">
      <span class="summary-label">Всего фраз</span>
      <strong id="totalCount" class="summary-value">0</strong>
    </div>
    <div class="summary-cell">
      <span class="summary-label">Оставить</span>
      <strong id="keepCount" class="summary-value">0</strong>
    </div>
    <div class="summary-cell">
      <span class="summary-label">Изменить</span>
      <strong id="changeCount" class="summary-value">0</strong>
    </div>
    <div class="summary-cell">
      <span class="summary-label">Удалить</span>
      <strong id="deleteCount" class="summary-value">0</strong>
    </div>
  </section>

  <div class="layout">
    <aside id="filters" class="filters">
      <h2>Фильтры</h2>
      <div class="filter-group">
        <label class="filter-label" for="surfaceFilter">Раздел</label>
        <select id="surfaceFilter" class="field"></select>
      </div>
      <div class="filter-group">
        <label class="filter-label" for="audienceFilter">Аудитория</label>
        <select id="audienceFilter" class="field"></select>
      </div>
      <div class="filter-group">
        <label class="filter-label" for="kindFilter">Тип текста</label>
        <select id="kindFilter" class="field"></select>
      </div>
      <div class="filter-group">
        <label class="filter-label" for="decisionFilter">Решение</label>
        <select id="decisionFilter" class="field">
          <option value="">Все решения</option>
          <option value="pending">Не проверено</option>
          <option value="keep">Оставить</option>
          <option value="change">Изменить</option>
          <option value="delete">Удалить</option>
        </select>
      </div>
      <div class="filter-group">
        <label class="filter-label" for="issueFilter">На что обратить внимание</label>
        <select id="issueFilter" class="field"></select>
      </div>
      <div class="filter-group">
        <label class="checkbox-line">
          <input id="issuesOnly" type="checkbox">
          <span>Только фразы с замечаниями</span>
        </label>
      </div>
      <button id="resetFilters" class="button filter-reset" type="button">Сбросить фильтры</button>
      <button id="resetReview" class="button danger filter-reset" type="button">Очистить проверку</button>
    </aside>

    <main class="content">
      <div class="toolbar">
        <input id="searchInput" class="field search" type="search" placeholder="Найти фразу, файл или раздел">
        <select id="sortField" class="field sort-field" aria-label="Сортировка">
          <option value="source">По порядку в проекте</option>
          <option value="text">По алфавиту</option>
          <option value="issues">Сначала с замечаниями</option>
          <option value="decision">По решению</option>
        </select>
        <button id="mobileFilterToggle" class="button mobile-filter-toggle" type="button">Фильтры</button>
      </div>
      <div class="result-line">
        <span id="resultCount"></span>
        <span id="savedIndicator" class="saved-indicator">Изменения сохраняются в этом браузере</span>
      </div>
      <div id="textList" class="text-list"></div>
      <nav class="pagination" aria-label="Страницы каталога">
        <button id="previousPage" class="button icon" type="button" title="Предыдущая страница" aria-label="Предыдущая страница">‹</button>
        <span id="pageLabel" class="page-label"></span>
        <button id="nextPage" class="button icon" type="button" title="Следующая страница" aria-label="Следующая страница">›</button>
      </nav>
    </main>
  </div>

  <script>
    const catalog = __CATALOG_DATA__;
    const STORAGE_KEY = "algo-max-ui-text-review-v1";
    const PAGE_SIZE = 30;
    const decisionLabels = {
      pending: "Не проверено",
      keep: "Оставить",
      change: "Изменить",
      delete: "Удалить",
    };
    let page = 1;
    let reviews = loadReviews();

    const byId = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

    function loadReviews() {
      try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      } catch {
        return {};
      }
    }

    function saveReviews() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(reviews));
        byId("savedIndicator").textContent = "Сохранено в этом браузере";
      } catch {
        byId("savedIndicator").textContent = "Автосохранение недоступно, скачайте результат";
      }
      updateSummary();
    }

    function reviewFor(item) {
      return {
        decision: "pending",
        replacement: "",
        note: "",
        ...(reviews[item.id] || {}),
      };
    }

    function uniqueValues(field) {
      return [...new Set(catalog.items.flatMap((item) => item[field]))]
        .sort((left, right) => left.localeCompare(right, "ru"));
    }

    function fillSelect(id, values, emptyLabel) {
      byId(id).innerHTML = [
        `<option value="">${escapeHtml(emptyLabel)}</option>`,
        ...values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`),
      ].join("");
    }

    function filterState() {
      return {
        query: byId("searchInput").value.trim().toLocaleLowerCase("ru"),
        surface: byId("surfaceFilter").value,
        audience: byId("audienceFilter").value,
        kind: byId("kindFilter").value,
        decision: byId("decisionFilter").value,
        issue: byId("issueFilter").value,
        issuesOnly: byId("issuesOnly").checked,
        sort: byId("sortField").value,
      };
    }

    function filteredItems() {
      const filters = filterState();
      const items = catalog.items.filter((item) => {
        const review = reviewFor(item);
        const haystack = [
          item.text,
          ...item.surfaces,
          ...item.kinds,
          ...item.audiences,
          ...item.issues,
          ...item.occurrences.flatMap((entry) => [entry.source, entry.context, entry.snippet]),
        ].join(" ").toLocaleLowerCase("ru");
        return (!filters.query || haystack.includes(filters.query))
          && (!filters.surface || item.surfaces.includes(filters.surface))
          && (!filters.audience || item.audiences.includes(filters.audience))
          && (!filters.kind || item.kinds.includes(filters.kind))
          && (!filters.decision || review.decision === filters.decision)
          && (!filters.issue || item.issues.includes(filters.issue))
          && (!filters.issuesOnly || item.issues.length > 0);
      });

      const decisionOrder = { change: 0, delete: 1, pending: 2, keep: 3 };
      items.sort((left, right) => {
        if (filters.sort === "text") return left.text.localeCompare(right.text, "ru");
        if (filters.sort === "issues") {
          return right.issues.length - left.issues.length || left.text.localeCompare(right.text, "ru");
        }
        if (filters.sort === "decision") {
          return decisionOrder[reviewFor(left).decision] - decisionOrder[reviewFor(right).decision];
        }
        return catalog.items.indexOf(left) - catalog.items.indexOf(right);
      });
      return items;
    }

    function tags(values, className = "") {
      return values.map((value) => `<span class="tag ${className}">${escapeHtml(value)}</span>`).join("");
    }

    function itemMarkup(item) {
      const review = reviewFor(item);
      const occurrenceLabel = item.occurrences.length === 1
        ? "1 место"
        : `${item.occurrences.length} мест`;
      return `
        <article class="text-item" data-item-id="${item.id}" data-decision="${review.decision}" data-has-note="${Boolean(review.note)}">
          <div class="item-head">
            <div class="meta">
              ${tags(item.surfaces, "surface")}
              ${tags(item.kinds)}
              ${item.occurrences.length > 1 ? `<span class="tag count">${occurrenceLabel}</span>` : ""}
              ${tags(item.issues, "issue")}
            </div>
            <select class="decision" data-review-field="decision" aria-label="Решение по фразе">
              ${Object.entries(decisionLabels).map(([value, label]) =>
                `<option value="${value}" ${review.decision === value ? "selected" : ""}>${label}</option>`
              ).join("")}
            </select>
          </div>
          <div class="item-body">
            <p class="current-text">${escapeHtml(item.text)}</p>
            <p class="item-context">${escapeHtml(item.audiences.join(", "))}</p>
            <div class="edit-fields">
              <label>
                <span class="field-label">Новая формулировка</span>
                <textarea class="field" data-review-field="replacement" placeholder="Напишите итоговый вариант">${escapeHtml(review.replacement)}</textarea>
              </label>
              <label>
                <span class="field-label">Комментарий</span>
                <textarea class="field" data-review-field="note" placeholder="Что именно нужно поправить">${escapeHtml(review.note)}</textarea>
              </label>
            </div>
            <details class="occurrences">
              <summary>Где используется: ${occurrenceLabel}</summary>
              <div class="source-list">
                ${item.occurrences.map((entry) => `
                  <div class="source-row">
                    <div>
                      <div class="source-path">${escapeHtml(entry.source)}:${entry.line}</div>
                      <div>${escapeHtml(entry.context)}</div>
                    </div>
                    <div class="source-snippet">${escapeHtml(entry.snippet)}</div>
                  </div>
                `).join("")}
              </div>
            </details>
          </div>
        </article>
      `;
    }

    function render() {
      const items = filteredItems();
      const pageCount = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
      page = Math.min(Math.max(page, 1), pageCount);
      const visible = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
      byId("resultCount").textContent = `Найдено: ${items.length} из ${catalog.items.length}`;
      byId("pageLabel").textContent = `${page} из ${pageCount}`;
      byId("previousPage").disabled = page <= 1;
      byId("nextPage").disabled = page >= pageCount;
      byId("textList").innerHTML = visible.length
        ? visible.map(itemMarkup).join("")
        : '<div class="empty">По выбранным фильтрам ничего не найдено</div>';
      updateSummary();
    }

    function updateSummary() {
      const counts = { pending: 0, keep: 0, change: 0, delete: 0 };
      catalog.items.forEach((item) => { counts[reviewFor(item).decision] += 1; });
      const reviewed = catalog.items.length - counts.pending;
      const percent = catalog.items.length ? Math.round(reviewed * 100 / catalog.items.length) : 0;
      byId("totalCount").textContent = catalog.items.length;
      byId("keepCount").textContent = counts.keep;
      byId("changeCount").textContent = counts.change;
      byId("deleteCount").textContent = counts.delete;
      byId("progressText").textContent = `${percent}%`;
      byId("progressValue").style.width = `${percent}%`;
    }

    function updateReview(itemElement, field, value) {
      const itemId = itemElement.dataset.itemId;
      reviews[itemId] = { ...reviewFor({ id: itemId }), [field]: value, updatedAt: new Date().toISOString() };
      itemElement.dataset.decision = reviews[itemId].decision;
      itemElement.dataset.hasNote = Boolean(reviews[itemId].note);
      saveReviews();
      if (field === "decision" && byId("decisionFilter").value) render();
    }

    function exportedReview() {
      return {
        format: "algo-max-ui-text-review",
        version: 1,
        catalogGeneratedAt: catalog.generatedAt,
        exportedAt: new Date().toISOString(),
        items: catalog.items
          .map((item) => ({ ...item, review: reviewFor(item) }))
          .filter((item) =>
            item.review.decision !== "pending" || item.review.replacement || item.review.note
          ),
      };
    }

    function downloadJson() {
      const blob = new Blob([JSON.stringify(exportedReview(), null, 2)], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "algo-max-text-review.json";
      link.click();
      URL.revokeObjectURL(url);
    }

    async function copyReview() {
      const selected = exportedReview().items;
      const lines = selected.length
        ? selected.flatMap((item, index) => {
            const review = item.review;
            return [
              `${index + 1}. ${decisionLabels[review.decision]}: ${item.text}`,
              review.replacement ? `Новый текст: ${review.replacement}` : "",
              review.note ? `Комментарий: ${review.note}` : "",
              `Источник: ${item.occurrences[0].source}:${item.occurrences[0].line}`,
              "",
            ].filter(Boolean);
          })
        : ["Проверенные изменения пока не отмечены."];
      try {
        await navigator.clipboard.writeText(lines.join("\n"));
        byId("savedIndicator").textContent = "Правки скопированы";
      } catch {
        byId("savedIndicator").textContent = "Не удалось скопировать, скачайте результат";
      }
    }

    function importReview(file) {
      const reader = new FileReader();
      reader.addEventListener("load", () => {
        try {
          const payload = JSON.parse(String(reader.result || ""));
          if (payload.format !== "algo-max-ui-text-review" || !Array.isArray(payload.items)) {
            throw new Error("unknown format");
          }
          for (const item of payload.items) {
            if (item.id && item.review) reviews[item.id] = item.review;
          }
          saveReviews();
          render();
          byId("savedIndicator").textContent = "Проверка загружена";
        } catch {
          byId("savedIndicator").textContent = "Файл проверки не распознан";
        }
      });
      reader.readAsText(file, "utf-8");
    }

    fillSelect("surfaceFilter", uniqueValues("surfaces"), "Все разделы");
    fillSelect("audienceFilter", uniqueValues("audiences"), "Все аудитории");
    fillSelect("kindFilter", uniqueValues("kinds"), "Все типы");
    fillSelect("issueFilter", uniqueValues("issues"), "Все замечания");

    byId("textList").addEventListener("input", (event) => {
      const field = event.target.dataset.reviewField;
      const item = event.target.closest(".text-item");
      if (field && item) updateReview(item, field, event.target.value);
    });
    byId("textList").addEventListener("change", (event) => {
      const field = event.target.dataset.reviewField;
      const item = event.target.closest(".text-item");
      if (field && item) updateReview(item, field, event.target.value);
    });

    ["searchInput", "surfaceFilter", "audienceFilter", "kindFilter", "decisionFilter", "issueFilter", "issuesOnly", "sortField"]
      .forEach((id) => {
        byId(id).addEventListener(id === "searchInput" ? "input" : "change", () => {
          page = 1;
          render();
        });
      });

    byId("previousPage").addEventListener("click", () => { page -= 1; render(); window.scrollTo({ top: 160, behavior: "smooth" }); });
    byId("nextPage").addEventListener("click", () => { page += 1; render(); window.scrollTo({ top: 160, behavior: "smooth" }); });
    byId("exportButton").addEventListener("click", downloadJson);
    byId("copyButton").addEventListener("click", copyReview);
    byId("importButton").addEventListener("click", () => byId("importInput").click());
    byId("importInput").addEventListener("change", (event) => {
      const file = event.target.files?.[0];
      if (file) importReview(file);
      event.target.value = "";
    });
    byId("mobileFilterToggle").addEventListener("click", () => byId("filters").classList.toggle("is-open"));
    byId("resetFilters").addEventListener("click", () => {
      ["searchInput", "surfaceFilter", "audienceFilter", "kindFilter", "decisionFilter", "issueFilter"]
        .forEach((id) => { byId(id).value = ""; });
      byId("issuesOnly").checked = false;
      byId("sortField").value = "source";
      page = 1;
      render();
    });
    byId("resetReview").addEventListener("click", () => {
      if (!confirm("Удалить все отметки и предложенные формулировки в этом браузере?")) return;
      reviews = {};
      saveReviews();
      render();
    });

    render();
  </script>
</body>
</html>
"""


def write_catalog(output: Path) -> dict[str, object]:
    catalog = build_catalog(extract_candidates())
    serialized = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    serialized = serialized.replace("<", "\\u003c")
    document = HTML_TEMPLATE.replace("__CATALOG_DATA__", serialized)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Создать автономный HTML-каталог пользовательских текстов Algo MAX."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Путь итогового HTML-файла (по умолчанию: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    catalog = write_catalog(output)
    stats = catalog["stats"]
    print(f"Каталог создан: {output}")
    print(
        f"Уникальных фраз: {stats['uniqueTexts']}; "
        f"вхождений: {stats['occurrences']}; "
        f"источников: {stats['sources']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
