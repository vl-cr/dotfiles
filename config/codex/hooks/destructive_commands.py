#!/usr/bin/env python3

"""Catch accidentally destructive shell commands without evaluating them.

Codex sandboxing and approvals remain the security boundary. This hook is an
additional, deliberately conservative accident guard.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import posixpath
import re
import shlex
import sys


MAX_DEPTH = 8
MAX_SOURCE_LENGTH = 100_000
MAX_TOKENS = 10_000
GENERIC_REASON = "Unable to verify this shell command safely."

ROOT_REASON = "Never recursively delete the root filesystem."
HOME_REASON = "Never recursively delete an entire home directory."
USERS_REASON = "Never recursively delete all user directories."
SYSTEM_REASON = "Never recursively delete macOS system files."
DISK_REASON = "Never erase, repartition, or format a disk."

SHELLS = frozenset({"ash", "bash", "dash", "ksh", "sh", "zsh"})
CONTROL_WORDS = frozenset(
    {
        "case", "do", "done", "elif", "else", "esac", "fi", "for", "if",
        "select", "then", "until", "while",
    }
)
FORMATTERS = frozenset({"blkdiscard", "mke2fs", "mkfs", "newfs", "wipefs"})
FORMATTER_PREFIXES = ("mkfs.", "newfs_")
SYSTEM_ROOTS = frozenset(
    {
        "/Applications",
        "/Library",
        "/System",
        "/Users",
        "/Volumes",
        "/bin",
        "/boot",
        "/etc",
        "/home",
        "/lib",
        "/lib64",
        "/opt",
        "/private",
        "/root",
        "/sbin",
        "/usr",
        "/var",
    }
)
SYSTEM_TREES = SYSTEM_ROOTS - {"/Applications", "/Users", "/Volumes", "/home"}
DISKUTIL_ACTIONS = frozenset(
    {
        ("erasedisk",),
        ("eraseoptical",),
        ("erasevolume",),
        ("mergepartitions",),
        ("partitiondisk",),
        ("randomdisk",),
        ("reformat",),
        ("resetfusion",),
        ("resizevolume",),
        ("secureerase",),
        ("splitpartition",),
        ("zerodisk",),
        ("apfs", "deletecontainer"),
        ("apfs", "deletesnapshot"),
        ("apfs", "deletevolume"),
        ("apfs", "deletevolumegroup"),
        ("apfs", "erasevolume"),
        ("apfs", "resizecontainer"),
        ("corestorage", "delete"),
        ("corestorage", "deletelvg"),
        ("corestorage", "deletevolume"),
    }
)

ASSIGNMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PLAIN_PARAMETER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

type Variables = dict[str, str | None]
type Functions = dict[str, str | None]

ACTUAL_HOME_KEY = "__CODEX_ACTUAL_HOME"
OPAQUE_STATE_KEY = "__CODEX_OPAQUE_STATE"


class ParseError(ValueError):
    """Raised when shell input cannot be analysed safely."""


@dataclass
class AnalysisBudget:
    """Shared work budget across recursive shell analysis."""

    remaining: int = 500_000

    def consume(self, source: str, token_count: int) -> None:
        self.remaining -= len(source) + token_count * 20 + 100
        if self.remaining < 0:
            raise ParseError("shell analysis budget exhausted")


@dataclass(frozen=True)
class Part:
    """One literal, parameter, or dynamic part of a shell word."""

    kind: str
    value: str
    active: bool = False


@dataclass(frozen=True)
class EvaluatedWord:
    """A quote-removed word plus the expansions that remain active."""

    text: str | None
    active_globs: frozenset[int] = frozenset()
    active_tilde: bool = False
    active_brace: bool = False


@dataclass(frozen=True)
class Word:
    """A shell word without performing any shell expansion."""

    raw: str
    parts: tuple[Part, ...]
    plain: bool
    nested_sources: tuple[str, ...] = ()

    def evaluate(self, variables: Variables) -> EvaluatedWord:
        """Resolve only statically known parameter expansions."""
        chunks: list[str] = []
        active_globs: set[int] = set()
        active_tilde = False
        active_brace = False
        length = 0

        for part in self.parts:
            if part.kind in {"dynamic", "mutation"}:
                return EvaluatedWord(None)
            if part.kind == "parameter":
                value = variables.get(part.value)
                if value is None:
                    return EvaluatedWord(None)
            else:
                value = part.value

            if part.active:
                for offset, character in enumerate(value):
                    if character in "*?[":
                        active_globs.add(length + offset)
                    elif character in "{}":
                        active_brace = True
                if length == 0 and value.startswith("~"):
                    active_tilde = True

            chunks.append(value)
            length += len(value)

        return EvaluatedWord(
            "".join(chunks),
            frozenset(active_globs),
            active_tilde,
            active_brace,
        )


@dataclass
class Heredoc:
    """A here-document body and its expansion mode."""

    body: str = ""
    quoted_delimiter: bool = False
    strip_tabs: bool = False


@dataclass
class Redirect:
    """A redirection removed from a simple command's argument vector."""

    operator: str
    target: Word
    heredoc: Heredoc | None = None


@dataclass
class Token:
    """A lexical token with source offsets for function-body extraction."""

    kind: str
    start: int
    end: int
    text: str = ""
    word: Word | None = None
    redirect: Redirect | None = None
    nested_sources: tuple[str, ...] = ()


def _alternate_parameter_command(expression: str) -> str | None:
    """Return Bash's command-substitution-style parameter body, if present."""
    if expression[:1].isspace():
        return expression.lstrip()
    if expression.startswith("|") and expression[1:2].isspace():
        return expression[1:].lstrip()
    return None


def _ansi_c_quote(source: str, start: int) -> tuple[str, int]:
    mapping = {
        "a": "\a",
        "b": "\b",
        "e": "\x1b",
        "E": "\x1b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
        "\\": "\\",
        "'": "'",
        '"': '"',
        "?": "?",
    }
    result: list[str] = []
    index = start + 2

    while index < len(source):
        character = source[index]
        if character == "'":
            value = "".join(result)
            if "\0" in value:
                raise ParseError("NUL byte in ANSI-C quote")
            return value, index + 1
        if character != "\\":
            result.append(character)
            index += 1
            continue
        if index + 1 >= len(source):
            raise ParseError("unterminated ANSI-C quote")

        escaped = source[index + 1]
        if escaped == "\n":
            index += 2
            continue
        if escaped in mapping:
            result.append(mapping[escaped])
            index += 2
            continue
        if escaped in "01234567":
            end = index + 2
            while end < min(index + 5, len(source)) and source[end] in "01234567":
                end += 1
            result.append(chr(int(source[index + 1 : end], 8)))
            index = end
            continue
        if escaped == "x":
            match = re.match(r"[0-9A-Fa-f]{1,2}", source[index + 2 :])
            if match is None:
                result.append("\\x")
                index += 2
            else:
                result.append(chr(int(match.group(0), 16)))
                index += 2 + len(match.group(0))
            continue
        if escaped in {"u", "U"}:
            width = 4 if escaped == "u" else 8
            digits = source[index + 2 : index + 2 + width]
            if len(digits) != width or not all(c in "0123456789abcdefABCDEF" for c in digits):
                result.extend(("\\", escaped))
                index += 2
            else:
                try:
                    result.append(chr(int(digits, 16)))
                except ValueError as error:
                    raise ParseError("invalid ANSI-C character") from error
                index += 2 + width
            continue
        if escaped == "c" and index + 2 < len(source):
            result.append(chr(ord(source[index + 2].upper()) ^ 64))
            index += 3
            continue

        result.extend(("\\", escaped))
        index += 2

    raise ParseError("unterminated ANSI-C quote")


def _single_quote(source: str, start: int) -> tuple[str, int]:
    end = source.find("'", start + 1)
    if end == -1:
        raise ParseError("unterminated single quote")
    return source[start + 1 : end], end + 1


def _delimiter_double_quote(source: str, start: int) -> tuple[str, int]:
    result: list[str] = []
    index = start + 1
    while index < len(source):
        character = source[index]
        if character == '"':
            return "".join(result), index + 1
        if character == "\\":
            if index + 1 >= len(source):
                raise ParseError("trailing escape in here-document delimiter")
            escaped = source[index + 1]
            if escaped in {'"', "\\", "$", "`"}:
                result.append(escaped)
            else:
                result.extend(("\\", escaped))
            index += 2
            continue
        result.append(character)
        index += 1
    raise ParseError("unterminated here-document delimiter")


