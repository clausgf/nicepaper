"""Fixed Huffman codebook for German text, for the low-bandwidth wire format.

The codebook is *fixed*, not adaptive: encoder (here) and decoder
(firmware, see firmware/huffman_de.h) must agree on the exact same
symbol -> code mapping without exchanging any header, which only works
if both sides derive it from the same static table. `_WEIGHTS` below is
a generic estimate (standard German letter frequencies, plus rough
guesses for case/digits/punctuation) -- not yet derived from a real
corpus of the strings this will actually carry (event titles, organizer
names, ...); expect to replace it once such a corpus is available.

Only string-valued fields are meant to go through this codec; numeric/
enum fields (dates, times, weekdays, ...) should use a compact binary
encoding instead, where Huffman coding of digit characters would waste
bits compared to just packing the value.

Regenerate firmware/huffman_de.h after editing `_WEIGHTS`:

    uv run python -m extensions.epaper.wire.huffman_de
"""

from __future__ import annotations

import heapq
from itertools import count
from pathlib import Path


class _Sentinel:
    """Marks a non-character symbol (ESCAPE, END). Never equals a `str`,
    so it can't collide with a real character even in pathological input."""

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<{self.name}>"


ESCAPE = _Sentinel("ESCAPE")  # next 8 bits are a raw UTF-8 byte, verbatim
END = _Sentinel("END")  # terminates the string; no length prefix needed

Symbol = str | _Sentinel

# Generic German character-frequency estimate (relative weights, not
# percentages -- only the ratios matter for Huffman). Base letter
# frequencies follow the commonly cited German "Buchstabenhäufigkeit"
# distribution (*10, rounded); uppercase is estimated as roughly 1/6 of
# its lowercase counterpart (only word-initial and German noun
# capitalization); space, digits and punctuation are rough guesses for
# short calendar/label strings.
_WEIGHTS: list[tuple[Symbol, int]] = [
    (" ", 160),
    ("e", 174), ("n", 98), ("i", 76), ("s", 73), ("r", 70), ("a", 65),
    ("t", 62), ("d", 51), ("h", 48), ("u", 44), ("l", 34), ("c", 31),
    ("g", 30), ("m", 25), ("o", 25), ("b", 19), ("w", 19), ("f", 17),
    ("k", 12), ("z", 11), ("p", 8), ("v", 7), ("ß", 3), ("j", 3),
    ("y", 1), ("x", 1), ("q", 1),
    ("ä", 5), ("ö", 3), ("ü", 7),
    ("A", 11), ("B", 3), ("C", 5), ("D", 9), ("E", 29), ("F", 3),
    ("G", 5), ("H", 8), ("I", 13), ("J", 1), ("K", 2), ("L", 6),
    ("M", 4), ("N", 16), ("O", 4), ("P", 1), ("Q", 1), ("R", 12),
    ("S", 12), ("T", 10), ("U", 7), ("V", 1), ("W", 3), ("X", 1),
    ("Y", 1), ("Z", 2),
    ("Ä", 1), ("Ö", 1), ("Ü", 1),
    ("0", 6), ("1", 6), ("2", 6), ("3", 6), ("4", 6), ("5", 6),
    ("6", 6), ("7", 6), ("8", 6), ("9", 6),
    (".", 20), (",", 18), (":", 8), (";", 3), ("-", 10), ("/", 4),
    ("(", 5), (")", 5), ("&", 1), ("+", 1), ("'", 3), ('"', 2),
    ("!", 3), ("?", 3), ("%", 1), ("€", 1),
    (ESCAPE, 5),
    (END, 2),
]


def _code_lengths(weights: list[tuple[Symbol, int]]) -> dict[Symbol, int]:
    """Huffman code length per symbol, via the classic merge algorithm
    (each merge of two nodes adds one bit to every symbol under them).
    Deterministic tie-breaking (insertion order) so this always produces
    the same lengths for the same `weights` list."""
    tiebreak = count()
    heap: list[list] = [[w, next(tiebreak), [sym]] for sym, w in weights]
    heapq.heapify(heap)
    lengths: dict[Symbol, int] = {sym: 0 for sym, _ in weights}
    while len(heap) > 1:
        w1, _, syms1 = heapq.heappop(heap)
        w2, _, syms2 = heapq.heappop(heap)
        for sym in syms1:
            lengths[sym] += 1
        for sym in syms2:
            lengths[sym] += 1
        heapq.heappush(heap, [w1 + w2, next(tiebreak), syms1 + syms2])
    return lengths


def _canonical_codes(weights: list[tuple[Symbol, int]]) -> dict[Symbol, tuple[int, int]]:
    """Canonical Huffman codes (code, length) per symbol: symbols sorted
    by (length, table order), codes assigned as a simple counter that
    left-shifts on each length increase. Only the length list needs to
    be shared between encoder and decoder for this to be reproducible;
    here both live in the same table, so it's a pure implementation
    detail of how the bit patterns are chosen."""
    lengths = _code_lengths(weights)
    order = {sym: i for i, (sym, _) in enumerate(weights)}
    symbols_by_length = sorted(order, key=lambda sym: (lengths[sym], order[sym]))
    codes: dict[Symbol, tuple[int, int]] = {}
    code = 0
    prev_length = 0
    for sym in symbols_by_length:
        length = lengths[sym]
        code <<= length - prev_length
        codes[sym] = (code, length)
        code += 1
        prev_length = length
    return codes


