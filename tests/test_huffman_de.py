import pytest

from extensions.epaper.wire import huffman_de


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Meeting Raum 3",
        "Büro der Geschäftsführung – Sprechstunde 14:00-15:30 (Änderung!)",
        "Straße, Größe, weiß, Grüße: äöüÄÖÜß",
        "ABC abc 0123456789 .,:;-/()&+'\"!?%€",
        "日本語 emoji 🎉 café",  # outside the codebook -> exercises ESCAPE fallback
    ],
)
def test_round_trip(text: str) -> None:
    encoded = huffman_de.encode(text)
    assert huffman_de.decode(encoded) == text


def test_common_chars_are_shorter_than_escaped_ones() -> None:
    # 'e' is the single most frequent symbol in the table, so it must get
    # a shorter code than a character that isn't in the table at all
    # (which pays a full ESCAPE symbol plus 8 raw bits per byte).
    _, e_length = huffman_de.CODES["e"]
    _, escape_length = huffman_de.CODES[huffman_de.ESCAPE]
    assert e_length < escape_length + 8


def test_compresses_typical_text() -> None:
    text = "Team Meeting Montag bis Freitag von 9:00 bis 17:00 Uhr"
    encoded = huffman_de.encode(text)
    assert len(encoded) < len(text.encode("utf-8"))


def test_decode_rejects_truncated_stream() -> None:
    encoded = huffman_de.encode("Raum 3")
    with pytest.raises(ValueError):
        huffman_de.decode(encoded[: len(encoded) // 2])