def _balanced_parentheses(source: str, opening: int) -> tuple[str, int]:
    depth = 1
    index = opening + 1
    quote: str | None = None
    at_boundary = True
    word: list[str] = []
    word_plain = True
    case_states: list[str] = []
    pending_heredocs: list[tuple[str, bool]] = []

    def flush_word() -> None:
        nonlocal word_plain
        if word and word_plain:
            value = "".join(word)
            if value == "case":
                case_states.append("await-in")
            elif value == "in" and case_states and case_states[-1] == "await-in":
                case_states[-1] = "pattern"
            elif value == "esac" and case_states:
                case_states.pop()
        word.clear()
        word_plain = True

    def consume_pending_heredocs(position: int) -> int:
        for delimiter, strip_tabs in pending_heredocs:
            while position <= len(source):
                line_end = source.find("\n", position)
                if line_end == -1:
                    line = source[position:]
                    next_position = len(source)
                else:
                    line = source[position:line_end]
                    next_position = line_end + 1
                comparable = line.lstrip("\t") if strip_tabs else line
                if comparable == delimiter:
                    position = next_position
                    break
                if line_end == -1:
                    raise ParseError("unterminated here-document in substitution")
                position = next_position
            else:
                raise ParseError("unterminated here-document in substitution")
        pending_heredocs.clear()
        return position

    while index < len(source):
        character = source[index]
        if quote is None and character == "#" and at_boundary:
            flush_word()
            newline = source.find("\n", index)
            if newline == -1:
                raise ParseError("unterminated substitution comment")
            index = newline
            continue
        if character == "\\" and quote != "'":
            if index + 1 >= len(source):
                raise ParseError("trailing escape in substitution")
            word_plain = False
            index += 2
            at_boundary = False
            continue
        if quote == "'":
            if character == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if character == '"':
                quote = None
                index += 1
                continue
            if source.startswith("$(", index) and not source.startswith("$((", index):
                _, index = _balanced_parentheses(source, index + 1)
                continue
            if character == "`":
                _, index = _backtick(source, index)
                continue
            index += 1
            continue
        if source.startswith("$'", index):
            word_plain = False
            _, index = _ansi_c_quote(source, index)
            at_boundary = False
            continue
        if character in {"'", '"'}:
            quote = character
            word_plain = False
            index += 1
            at_boundary = False
            continue
        if source.startswith("<<", index) and not source.startswith("<<<", index):
            flush_word()
            strip_tabs = source.startswith("<<-", index)
            delimiter_start = index + (3 if strip_tabs else 2)
            while delimiter_start < len(source) and source[delimiter_start] in " \t":
                delimiter_start += 1
            if delimiter_start >= len(source) or source[delimiter_start] == "\n":
                raise ParseError("here-document without a delimiter")
            delimiter_word, delimiter_end = _scan_word(
                source, delimiter_start, delimiter=True
            )
            delimiter = delimiter_word.evaluate({}).text
            if delimiter is None:
                raise ParseError("dynamic here-document delimiter")
            pending_heredocs.append((delimiter, strip_tabs))
            index = delimiter_end
            at_boundary = False
            continue
        if character == "(":
            flush_word()
            depth += 1
        elif character == ")":
            flush_word()
            if case_states and case_states[-1] == "pattern":
                case_states[-1] = "body"
            else:
                depth -= 1
                if depth == 0:
                    if pending_heredocs:
                        raise ParseError("here-document body missing before substitution end")
                    return source[opening + 1 : index], index + 1
        elif character == "\n":
            flush_word()
            index += 1
            at_boundary = True
            if pending_heredocs:
                index = consume_pending_heredocs(index)
            continue
        elif character.isspace() or character in ";&|<>":
            flush_word()
            if case_states and case_states[-1] == "body" and source.startswith(
                (";;", ";&"), index
            ):
                case_states[-1] = "pattern"
            at_boundary = True
            index += 1
            continue
        else:
            word.append(character)
            at_boundary = False
        index += 1

    raise ParseError("unterminated parenthesised expression")


def _arithmetic_expansion(source: str, start: int) -> tuple[str, int]:
    depth = 1
    index = start + 3
    content_start = index
    quote: str | None = None

    while index < len(source):
        character = source[index]
        if character == "\\" and quote != "'":
            if index + 1 >= len(source):
                raise ParseError("trailing escape in arithmetic expansion")
            index += 2
            continue
        if quote is not None:
            if character == quote:
                quote = None
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
            index += 1
            continue
        if source.startswith("$(", index) and not source.startswith("$((", index):
            _, index = _balanced_parentheses(source, index + 1)
            continue
        if source.startswith("((", index):
            depth += 1
            index += 2
            continue
        if source.startswith("))", index):
            depth -= 1
            if depth == 0:
                return source[content_start:index], index + 2
            index += 2
            continue
        index += 1

    raise ParseError("unterminated arithmetic expansion")


def _parameter_expansion(source: str, start: int) -> tuple[str, int]:
    depth = 1
    index = start + 2
    content_start = index
    quote: str | None = None
    at_boundary = True
    alternate_command = source[index : index + 1].isspace() or (
        source[index : index + 1] == "|"
        and source[index + 1 : index + 2].isspace()
    )

    while index < len(source):
        character = source[index]
        if character == "\\" and quote != "'":
            if index + 1 >= len(source):
                raise ParseError("trailing escape in parameter expansion")
            index += 2
            at_boundary = False
            continue
        if quote == "'":
            if character == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if character == '"':
                quote = None
                index += 1
                continue
            if source.startswith("$(", index) and not source.startswith("$((", index):
                _, index = _balanced_parentheses(source, index + 1)
                continue
            if character == "`":
                _, index = _backtick(source, index)
                continue
            index += 1
            continue
        if alternate_command and character == "#" and at_boundary:
            newline = source.find("\n", index)
            if newline == -1:
                raise ParseError("unterminated parameter-expansion comment")
            index = newline + 1
            at_boundary = True
            continue
        if source.startswith("$'", index):
            _, index = _ansi_c_quote(source, index)
            at_boundary = False
            continue
        if character in {"'", '"'}:
            quote = character
            index += 1
            at_boundary = False
            continue
        if source.startswith("$(", index) and not source.startswith("$((", index):
            _, index = _balanced_parentheses(source, index + 1)
            at_boundary = False
            continue
        if character == "`":
            _, index = _backtick(source, index)
            at_boundary = False
            continue
        if source.startswith("${", index):
            depth += 1
            index += 2
            at_boundary = False
            continue
        if alternate_command and character == "{":
            raise ParseError("ambiguous brace group in alternate substitution")
        if character == "}":
            depth -= 1
            if depth == 0:
                return source[content_start:index], index + 1
        at_boundary = character.isspace() or character in ";&|()"
        index += 1

    raise ParseError("unterminated parameter expansion")


def _backtick(source: str, start: int) -> tuple[str, int]:
    index = start + 1
    while index < len(source):
        if source[index] == "\\":
            if index + 1 >= len(source):
                raise ParseError("trailing escape in backtick substitution")
            index += 2
            continue
        if source[index] == "`":
            return source[start + 1 : index], index + 1
        index += 1
    raise ParseError("unterminated backtick substitution")


def _nested_expansions(source: str, *, comments: bool = False) -> tuple[str, ...]:
    """Collect executable substitutions from a data-only shell region."""
    nested: list[str] = []
    index = 0
    quote: str | None = None
    at_boundary = True

    while index < len(source):
        character = source[index]
        if comments and quote is None and character == "#" and at_boundary:
            newline = source.find("\n", index)
            index = len(source) if newline == -1 else newline + 1
            at_boundary = True
            continue
        if character == "\\" and quote != "'":
            if index + 1 >= len(source):
                raise ParseError("trailing escape")
            index += 2
            at_boundary = False
            continue
        if quote == "'":
            if character == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if character == '"':
                quote = None
                index += 1
                continue
            if source.startswith("$(", index) and not source.startswith("$((", index):
                body, index = _balanced_parentheses(source, index + 1)
                nested.append(body)
                continue
            if character == "`":
                body, index = _backtick(source, index)
                nested.append(body)
                continue
            index += 1
            continue
        if character in {"'", '"'}:
            quote = character
            index += 1
            continue
        if source.startswith("$(", index) and not source.startswith("$((", index):
            body, index = _balanced_parentheses(source, index + 1)
            nested.append(body)
            at_boundary = False
            continue
        if source.startswith(("<(", ">("), index):
            body, index = _balanced_parentheses(source, index + 1)
            nested.append(body)
            at_boundary = False
            continue
        if character == "`":
            body, index = _backtick(source, index)
            nested.append(body)
            at_boundary = False
            continue
        at_boundary = character.isspace() or character in ";&|()"
        index += 1

    if quote is not None:
        raise ParseError("unterminated quote")
    return tuple(nested)