CODES: dict[Symbol, tuple[int, int]] = _canonical_codes(_WEIGHTS)
_DECODE: dict[tuple[int, int], Symbol] = {(length, code): sym for sym, (code, length) in CODES.items()}
_MAX_CODE_LENGTH = max(length for _, length in CODES.values())


class _BitWriter:
    def __init__(self) -> None:
        self._bits: list[int] = []

    def write(self, value: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def to_bytes(self) -> bytes:
        bits = self._bits + [0] * ((-len(self._bits)) % 8)
        out = bytearray(len(bits) // 8)
        for i, bit in enumerate(bits):
            out[i // 8] |= bit << (7 - i % 8)
        return bytes(out)


class _BitReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._bit_pos = 0

    def read_bit(self) -> int:
        byte = self._data[self._bit_pos // 8]
        bit = (byte >> (7 - self._bit_pos % 8)) & 1
        self._bit_pos += 1
        return bit


def encode(text: str) -> bytes:
    """Encode `text` to Huffman-coded bytes. Characters outside the
    codebook are passed through as raw UTF-8 bytes behind an ESCAPE
    symbol each, so any string can be encoded, just less efficiently."""
    writer = _BitWriter()
    for ch in text:
        code_and_length = CODES.get(ch)
        if code_and_length is not None:
            writer.write(*code_and_length)
        else:
            esc_code, esc_length = CODES[ESCAPE]
            for raw_byte in ch.encode("utf-8"):
                writer.write(esc_code, esc_length)
                writer.write(raw_byte, 8)
    writer.write(*CODES[END])
    return writer.to_bytes()


def decode(data: bytes) -> str:
    """Inverse of `encode`. Raises ValueError on a malformed/truncated
    stream (e.g. no END symbol before the input runs out)."""
    reader = _BitReader(data)
    total_bits = len(data) * 8
    out_chars: list[str] = []
    pending_bytes = bytearray()

    def flush_escaped() -> None:
        if pending_bytes:
            out_chars.append(pending_bytes.decode("utf-8"))
            pending_bytes.clear()

    while True:
        code = 0
        length = 0
        sym = None
        while sym is None:
            if reader._bit_pos >= total_bits:
                raise ValueError("truncated huffman stream (no END symbol)")
            code = (code << 1) | reader.read_bit()
            length += 1
            if length > _MAX_CODE_LENGTH:
                raise ValueError("invalid huffman stream")
            sym = _DECODE.get((length, code))
        if sym is END:
            flush_escaped()
            return "".join(out_chars)
        if sym is ESCAPE:
            raw_byte = 0
            for _ in range(8):
                raw_byte = (raw_byte << 1) | reader.read_bit()
            pending_bytes.append(raw_byte)
            continue
        flush_escaped()
        out_chars.append(sym)  # type: ignore[arg-type]


def _c_symbol_kind(sym: Symbol) -> str:
    if sym is ESCAPE:
        return "HUFFMAN_DE_ESCAPE"
    if sym is END:
        return "HUFFMAN_DE_END"
    return "HUFFMAN_DE_CHAR"


def _c_table_entries() -> list[str]:
    entries = []
    for sym, (code, length) in CODES.items():
        kind = _c_symbol_kind(sym)
        if kind == "HUFFMAN_DE_CHAR":
            utf8 = sym.encode("utf-8")  # type: ignore[union-attr]
            utf8_bytes = ", ".join(f"0x{b:02x}" for b in utf8)
            padding = ", ".join(["0x00"] * (4 - len(utf8)))
            utf8_init = utf8_bytes + (", " + padding if padding else "")
            entries.append(
                f"    {{ {kind}, {{{utf8_init}}}, {len(utf8)}, "
                f"0x{code:x}, {length} }}, /* {sym!r} */"
            )
        else:
            entries.append(
                f"    {{ {kind}, {{0x00, 0x00, 0x00, 0x00}}, 0, "
                f"0x{code:x}, {length} }},"
            )
    return entries


_GENERATED_NOTICE = (
    "/* Generated by extensions/epaper/wire/huffman_de.py -- do not edit by\n"
    " * hand, regenerate instead. Fixed German-text Huffman codebook, see\n"
    " * that module's docstring for the wire format this decodes.\n"
    " *\n"
    " * Decode-only: encoding happens server-side (nicepaper); firmware\n"
    " * only needs to turn received bytes back into a string. */"
)


def generate_c_header() -> str:
    """Declarations only -- the table and decode function are defined once
    in huffman_de.c, so including this header from several translation
    units doesn't duplicate the (fairly large) codebook table."""
    lines = [
        "#ifndef HUFFMAN_DE_H",
        "#define HUFFMAN_DE_H",
        "",
        _GENERATED_NOTICE,
        "",
        "#include <stdint.h>",
        "#include <stddef.h>",
        "",
        "#ifdef __cplusplus",
        'extern "C" {',
        "#endif",
        "",
        "typedef enum {",
        "    HUFFMAN_DE_CHAR,",
        "    HUFFMAN_DE_ESCAPE,",
        "    HUFFMAN_DE_END,",
        "} huffman_de_kind_t;",
        "",
        "typedef struct {",
        "    huffman_de_kind_t kind;",
        "    uint8_t utf8[4];",
        "    uint8_t utf8_len;",
        "    uint32_t code;",
        "    uint8_t length;",
        "} huffman_de_symbol_t;",
        "",
        f"#define HUFFMAN_DE_TABLE_SIZE {len(CODES)}",
        "extern const huffman_de_symbol_t HUFFMAN_DE_TABLE[HUFFMAN_DE_TABLE_SIZE];",
        "",
        "/* Decodes `data` (byte_len bytes) into `out` (out_size bytes,",
        " * NUL-terminated). Returns the decoded length (excl. NUL), or -1 on",
        " * a malformed stream or if `out` is too small. */",
        "int huffman_de_decode(const uint8_t *data, size_t byte_len,",
        "                       char *out, size_t out_size);",
        "",
        "#ifdef __cplusplus",
        "}",
        "#endif",
        "",
        "#endif /* HUFFMAN_DE_H */",
        "",
    ]
    return "\n".join(lines)


def generate_c_source() -> str:
    """Table definition and decode implementation, compiled once."""
    lines = [
        _GENERATED_NOTICE,
        "",
        '#include "huffman_de.h"',
        "",
        "const huffman_de_symbol_t HUFFMAN_DE_TABLE[HUFFMAN_DE_TABLE_SIZE] = {",
        *_c_table_entries(),
        "};",
        "",
        "typedef struct {",
        "    const uint8_t *data;",
        "    size_t byte_len;",
        "    size_t bit_pos;",
        "} huffman_de_reader_t;",
        "",
        "static int huffman_de_read_bit(huffman_de_reader_t *r) {",
        "    uint8_t byte = r->data[r->bit_pos / 8];",
        "    int bit = (byte >> (7 - (r->bit_pos % 8))) & 1;",
        "    r->bit_pos++;",
        "    return bit;",
        "}",
        "",
        "int huffman_de_decode(const uint8_t *data, size_t byte_len,",
        "                       char *out, size_t out_size) {",
        "    huffman_de_reader_t r = { data, byte_len, 0 };",
        "    size_t out_len = 0;",
        "    uint32_t code = 0;",
        "    uint8_t length = 0;",
        "    while (r.bit_pos < byte_len * 8) {",
        "        code = (code << 1) | (uint32_t)huffman_de_read_bit(&r);",
        "        length++;",
        "        const huffman_de_symbol_t *match = NULL;",
        "        for (size_t i = 0; i < HUFFMAN_DE_TABLE_SIZE; i++) {",
        "            if (HUFFMAN_DE_TABLE[i].length == length && HUFFMAN_DE_TABLE[i].code == code) {",
        "                match = &HUFFMAN_DE_TABLE[i];",
        "                break;",
        "            }",
        "        }",
        "        if (!match) {",
        f"            if (length > {_MAX_CODE_LENGTH}) return -1;",
        "            continue;",
        "        }",
        "        code = 0;",
        "        length = 0;",
        "        if (match->kind == HUFFMAN_DE_END) {",
        "            if (out_len >= out_size) return -1;",
        "            out[out_len] = '\\0';",
        "            return (int)out_len;",
        "        }",
        "        if (match->kind == HUFFMAN_DE_ESCAPE) {",
        "            if (r.bit_pos + 8 > byte_len * 8) return -1;",
        "            uint8_t raw = 0;",
        "            for (int b = 0; b < 8; b++) raw = (uint8_t)((raw << 1) | (uint8_t)huffman_de_read_bit(&r));",
        "            if (out_len + 1 >= out_size) return -1;",
        "            out[out_len++] = (char)raw;",
        "            continue;",
        "        }",
        "        if (out_len + match->utf8_len >= out_size) return -1;",
        "        for (uint8_t b = 0; b < match->utf8_len; b++) out[out_len++] = (char)match->utf8[b];",
        "    }",
        "    return -1; /* ran out of input before an END symbol */",
        "}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    firmware_dir = Path(__file__).resolve().parents[3] / "firmware"
    (firmware_dir / "huffman_de.h").write_text(generate_c_header())
    (firmware_dir / "huffman_de.c").write_text(generate_c_source())
    print(f"wrote {firmware_dir / 'huffman_de.h'}")
    print(f"wrote {firmware_dir / 'huffman_de.c'}")
