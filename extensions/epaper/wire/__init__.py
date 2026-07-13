"""Low-bandwidth wire format for e.g. LoRaWAN displays.

Instead of shipping a rendered PNG, only widget data is sent and the
device renders it locally. String fields go through the fixed German
Huffman codebook in `huffman_de`; the per-widget data payload format is
not designed yet.
"""