def _double_quote(source: str, start: int) -> tuple[list[Part], list[str], int]:
    parts: list[Part] = []
    nested: list[str] = []
    literal: list[str] = []
    index = start + 1

    def flush() -> None:
        if literal:
            parts.append(Part("literal", "".join(literal)))
            literal.clear()

    while index < len(source):
        character = source[index]
        if character == '"':
            flush()
            return parts, nested, index + 1
        if character == "\\":
            if index + 1 >= len(source):
                raise ParseError("trailing escape in double quote")
            escaped = source[index + 1]
            if escaped == "\n":
                index += 2
                continue
            if escaped in {'"', "\\", "$", "`"}:
                literal.append(escaped)
            else:
                literal.extend(("\\", escaped))
            index += 2
            continue
        if source.startswith("$((", index):
            flush()
            body, index = _arithmetic_expansion(source, index)
            nested.extend(_nested_expansions(body))
            parts.append(Part("dynamic", ""))
            continue
        if source.startswith("$(", index):
            flush()
            body, index = _balanced_parentheses(source, index + 1)
            nested.append(body)
            parts.append(Part("dynamic", ""))
            continue
        if source.startswith("${", index):
            flush()
            expression, index = _parameter_expansion(source, index)
            nested.extend(_nested_expansions(expression))
            alternate = _alternate_parameter_command(expression)
            if alternate is not None:
                nested.append(alternate)
                parts.append(Part("dynamic", ""))
            elif PLAIN_PARAMETER.fullmatch(expression):
                parts.append(Part("parameter", expression))
            elif mutation := re.match(
                r"^([A-Za-z_][A-Za-z0-9_]*):?=", expression
            ):
                parts.append(Part("mutation", mutation.group(1)))
            else:
                parts.append(Part("dynamic", ""))
            continue
        if character == "$" and index + 1 < len(source) and (
            source[index + 1].isalpha() or source[index + 1] == "_"
        ):
            flush()
            end = index + 2
            while end < len(source) and (source[end].isalnum() or source[end] == "_"):
                end += 1
            parts.append(Part("parameter", source[index + 1 : end]))
            index = end
            continue
        if (
            character == "$"
            and index + 1 < len(source)
            and source[index + 1] in "@*#?-$!0123456789"
        ):
            flush()
            parts.append(Part("dynamic", ""))
            index += 2
            continue
        if character == "`":
            flush()
            body, index = _backtick(source, index)
            nested.append(body)
            parts.append(Part("dynamic", ""))
            continue
        literal.append(character)
        index += 1

    raise ParseError("unterminated double quote")


def _is_word_boundary(character: str) -> bool:
    return character.isspace() or character in ";&|()<>\0"


def _scan_word(source: str, start: int, *, delimiter: bool = False) -> tuple[Word, int]:
    parts: list[Part] = []
    nested: list[str] = []
    literal: list[str] = []
    plain = True
    index = start

    def flush(*, active: bool = True) -> None:
        if literal:
            parts.append(Part("literal", "".join(literal), active and not delimiter))
            literal.clear()

    while index < len(source):
        character = source[index]
        if not delimiter and source.startswith(("<(", ">("), index):
            plain = False
            flush()
            body, index = _balanced_parentheses(source, index + 1)
            nested.append(body)
            parts.append(Part("dynamic", ""))
            continue
        if not delimiter and _is_word_boundary(character):
            break
        if delimiter and _is_word_boundary(character):
            break
        if character == "\\":
            plain = False
            flush()
            if index + 1 >= len(source):
                raise ParseError("trailing escape")
            if source[index + 1] == "\n":
                index += 2
                continue
            parts.append(Part("literal", source[index + 1]))
            index += 2
            continue
        if character == "'":
            plain = False
            flush()
            value, index = _single_quote(source, index)
            parts.append(Part("literal", value))
            continue
        if delimiter and source.startswith("$'", index):
            plain = False
            flush()
            value, index = _ansi_c_quote(source, index)
            parts.append(Part("literal", value))
            continue
        if character == '"':
            plain = False
            flush()
            if delimiter:
                value, index = _delimiter_double_quote(source, index)
                parts.append(Part("literal", value))
            else:
                quoted_parts, quoted_nested, index = _double_quote(source, index)
                parts.extend(quoted_parts)
                nested.extend(quoted_nested)
            continue
        if not delimiter and source.startswith("$'", index):
            plain = False
            flush()
            value, index = _ansi_c_quote(source, index)
            parts.append(Part("literal", value))
            continue
        if not delimiter and source.startswith('$"', index):
            plain = False
            flush()
            quoted_parts, quoted_nested, index = _double_quote(source, index + 1)
            parts.extend(quoted_parts)
            nested.extend(quoted_nested)
            continue
        if not delimiter and source.startswith("$((", index):
            plain = False
            flush()
            body, index = _arithmetic_expansion(source, index)
            nested.extend(_nested_expansions(body))
            parts.append(Part("dynamic", ""))
            continue
        if not delimiter and source.startswith("$(", index):
            plain = False
            flush()
            body, index = _balanced_parentheses(source, index + 1)
            nested.append(body)
            parts.append(Part("dynamic", ""))
            continue
        if not delimiter and source.startswith("${", index):
            plain = False
            flush()
            expression, index = _parameter_expansion(source, index)
            nested.extend(_nested_expansions(expression))
            alternate = _alternate_parameter_command(expression)
            if alternate is not None:
                nested.append(alternate)
                parts.append(Part("dynamic", ""))
            elif PLAIN_PARAMETER.fullmatch(expression):
                parts.append(Part("parameter", expression, True))
            elif mutation := re.match(
                r"^([A-Za-z_][A-Za-z0-9_]*):?=", expression
            ):
                parts.append(Part("mutation", mutation.group(1)))
            else:
                parts.append(Part("dynamic", ""))
            continue
        if not delimiter and character == "$" and index + 1 < len(source) and (
            source[index + 1].isalpha() or source[index + 1] == "_"
        ):
            plain = False
            flush()
            end = index + 2
            while end < len(source) and (source[end].isalnum() or source[end] == "_"):
                end += 1
            parts.append(Part("parameter", source[index + 1 : end], True))
            index = end
            continue
        if (
            not delimiter
            and character == "$"
            and index + 1 < len(source)
            and source[index + 1] in "@*#?-$!0123456789"
        ):
            plain = False
            flush()
            parts.append(Part("dynamic", ""))
            index += 2
            continue
        if not delimiter and character == "`":
            plain = False
            flush()
            body, index = _backtick(source, index)
            nested.append(body)
            parts.append(Part("dynamic", ""))
            continue

        literal.append(character)
        index += 1

    flush()
    if index == start:
        raise ParseError("expected shell word")
    return Word(source[start:index], tuple(parts), plain, tuple(nested)), index


def _redirection_at(source: str, index: int) -> tuple[str, int] | None:
    start = index
    if source.startswith(("<(", ">("), index):
        return None
    if source[index].isdigit():
        while index < len(source) and source[index].isdigit():
            index += 1
        if index >= len(source) or source[index] not in "<>":
            return None
    elif source.startswith("&>", index):
        index += 1
    elif source[index] not in "<>":
        return None

    operators = ("<<<", "<<-", "&>>", ">>", ">|", "<>", "<&", ">&", "<<", "&>", ">", "<")
    for operator in operators:
        if source.startswith(operator, index):
            return source[start:index] + operator, index + len(operator)
    return None


def _consume_arithmetic_command(source: str, start: int) -> tuple[str, int]:
    depth = 1
    index = start + 2
    while index < len(source):
        if source[index] == "\\":
            if index + 1 >= len(source):
                raise ParseError("trailing escape in arithmetic command")
            index += 2
            continue
        if source.startswith("((", index):
            depth += 1
            index += 2
            continue
        if source.startswith("))", index):
            depth -= 1
            if depth == 0:
                return source[start + 2 : index], index + 2
            index += 2
            continue
        if source[index] in {"'", '"'}:
            quote = source[index]
            end = index + 1
            while end < len(source) and source[end] != quote:
                if source[end] == "\\" and quote == '"':
                    end += 1
                end += 1
            if end >= len(source):
                raise ParseError("unterminated arithmetic quote")
            index = end + 1
            continue
        index += 1
    raise ParseError("unterminated arithmetic command")


def _operator_at(source: str, index: int) -> tuple[str, int] | None:
    operators = (";;&", "&&", "||", ";;", ";&", "|&", ";", "&", "|", "(", ")")
    for operator in operators:
        if source.startswith(operator, index):
            return operator, index + len(operator)
    if source[index] in "{}":
        previous_boundary = index == 0 or _is_word_boundary(source[index - 1])
        next_boundary = index + 1 == len(source) or _is_word_boundary(source[index + 1])
        if previous_boundary and next_boundary:
            return source[index], index + 1
    return None


def _consume_heredocs(source: str, index: int, pending: list[tuple[Redirect, str]]) -> int:
    for redirect, delimiter in pending:
        body_lines: list[str] = []
        found = False
        while index <= len(source):
            end = source.find("\n", index)
            if end == -1:
                line = source[index:]
                next_index = len(source)
            else:
                line = source[index:end]
                next_index = end + 1
            comparable = line.lstrip("\t") if redirect.heredoc and redirect.heredoc.strip_tabs else line
            if comparable == delimiter:
                index = next_index
                found = True
                break
            body_line = line.lstrip("\t") if redirect.heredoc and redirect.heredoc.strip_tabs else line
            body_lines.append(body_line + ("\n" if end != -1 else ""))
            if end == -1:
                break
            index = next_index
        if not found:
            raise ParseError("unterminated here-document")
        if redirect.heredoc is None:
            raise ParseError("missing here-document metadata")
        redirect.heredoc.body = "".join(body_lines)
    return index


