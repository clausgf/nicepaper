"""
Templates section: the simplified UI's name for screens (a room's door sign
is laid out from a "template" -- the unsimplified editor's own vocabulary,
screen/ui.py, is unaffected).

Scaffolding only for now -- the actual editor content will follow the same
shape as the other feature packages' simplified_ui.py, once designed.
"""
from extensions.epaper.ui.simplified_ui.common import scaffold_note
from extensions.epaper.ui.simplified_ui.layout import Shell


def render_templates(shell: Shell) -> None:
    scaffold_note('Templates (screens) will be editable here.')