def _tokenise(source: str) -> list[Token]:
    tokens: list[Token] = []
    pending_heredocs: list[tuple[Redirect, str]] = []
    index = 0
    at_boundary = True

    while index < len(source):
        if len(tokens) > MAX_TOKENS:
            raise ParseError("too many shell tokens")
        character = source[index]
        if character in " \t\r":
            index += 1
            at_boundary = True
            continue
        if character == "\n":
            tokens.append(Token("operator", index, index + 1, "\n"))
            index += 1
            at_boundary = True
            if pending_heredocs:
                index = _consume_heredocs(source, index, pending_heredocs)
                pending_heredocs.clear()
            continue
        if character == "#" and at_boundary:
            end = source.find("\n", index)
            index = len(source) if end == -1 else end
            continue
        if character == "\0":
            raise ParseError("NUL byte in shell command")
        if source.startswith("((", index) and at_boundary:
            body, end = _consume_arithmetic_command(source, index)
            tokens.append(Token("data", index, end, nested_sources=_nested_expansions(body)))
            index = end
            at_boundary = False
            continue
        redirection_match = _redirection_at(source, index)
        if redirection_match is not None:
            operator, after_operator = redirection_match
            target_start = after_operator
            while target_start < len(source) and source[target_start] in " \t":
                target_start += 1
            if target_start >= len(source) or source[target_start] == "\n":
                raise ParseError("redirection without a target")
            redirection_kind = re.sub(r"^[0-9]+", "", operator)
            is_heredoc = redirection_kind in {"<<", "<<-"}
            target, end = _scan_word(source, target_start, delimiter=is_heredoc)
            redirect = Redirect(operator, target)
            if is_heredoc:
                evaluated = target.evaluate({})
                if evaluated.text is None:
                    raise ParseError("dynamic here-document delimiter")
                redirect.heredoc = Heredoc(
                    quoted_delimiter=not target.plain,
                    strip_tabs=operator.endswith("<<-"),
                )
                pending_heredocs.append((redirect, evaluated.text))
            tokens.append(Token("redirect", index, end, redirect=redirect))
            index = end
            at_boundary = False
            continue
        operator_match = _operator_at(source, index)
        if operator_match is not None:
            operator, end = operator_match
            tokens.append(Token("operator", index, end, operator))
            index = end
            at_boundary = True
            continue

        word, end = _scan_word(source, index)
        if not word.parts and re.fullmatch(r"(?:\\\n)+", word.raw):
            index = end
            at_boundary = True
            continue
        if end < len(source) and source[end] == "(" and word.raw.endswith("="):
            assignment_prefix = word.raw[:-1]
            if ASSIGNMENT_NAME.fullmatch(assignment_prefix):
                body, array_end = _balanced_parentheses(source, end)
                tokens.append(
                    Token(
                        "array",
                        index,
                        array_end,
                        text=assignment_prefix,
                        nested_sources=_nested_expansions(body, comments=True),
                    )
                )
                index = array_end
                at_boundary = False
                continue
        tokens.append(Token("word", index, end, word=word))
        index = end
        at_boundary = False

    if pending_heredocs:
        raise ParseError("here-document header without a body")
    return tokens


def _validate_structure(tokens: list[Token]) -> None:
    """Reject unbalanced shell groups and unfinished control structures."""
    groups: list[str] = []
    case_patterns: list[bool] = []
    controls: list[str] = []
    openers = {
        "case": "esac",
        "for": "done",
        "if": "fi",
        "select": "done",
        "until": "done",
        "while": "done",
    }
    index = 0

    while index < len(tokens):
        token = tokens[index]
        if token.kind == "operator":
            operator = token.text
            if operator in {"(", "{"}:
                groups.append(operator)
            elif operator == ")":
                if groups and groups[-1] == "(":
                    groups.pop()
                elif case_patterns and case_patterns[-1]:
                    case_patterns[-1] = False
                else:
                    raise ParseError("unmatched closing parenthesis")
            elif operator == "}":
                if not groups or groups[-1] != "{":
                    raise ParseError("unmatched closing brace")
                groups.pop()
            elif operator in {";;", ";&", ";;&"} and case_patterns:
                case_patterns[-1] = True
            index += 1
            continue

        end = index
        while end < len(tokens) and tokens[end].kind != "operator":
            end += 1
        initial_words = [
            candidate.word.evaluate({}).text
            for candidate in tokens[index:end]
            if candidate.kind == "word"
            and candidate.word is not None
            and candidate.word.plain
        ]
        first = initial_words[0] if initial_words else None
        if first == "!" and len(initial_words) > 1:
            first = initial_words[1]

        if first == "esac" and case_patterns:
            case_patterns.pop()
            if not controls or controls[-1] != "esac":
                raise ParseError("mismatched esac")
            controls.pop()
        elif case_patterns and case_patterns[-1]:
            pass
        elif first in openers:
            expected = openers[first]
            controls.append(expected)
            if first == "case":
                case_patterns.append(True)
        elif first in {"done", "esac", "fi"}:
            if not controls or controls[-1] != first:
                raise ParseError(f"mismatched {first}")
            controls.pop()
        index = end

    if groups or case_patterns or controls:
        raise ParseError("unfinished shell structure")


def _heredoc_substitutions(body: str) -> tuple[str, ...]:
    nested: list[str] = []
    index = 0
    while index < len(body):
        if body[index] == "\\":
            index += 2 if index + 1 < len(body) else 1
            continue
        if body.startswith("$(", index) and not body.startswith("$((", index):
            source, index = _balanced_parentheses(body, index + 1)
            nested.append(source)
            continue
        if body[index] == "`":
            source, index = _backtick(body, index)
            nested.append(source)
            continue
        index += 1
    return tuple(nested)


def _assignment(word: Word, variables: Variables) -> tuple[str, str | None] | None:
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)(\+?=)", word.raw)
    if match is None:
        return None
    name, operator = match.groups()
    raw_value = word.raw[match.end() :]
    if raw_value:
        value_word, end = _scan_word(raw_value, 0)
        if end != len(raw_value):
            return None
        evaluated = value_word.evaluate(variables)
        if evaluated.text is None:
            return name, None
        value = evaluated.text
    else:
        evaluated = EvaluatedWord("")
        value = ""
    if evaluated.active_tilde and value.startswith("~"):
        if value == "~" or value.startswith("~/"):
            actual_home = variables.get(ACTUAL_HOME_KEY)
            if actual_home is None:
                return name, None
            value = actual_home + value[1:]
    if operator == "+=":
        previous = variables.get(name)
        if previous is None:
            return name, None
        value = previous + value
    return name, value


def _basename(value: str) -> str:
    return posixpath.basename(value.rstrip("/")) or value


def _record_value(mapping: Variables | Functions, name: str, value: str | None) -> None:
    if name not in mapping:
        mapping[name] = value
    elif mapping[name] != value:
        mapping[name] = None


def _record_shell_value(variables: Variables, name: str, value: str | None) -> None:
    if OPAQUE_STATE_KEY in variables:
        variables[name] = None
    else:
        _record_value(variables, name, value)


def _record_function(
    functions: Functions, variables: Variables, name: str, body: str | None
) -> None:
    if OPAQUE_STATE_KEY in variables:
        functions[name] = None
    else:
        _record_value(functions, name, body)


def _has_active_field_splitting(word: Word, variables: Variables) -> bool:
    return any(
        part.kind == "parameter"
        and part.active
        and (
            variables.get(part.value) is None
            or any(
                character.isspace()
                for character in variables.get(part.value) or ""
            )
        )
        for part in word.parts
    )


def _brace_variants(value: str, *, limit: int = 32) -> tuple[str, ...] | None:
    """Expand a bounded, simple brace expression without invoking a shell."""
    pending = [value]
    expanded: list[str] = []
    while pending:
        candidate = pending.pop()
        opening = candidate.find("{")
        if opening == -1:
            expanded.append(candidate)
            if len(expanded) + len(pending) > limit:
                return None
            continue
        closing = candidate.find("}", opening + 1)
        if closing == -1 or "{" in candidate[opening + 1 : closing]:
            return None
        content = candidate[opening + 1 : closing]
        alternatives: list[str]
        if "," in content:
            alternatives = content.split(",")
            if any(
                not alternative
                or re.fullmatch(r"[A-Za-z0-9_.-]+", alternative) is None
                for alternative in alternatives
            ):
                return None
        else:
            numeric = re.fullmatch(r"(-?\d+)\.\.(-?\d+)(?:\.\.(-?\d+))?", content)
            alphabetic = re.fullmatch(
                r"([A-Za-z])\.\.([A-Za-z])(?:\.\.(-?\d+))?", content
            )
            if numeric is not None:
                start, stop = (int(numeric.group(1)), int(numeric.group(2)))
                step = int(numeric.group(3) or (1 if start <= stop else -1))
                if step == 0 or (stop - start) * step < 0:
                    return None
                boundary = stop + (1 if step > 0 else -1)
                alternatives = [str(number) for number in range(start, boundary, step)]
            elif alphabetic is not None:
                start, stop = (ord(alphabetic.group(1)), ord(alphabetic.group(2)))
                step = int(alphabetic.group(3) or (1 if start <= stop else -1))
                if step == 0 or (stop - start) * step < 0:
                    return None
                boundary = stop + (1 if step > 0 else -1)
                alternatives = [chr(codepoint) for codepoint in range(start, boundary, step)]
            else:
                return None
        if len(alternatives) + len(expanded) + len(pending) > limit:
            return None
        prefix = candidate[:opening]
        suffix = candidate[closing + 1 :]
        pending.extend(prefix + alternative + suffix for alternative in alternatives)
    return tuple(expanded)


def _protected_path(word: Word, variables: Variables, cwd: str | None) -> str | None:
    evaluated = word.evaluate(variables)
    if evaluated.text is None:
        return GENERIC_REASON
    value = evaluated.text
    if evaluated.active_brace:
        variants = _brace_variants(value)
        if variants is None:
            return GENERIC_REASON
        for variant in variants:
            variant_word = Word(
                variant,
                (Part("literal", variant, True),),
                True,
            )
            reason = _protected_path(variant_word, variables, cwd)
            if reason is not None:
                return reason
        return None
    if evaluated.active_tilde:
        if value == "~" or value.startswith("~/"):
            actual_home = variables.get(ACTUAL_HOME_KEY)
            if actual_home is None:
                return GENERIC_REASON
            value = actual_home + value[1:]
        else:
            return GENERIC_REASON

    first_glob = min(evaluated.active_globs) if evaluated.active_globs else None
    if first_glob is not None and ".." in value[first_glob:].split("/"):
        return GENERIC_REASON
    path_for_check = value if first_glob is None else value[:first_glob]
    if first_glob is not None:
        if "/" in path_for_check:
            path_for_check = path_for_check.rsplit("/", 1)[0] or "/"
        else:
            path_for_check = "."
    if not path_for_check.startswith("/"):
        if cwd is None:
            return GENERIC_REASON
        path_for_check = posixpath.join(cwd, path_for_check)
    path_for_check = posixpath.normpath(re.sub(r"/+", "/", path_for_check))

    actual_home = variables.get(ACTUAL_HOME_KEY)
    if actual_home is None:
        return GENERIC_REASON
    home = posixpath.normpath(re.sub(r"/+", "/", actual_home))
    folded = path_for_check.casefold()
    folded_home = home.casefold()
    if folded == "/":
        return ROOT_REASON
    if folded == folded_home:
        return HOME_REASON
    if folded_home != "/" and folded.startswith(folded_home.rstrip("/") + "/"):
        return None
    if folded == "/users":
        return USERS_REASON
    if folded.startswith("/users/"):
        relative = folded.removeprefix("/users/").strip("/")
        if relative and "/" not in relative:
            return HOME_REASON
    if folded == "/home":
        return USERS_REASON
    if folded.startswith("/home/"):
        relative = folded.removeprefix("/home/").strip("/")
        if relative:
            return HOME_REASON
    if folded == "/system" or folded.startswith("/system/"):
        return SYSTEM_REASON
    if any(
        folded == root.casefold() or folded.startswith(root.casefold() + "/")
        for root in SYSTEM_TREES
    ):
        return SYSTEM_REASON
    if any(folded == root.casefold() for root in SYSTEM_ROOTS):
        return SYSTEM_REASON
    if folded == "/volumes" or (
        folded.startswith("/volumes/")
        and "/" not in folded.removeprefix("/volumes/").strip("/")
    ):
        return DISK_REASON
    return None


def _rm_reason(arguments: list[Word], variables: Variables, cwd: str | None) -> str | None:
    recursive = False
    ambiguous_option = False
    operands: list[Word] = []
    options_ended = False
    safe_short_options = frozenset("dfiIPRrvWx")
    safe_long_options = {
        "--dir",
        "--force",
        "--help",
        "--no-preserve-root",
        "--one-file-system",
        "--preserve-root",
        "--recursive",
        "--verbose",
        "--version",
    }

    for argument in arguments:
        evaluated = argument.evaluate(variables)
        if evaluated.text is None:
            if not options_ended:
                return GENERIC_REASON
            operands.append(argument)
            continue
        if _has_active_field_splitting(argument, variables):
            return GENERIC_REASON
        value = evaluated.text
        if not options_ended and value == "--":
            options_ended = True
            continue
        if not options_ended and value.startswith("--"):
            option_name = value.split("=", 1)[0]
            if option_name == "--recursive":
                recursive = True
            elif option_name == "--interactive":
                pass
            elif option_name not in safe_long_options:
                ambiguous_option = True
            continue
        if not options_ended and value.startswith("-") and value != "-":
            flags = value[1:]
            if "r" in flags or "R" in flags:
                recursive = True
            if any(flag not in safe_short_options for flag in flags):
                ambiguous_option = True
            continue
        operands.append(argument)

    unknown_argument = any(
        operand.evaluate(variables).text is None for operand in operands
    )
    protected_reasons = [
        reason
        for operand in operands
        if operand.evaluate(variables).text is not None
        and (reason := _protected_path(operand, variables, cwd)) is not None
    ]
    if protected_reasons and (recursive or ambiguous_option):
        return protected_reasons[0]
    if protected_reasons and unknown_argument:
        return GENERIC_REASON
    if recursive and unknown_argument:
        return GENERIC_REASON
    return None


def _wrapper_command(
    executable: str,
    arguments: list[Word],
    variables: Variables,
) -> tuple[list[Word] | None, str | None]:
    index = 0

    def value_at(position: int) -> str | None:
        return arguments[position].evaluate(variables).text

    def working_directory_at(position: int) -> str | None:
        word = arguments[position]
        evaluated = word.evaluate(variables)
        if (
            evaluated.text is None
            or evaluated.active_globs
            or evaluated.active_brace
            or _has_active_field_splitting(word, variables)
        ):
            return None
        value = evaluated.text
        if evaluated.active_tilde:
            if value != "~" and not value.startswith("~/"):
                return None
            actual_home = variables.get(ACTUAL_HOME_KEY)
            if actual_home is None:
                return None
            value = actual_home + value[1:]
        return value

    def set_working_directory(value: str) -> None:
        current = variables.get("PWD")
        if value.startswith("/"):
            variables["PWD"] = posixpath.normpath(value)
        elif current is None:
            variables["PWD"] = None
        else:
            variables["PWD"] = posixpath.normpath(posixpath.join(current, value))

    if executable == "sudo":
        options_with_values = {
            "-a", "-C", "-D", "-g", "-h", "-p", "-R", "-r", "-T", "-t", "-U", "-u"
        }
        no_value = {"-A", "-b", "-E", "-H", "-K", "-k", "-n", "-P", "-S", "-V", "-v"}
        long_with_values = {
            "--chdir", "--group", "--host", "--prompt", "--role", "--type", "--user"
        }
        long_without_values = {
            "--askpass", "--background", "--edit", "--help", "--login",
            "--non-interactive", "--preserve-env", "--remove-timestamp",
            "--reset-timestamp", "--stdin", "--validate", "--version",
        }
        while index < len(arguments):
            value = value_at(index)
            if value is None:
                return None, GENERIC_REASON
            if value == "--":
                index += 1
                break
            if not value.startswith("-") or value == "-":
                break
            option = value.split("=", 1)[0]
            if option.startswith("--"):
                if option in long_with_values:
                    if "=" in value:
                        option_value = value.split("=", 1)[1]
                        index += 1
                    elif index + 1 < len(arguments):
                        option_value = (
                            working_directory_at(index + 1)
                            if option == "--chdir"
                            else value_at(index + 1)
                        )
                        if option_value is None:
                            return None, GENERIC_REASON
                        index += 2
                    else:
                        return None, GENERIC_REASON
                    if option == "--chdir":
                        set_working_directory(option_value)
                elif option in long_without_values and (
                    "=" not in value or option == "--preserve-env"
                ):
                    index += 1
                else:
                    return None, GENERIC_REASON
            elif option in options_with_values:
                if index + 1 >= len(arguments):
                    return None, GENERIC_REASON
                option_value = (
                    working_directory_at(index + 1)
                    if option == "-D"
                    else value_at(index + 1)
                )
                if option_value is None:
                    return None, GENERIC_REASON
                if option == "-D":
                    set_working_directory(option_value)
                index += 2
            elif len(value) > 2 and value[:2] in options_with_values:
                if value[:2] == "-D":
                    set_working_directory(value[2:])
                index += 1
            elif option in no_value:
                index += 1
            else:
                return None, GENERIC_REASON
        while index < len(arguments):
            value = value_at(index)
            if value is None:
                return None, GENERIC_REASON
            if "=" not in value or not ASSIGNMENT_NAME.fullmatch(value.split("=", 1)[0]):
                break
            index += 1
    elif executable == "env":
        while index < len(arguments):
            value = value_at(index)
            if value is None:
                return None, GENERIC_REASON
            if value == "--":
                index += 1
                break
            if "=" in value and ASSIGNMENT_NAME.fullmatch(value.split("=", 1)[0]):
                index += 1
                continue
            if value in {"-i", "--ignore-environment", "-0", "--null"}:
                index += 1
                continue
            if value in {"-S", "--split-string"} or value.startswith("--split-string="):
                return None, GENERIC_REASON
            if value in {"-u", "--unset"}:
                index += 2
                continue
            if value in {"-C", "--chdir"}:
                if index + 1 >= len(arguments):
                    return None, GENERIC_REASON
                option_value = working_directory_at(index + 1)
                if option_value is None:
                    return None, GENERIC_REASON
                set_working_directory(option_value)
                index += 2
                continue
            if value.startswith("--chdir="):
                set_working_directory(value.split("=", 1)[1])
                index += 1
                continue
            if value.startswith("--unset="):
                index += 1
                continue
            if value.startswith("-"):
                return None, GENERIC_REASON
            break
    elif executable == "doas":
        while index < len(arguments):
            value = value_at(index)
            if value is None:
                return None, GENERIC_REASON
            if value == "--":
                index += 1
                break
            if value in {"-a", "-C", "-u"}:
                index += 2
                continue
            if value in {"-L", "-n", "-s"}:
                index += 1
                continue
            if value.startswith("-") and value != "-":
                return None, GENERIC_REASON
            break
    elif executable == "chroot":
        options_with_values = {"-g", "-G", "-u", "--groups", "--userspec"}
        while index < len(arguments):
            value = value_at(index)
            if value is None:
                return None, GENERIC_REASON
            if value == "--":
                index += 1
                break
            option = value.split("=", 1)[0]
            if option == "--skip-chdir":
                return None, GENERIC_REASON
            if option in options_with_values:
                index += 1 if "=" in value else 2
                continue
            if value.startswith("-") and value != "-":
                return None, GENERIC_REASON
            break
        if index >= len(arguments):
            return None, GENERIC_REASON
        root_word = arguments[index]
        root = root_word.evaluate(variables)
        if (
            root.text is None
            or root.active_globs
            or root.active_brace
            or _has_active_field_splitting(root_word, variables)
        ):
            return None, GENERIC_REASON
        index += 1
        variables["PWD"] = "/"
    elif executable in {"command", "builtin"}:
        while index < len(arguments):
            value = value_at(index)
            if value == "--":
                index += 1
                break
            if value is not None and value.startswith("-") and value != "-":
                if not set(value[1:]) <= set("pVv"):
                    return None, GENERIC_REASON
                index += 1
                continue
            break
    elif executable == "exec":
        while index < len(arguments):
            value = value_at(index)
            if value == "--":
                index += 1
                break
            if value == "-a":
                index += 2
                continue
            if value in {"-c", "-l"}:
                index += 1
                continue
            if value is not None and value.startswith("-") and value != "-":
                return None, GENERIC_REASON
            break
    elif executable == "nohup":
        if index < len(arguments) and value_at(index) == "--":
            index += 1
    elif executable == "time":
        while index < len(arguments):
            value = value_at(index)
            if value == "--":
                index += 1
                break
            if value in {"-f", "--format", "-o", "--output"}:
                index += 2
                continue
            if value is not None and value.startswith(("--format=", "--output=")):
                index += 1
                continue
            if value is not None and value.startswith("-") and value != "-":
                index += 1
                continue
            break
    elif executable == "nice":
        while index < len(arguments):
            value = value_at(index)
            if value == "--":
                index += 1
                break
            if value in {"-n", "--adjustment"}:
                index += 2
                continue
            if value is not None and (
                value.startswith("--adjustment=") or re.fullmatch(r"-[0-9]+", value)
            ):
                index += 1
                continue
            break
    elif executable in {"-", "noglob", "nocorrect"}:
        pass
    elif executable == "coproc":
        if not arguments:
            return None, GENERIC_REASON
    elif executable == "xargs":
        options_with_values = {
            "-a", "--arg-file", "-d", "--delimiter", "-E", "--eof", "-I",
            "--replace", "-L", "--max-lines", "-n", "--max-args", "-P",
            "--max-procs", "-s", "--max-chars",
        }
        while index < len(arguments):
            value = value_at(index)
            if value is None:
                return None, GENERIC_REASON
            if value == "--":
                index += 1
                break
            option = value.split("=", 1)[0]
            if option in options_with_values:
                index += 1 if "=" in value else 2
                continue
            if value.startswith("-") and value != "-":
                index += 1
                continue
            break
        if index >= len(arguments):
            return None, None
        opaque_input = Word("<xargs-input>", (Part("dynamic", ""),), False)
        return [*arguments[index:], opaque_input], None
    else:
        return None, None

    if index >= len(arguments):
        return None, GENERIC_REASON
    return arguments[index:], None


def _shell_script_argument(
    arguments: list[Word], variables: Variables
) -> tuple[str | None, bool]:
    index = 0
    options_with_values = {"-O", "+O", "-o", "+o", "--init-file", "--rcfile"}
    while index < len(arguments):
        value = arguments[index].evaluate(variables).text
        if value is None:
            return None, True
        if value == "--":
            return None, False
        option_name = value.split("=", 1)[0]
        if option_name in options_with_values:
            if "=" in value:
                index += 1
            elif index + 1 >= len(arguments):
                return None, True
            else:
                index += 2
            continue
        if value.startswith("-") and value != "-":
            if "c" in value[1:]:
                if index + 1 >= len(arguments):
                    return None, True
                return arguments[index + 1].evaluate(variables).text, True
            index += 1
            continue
        return None, False
    return None, False


def _disk_reason(
    executable: str, arguments: list[Word], variables: Variables
) -> str | None:
    lowered = executable.lower()
    if lowered in FORMATTERS or lowered.startswith(FORMATTER_PREFIXES):
        return DISK_REASON
    values = [argument.evaluate(variables).text for argument in arguments]
    if lowered == "diskutil":
        if any(value is None for value in values):
            return GENERIC_REASON
        static = [value.lower() for value in values if value is not None]
        while static and static[0] in {"quiet", "plist", "-plist"}:
            static.pop(0)
        for action in DISKUTIL_ACTIONS:
            if tuple(static[: len(action)]) == action:
                return DISK_REASON
    if lowered == "gpt":
        static_values = [value.casefold() for value in values if value is not None]
        if "destroy" in static_values:
            return DISK_REASON
    if lowered == "dd":
        if any(value is None for value in values):
            return GENERIC_REASON
        for value in values:
            if value is not None and re.match(
                r"^of=/dev/(?:r?disk|sd|nvme|vd|xvd)", value
            ):
                return DISK_REASON
    if lowered == "tee":
        for argument in arguments:
            reason = _device_target_reason(argument, variables)
            if reason is not None:
                return reason
    if lowered in {"cp", "install", "mv"} and values:
        if values[-1] is None:
            return GENERIC_REASON
        reason = _device_target_reason(arguments[-1], variables)
        if reason is not None:
            return reason
    return None


def _redirection_kind(operator: str) -> str:
    return re.sub(r"^[0-9]+", "", operator)


def _device_path(value: str | None) -> bool:
    return bool(
        value
        and re.match(
            r"^/dev/(?:r?disk(?:[0-9]|$)|sd(?:[a-z0-9]|$)|nvme(?:[0-9]|$)|"
            r"vd(?:[a-z0-9]|$)|xvd(?:[a-z0-9]|$)|md(?:[0-9]|$)|mapper/[^/]+)",
            value.casefold(),
        )
    )


def _device_target_reason(word: Word, variables: Variables) -> str | None:
    evaluated = word.evaluate(variables)
    if evaluated.text is None:
        return GENERIC_REASON
    if evaluated.active_brace:
        variants = _brace_variants(evaluated.text)
        if variants is None:
            return (
                DISK_REASON
                if evaluated.text.casefold().startswith("/dev/")
                else GENERIC_REASON
            )
        reasons = (
            _device_target_reason(
                Word(variant, (Part("literal", variant, True),), True),
                variables,
            )
            for variant in variants
        )
        return next((reason for reason in reasons if reason is not None), None)

    value = evaluated.text
    if not value.startswith("/"):
        cwd = variables.get("PWD")
        if cwd is not None:
            value = posixpath.normpath(posixpath.join(cwd, value))
    if _device_path(value):
        return DISK_REASON
    if not evaluated.active_globs:
        return None
    prefix = value[: min(evaluated.active_globs)].casefold()
    device_prefixes = (
        "/dev/disk",
        "/dev/rdisk",
        "/dev/sd",
        "/dev/nvme",
        "/dev/vd",
        "/dev/xvd",
        "/dev/md",
        "/dev/mapper/",
    )
    matches_device = any(
        candidate.startswith(prefix) or prefix.startswith(candidate)
        for candidate in device_prefixes
    )
    return DISK_REASON if matches_device else None


def _shell_has_script_operand(arguments: list[Word], variables: Variables) -> bool:
    index = 0
    options_with_values = {"-O", "+O", "-o", "+o", "--init-file", "--rcfile"}
    while index < len(arguments):
        value = arguments[index].evaluate(variables).text
        if value is None:
            return True
        if value == "--":
            return index + 1 < len(arguments)
        option = value.split("=", 1)[0]
        if option in options_with_values and "=" not in value:
            index += 2
        elif value.startswith(("-", "+")) and value not in {"-", "+"}:
            index += 1
        else:
            return True
    return False


def _find_reason(
    executable: str,
    arguments: list[Word],
    variables: Variables,
    functions: Functions,
    cwd: str | None,
    depth: int,
    budget: AnalysisBudget,
) -> str | None:
    if executable != "find":
        return None
    values = [argument.evaluate(variables).text for argument in arguments]
    index = 0
    while index < len(values):
        value = values[index]
        if value in {"-H", "-L", "-P"} or (
            value is not None and value.startswith("-O")
        ):
            index += 1
            continue
        if value == "-D":
            index += 2
            continue
        break
    protected_reason: str | None = None
    for argument, value in zip(arguments[index:], values[index:], strict=True):
        if value is None:
            break
        if value.startswith("-") or value in {"!", "("}:
            break
        reason = _protected_path(argument, variables, cwd)
        if reason is not None:
            protected_reason = reason
            break
    if "-delete" in values:
        return protected_reason or (GENERIC_REASON if any(v is None for v in values) else None)

    action_markers = {"-exec", "-execdir", "-ok", "-okdir"}
    for position, value in enumerate(values):
        if value not in action_markers:
            continue
        action: list[str] = []
        action_end = len(values)
        for action_position, action_value in enumerate(
            values[position + 1 :], start=position + 1
        ):
            if action_value in {";", "+"}:
                action_end = action_position
                break
            if action_value is None:
                return GENERIC_REASON
            action.append(action_value)
        if not action:
            return GENERIC_REASON
        recursive_rm = any(_basename(item).casefold() == "rm" for item in action) and any(
            item.startswith("-") and ("r" in item[1:] or "R" in item[1:])
            for item in action
        )
        if recursive_rm:
            return protected_reason or GENERIC_REASON
        action_source = " ".join(
            argument.raw for argument in arguments[position + 1 : action_end]
        )
        reason = _analyse_script(
            action_source,
            variables.copy(),
            functions.copy(),
            cwd,
            depth + 1,
            budget,
        )
        if reason is not None:
            return reason
    return None


def _analyse_segment(
    segment: list[Token],
    variables: Variables,
    functions: Functions,
    cwd: str | None,
    depth: int,
    budget: AnalysisBudget,
) -> str | None:
    for token in segment:
        nested = token.nested_sources
        if token.word is not None:
            nested += token.word.nested_sources
            for part in token.word.parts:
                if part.kind == "mutation":
                    variables[part.value] = None
        if token.redirect is not None:
            nested += token.redirect.target.nested_sources
            for part in token.redirect.target.parts:
                if part.kind == "mutation":
                    variables[part.value] = None
            redirect_kind = _redirection_kind(token.redirect.operator)
            redirect_aliases = {
                f"@global-alias:{token.redirect.operator.casefold()}",
                f"@global-alias:{redirect_kind.casefold()}",
            }
            target_value = token.redirect.target.evaluate(variables).text
            if token.redirect.target.plain and target_value is not None:
                redirect_aliases.add(f"@global-alias:{target_value.casefold()}")
            if any(alias in functions for alias in redirect_aliases):
                return GENERIC_REASON
            if ">" in redirect_kind:
                reason = _device_target_reason(token.redirect.target, variables)
                if reason is not None:
                    return reason
            heredoc = token.redirect.heredoc
            if heredoc is not None and not heredoc.quoted_delimiter:
                nested += _heredoc_substitutions(heredoc.body)
        for source in nested:
            reason = _analyse_script(
                source,
                variables.copy(),
                functions.copy(),
                variables.get("PWD"),
                depth + 1,
                budget,
            )
            if reason is not None:
                return reason

    words = [
        token.word
        for token in segment
        if token.kind == "word" and token.word is not None
    ]
    if not words:
        return None

    for position, word in enumerate(words):
        value = word.evaluate(variables).text
        alias_key = f"@global-alias:{value.casefold()}" if value is not None else ""
        if not word.plain or alias_key not in functions:
            continue
        body = functions[alias_key]
        if body is None:
            return GENERIC_REASON
        expanded_words = [candidate.raw for candidate in words]
        expanded_words[position] = body
        return _analyse_script(
            " ".join(expanded_words),
            variables,
            functions,
            variables.get("PWD"),
            depth + 1,
            budget,
        )

    while words:
        value = words[0].evaluate(variables).text
        if words[0].plain and value in {
            "!", "do", "elif", "else", "if", "then", "until", "while"
        }:
            words.pop(0)
            continue
        break
    if not words:
        return None

    first = words[0].evaluate(variables).text
    if words[0].plain and first in {"case", "for", "select"}:
        return None

    local_variables = variables.copy()
    index = 0
    assignments: list[tuple[str, str | None]] = []
    while index < len(words):
        assignment = _assignment(words[index], local_variables)
        if assignment is None:
            break
        name, value = assignment
        assignments.append(assignment)
        index += 1

    if index == len(words):
        for name, value in assignments:
            _record_shell_value(variables, name, value)
        return None
    words = words[index:]

    executable_word = words[0].evaluate(local_variables)
    executable_value = executable_word.text
    if (
        executable_value is None
        or executable_word.active_globs
        or executable_word.active_brace
        or _has_active_field_splitting(words[0], local_variables)
    ):
        return GENERIC_REASON
    executable = _basename(executable_value).casefold()

    if executable in {"export", "readonly", "typeset", "declare", "local"}:
        for word in words[1:]:
            assignment = _assignment(word, local_variables)
            if assignment is not None:
                _record_shell_value(variables, assignment[0], assignment[1])
        return None
    if executable == "unset":
        for word in words[1:]:
            name = word.evaluate(local_variables).text
            if name is not None:
                variables[name] = None
        return None
    if executable == "alias":
        global_alias = False
        for word in words[1:]:
            value = word.evaluate(local_variables).text
            if value is None:
                return GENERIC_REASON
            if value == "--":
                continue
            if value.startswith("-") and "=" not in value:
                if "g" in value[1:]:
                    global_alias = True
                continue
            if "=" not in value:
                continue
            name, body = value.split("=", 1)
            if not name:
                return GENERIC_REASON
            kind = "@global-alias" if global_alias else "@alias"
            _record_function(
                functions, variables, f"{kind}:{name.casefold()}", body
            )
        return None
    if executable == "unalias":
        for word in words[1:]:
            name = word.evaluate(local_variables).text
            if name is not None:
                functions[f"@alias:{name.casefold()}"] = None
                functions[f"@global-alias:{name.casefold()}"] = None
        return None

    command_words = words
    for _ in range(8):
        unwrapped, wrapper_reason = _wrapper_command(
            executable, command_words[1:], local_variables
        )
        if wrapper_reason is not None:
            return wrapper_reason
        if unwrapped is None:
            break
        command_words = unwrapped
        executable_value = command_words[0].evaluate(local_variables).text
        if executable_value is None:
            return GENERIC_REASON
        executable = _basename(executable_value).casefold()
    else:
        return GENERIC_REASON

    arguments = command_words[1:]
    alias_key = f"@alias:{executable}"
    if alias_key in functions:
        body = functions[alias_key]
        values = [argument.evaluate(local_variables).text for argument in arguments]
        if body is None or any(value is None for value in values):
            return GENERIC_REASON
        script = body
        if values:
            script += " " + shlex.join(value for value in values if value is not None)
        return _analyse_script(
            script, variables, functions, variables.get("PWD"), depth + 1, budget
        )
    if executable in functions:
        body = functions[executable]
        if body is None:
            return GENERIC_REASON
        return _analyse_script(
            body, variables, functions, variables.get("PWD"), depth + 1, budget
        )
    if executable in SHELLS:
        script, has_c = _shell_script_argument(arguments, local_variables)
        if has_c:
            if script is None:
                return GENERIC_REASON
            return _analyse_script(
                script,
                local_variables.copy(),
                functions.copy(),
                local_variables.get("PWD"),
                depth + 1,
                budget,
            )
        if _shell_has_script_operand(arguments, local_variables):
            return GENERIC_REASON
        stdin_sources: list[str] = []
        for token in segment:
            redirect = token.redirect
            if redirect is None:
                continue
            kind = _redirection_kind(redirect.operator)
            if redirect.heredoc is not None:
                stdin_sources.append(redirect.heredoc.body)
            elif kind == "<<<":
                source = redirect.target.evaluate(local_variables).text
                if source is None:
                    return GENERIC_REASON
                stdin_sources.append(source)
            elif "<" in kind:
                return GENERIC_REASON
        if not stdin_sources:
            return GENERIC_REASON
        for source in stdin_sources:
            reason = _analyse_script(
                source,
                local_variables.copy(),
                functions.copy(),
                local_variables.get("PWD"),
                depth + 1,
                budget,
            )
            if reason is not None:
                return reason
        return None
    if executable == "eval":
        values = [argument.evaluate(local_variables).text for argument in arguments]
        if any(value is None for value in values):
            return GENERIC_REASON
        script = " ".join(value for value in values if value is not None)
        return _analyse_script(
            script, variables, functions, variables.get("PWD"), depth + 1, budget
        )
    if executable in {".", "source"}:
        return GENERIC_REASON
    if executable == "trap":
        if not arguments:
            return None
        action_index = 1 if arguments[0].evaluate(local_variables).text == "--" else 0
        if action_index >= len(arguments):
            return None
        action = arguments[action_index].evaluate(local_variables).text
        if action is None:
            return GENERIC_REASON
        if action in {"", "-"} or action.startswith("-"):
            return None
        return _analyse_script(
            action,
            variables.copy(),
            functions.copy(),
            variables.get("PWD"),
            depth + 1,
            budget,
        )
    if executable == "cd":
        values = [argument.evaluate(local_variables).text for argument in arguments]
        target = next(
            (value for value in values if value is not None and not value.startswith("-")),
            local_variables.get("HOME"),
        )
        current = local_variables.get("PWD")
        if target is None or target == "-" or (not target.startswith("/") and current is None):
            variables["PWD"] = None
        else:
            destination = target if target.startswith("/") else posixpath.join(current or "", target)
            _record_shell_value(variables, "PWD", posixpath.normpath(destination))
        return None
    if executable in {"pushd", "popd"}:
        variables["PWD"] = None
        return None
    if executable in {"read", "readarray", "mapfile"}:
        for word in arguments:
            value = word.evaluate(local_variables).text
            if value is not None and ASSIGNMENT_NAME.fullmatch(value):
                variables[value] = None
        return None
    if executable == "printf":
        values = [argument.evaluate(local_variables).text for argument in arguments]
        if "-v" in values:
            position = values.index("-v")
            if position + 1 >= len(values) or values[position + 1] is None:
                return GENERIC_REASON
            variables[values[position + 1] or ""] = None
        return None
    if executable == "rm":
        reason = _rm_reason(arguments, local_variables, local_variables.get("PWD"))
        if reason is not None:
            return reason

    reason = _disk_reason(executable, arguments, local_variables)
    if reason is not None:
        return reason
    reason = _find_reason(
        executable,
        arguments,
        local_variables,
        functions,
        local_variables.get("PWD"),
        depth,
        budget,
    )
    if reason is not None:
        return reason

    return None


def _analyse_nested_tokens(
    segment: list[Token],
    variables: Variables,
    functions: Functions,
    cwd: str | None,
    depth: int,
    budget: AnalysisBudget,
) -> str | None:
    for token in segment:
        nested = token.nested_sources
        if token.word is not None:
            nested += token.word.nested_sources
        if token.redirect is not None:
            nested += token.redirect.target.nested_sources
        for source in nested:
            reason = _analyse_script(
                source,
                variables.copy(),
                functions.copy(),
                variables.get("PWD"),
                depth + 1,
                budget,
            )
            if reason is not None:
                return reason
    return None


def _plain_function_word(tokens: list[Token], position: int) -> str | None:
    token = tokens[position]
    if token.kind != "word" or token.word is None or not token.word.plain:
        return None
    return token.word.evaluate({}).text


def _function_at(
    tokens: list[Token], index: int, source: str
) -> tuple[str, str, int] | None:
    name: str | None = None
    brace_index: int | None = None
    cursor = index
    if _plain_function_word(tokens, index) == "function":
        cursor += 1
        if cursor < len(tokens):
            name = _plain_function_word(tokens, cursor)
        cursor += 1
        if cursor + 1 < len(tokens) and (
            tokens[cursor].text == "(" and tokens[cursor + 1].text == ")"
        ):
            cursor += 2
    else:
        name = _plain_function_word(tokens, index)
        cursor += 1
        if cursor + 1 >= len(tokens) or not (
            tokens[cursor].text == "(" and tokens[cursor + 1].text == ")"
        ):
            return None
        cursor += 2
    while cursor < len(tokens) and tokens[cursor].text == "\n":
        cursor += 1
    if (
        name is not None
        and ASSIGNMENT_NAME.fullmatch(name)
        and cursor < len(tokens)
        and tokens[cursor].text == "{"
    ):
        brace_index = cursor
    if name is None or brace_index is None:
        return None

    brace_depth = 1
    end_index = brace_index + 1
    while end_index < len(tokens):
        if tokens[end_index].kind == "operator":
            if tokens[end_index].text == "{":
                brace_depth += 1
            elif tokens[end_index].text == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    body = source[tokens[brace_index].end : tokens[end_index].start]
                    return name, body, end_index + 1
        end_index += 1
    raise ParseError("unterminated function definition")


def _analyse_script(
    source: str,
    variables: Variables,
    functions: Functions,
    cwd: str | None,
    depth: int,
    budget: AnalysisBudget | None = None,
) -> str | None:
    if depth > MAX_DEPTH or len(source) > MAX_SOURCE_LENGTH:
        return GENERIC_REASON
    if budget is None:
        budget = AnalysisBudget()
    tokens = _tokenise(source)
    _validate_structure(tokens)
    budget.consume(source, len(tokens))
    if any(
        (token.kind == "operator" and token.text not in {";", "\n"})
        or (
            token.kind == "word"
            and token.word is not None
            and token.word.plain
            and token.word.raw in CONTROL_WORDS
        )
        for token in tokens
    ):
        variables[OPAQUE_STATE_KEY] = None
    index = 0
    case_patterns: list[bool] = []

    while index < len(tokens):
        if tokens[index].kind == "operator":
            if case_patterns:
                if tokens[index].text == ")" and case_patterns[-1]:
                    case_patterns[-1] = False
                elif tokens[index].text in {";;", ";&", ";;&"}:
                    case_patterns[-1] = True
            index += 1
            continue
        function = _function_at(tokens, index, source)
        if function is not None:
            name, body, index = function
            _record_function(functions, variables, name.casefold(), body)
            continue

        end = index
        while end < len(tokens) and tokens[end].kind != "operator":
            end += 1
        segment = tokens[index:end]
        first = _plain_function_word(segment, 0) if segment else None
        if first == "esac" and case_patterns:
            reason = _analyse_nested_tokens(
                segment, variables, functions, cwd, depth, budget
            )
            case_patterns.pop()
        elif case_patterns and case_patterns[-1]:
            reason = _analyse_nested_tokens(
                segment, variables, functions, cwd, depth, budget
            )
        else:
            reason = _analyse_segment(
                segment, variables, functions, cwd, depth, budget
            )
            if first == "case":
                case_patterns.append(True)
        if reason is not None:
            return reason
        index = end
    return None


def denial_reason(
    command: str, *, cwd: str | None = None, home: str | None = None
) -> str | None:
    """
    Return the first reason to deny a shell command without executing it.

    Args:
        > command (str):
            Shell source supplied by Codex.
        > cwd (str | None):
            Working directory used to resolve relative removal targets.
        > home (str | None):
            Home directory used to resolve active HOME and tilde expansions.

    Returns:
        - str | None: A denial reason, or None when no reviewed pattern matches.
    """
    if not isinstance(command, str):
        return GENERIC_REASON
    if command == "":
        return None
    try:
        if "\0" in command or len(command) > MAX_SOURCE_LENGTH:
            raise ParseError("invalid shell input")
        working_directory = posixpath.abspath(cwd or os.getcwd())
        home_directory = posixpath.abspath(home or os.path.expanduser("~"))
        variables: Variables = {
            "HOME": home_directory,
            "PWD": working_directory,
            ACTUAL_HOME_KEY: home_directory,
        }
        return _analyse_script(command, variables, {}, working_directory, 0)
    except Exception:
        return GENERIC_REASON


def _emit_denial(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")


def main() -> None:
    """Read one Codex hook payload and emit a valid fail-closed decision."""
    reason: str | None = None
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            reason = GENERIC_REASON
        else:
            tool_input = payload.get("tool_input")
            if not isinstance(tool_input, dict):
                reason = GENERIC_REASON
            else:
                command = tool_input.get("command")
                if not isinstance(command, str):
                    reason = GENERIC_REASON
                else:
                    payload_cwd = tool_input.get("workdir", payload.get("cwd"))
                    if payload_cwd is not None and (
                        not isinstance(payload_cwd, str)
                        or not posixpath.isabs(payload_cwd)
                    ):
                        reason = GENERIC_REASON
                    else:
                        reason = denial_reason(command, cwd=payload_cwd)
    except Exception:
        reason = GENERIC_REASON

    if reason is not None:
        _emit_denial(reason)


if __name__ == "__main__":
    main()
