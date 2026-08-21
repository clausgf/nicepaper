"""
Page frame and navigation for the simplified UI.

The simplified UI is a standalone extension page (register_project_page,
see extensions/epaper/__init__.py) -- nice4iot renders no chrome around
it, so this module owns the whole frame: a header (hamburger + brand +
nice4iot user menu), a two-level sidebar in a responsive left drawer, and
a content area that switches views without a page reload.

Navigation is client-side state switching, not URL routing: nice4iot only
routes the extension page's *exact* base URL to us (its catch-all regex
ends in ``/?$``), so a deep link like ``.../ext/epaper/rooms`` would 404 on
reload. See docs/simplified-ui.md for the nice4iot changes that would let
sections become bookmarkable.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

from nicegui import ui

from extensions.epaper.paths import EpaperPaths

# Sidebar shows inline at >=1024px (Tailwind `lg`) and collapses to a
# toggled overlay below it. This is NiceGUI's default drawer breakpoint
# (value=None -> show-if-above 1024px); the hamburger uses the matching
# `lg:hidden` so the two never disagree. Bump both together to move to `xl`.
DRAWER_BREAKPOINT = 1024


@dataclass(frozen=True)
class NavItem:
    """One entry in the sidebar. A leaf carries a `render` (it is a view);
    a group carries `children` and no render (clicking only folds it)."""
    id: str
    label: str
    icon: str
    render: Optional[Callable[['Shell'], None]] = None
    children: tuple['NavItem', ...] = field(default_factory=tuple)


class Shell:
    """Navigation state and page context, one instance per rendered page.

    `navigate()` sets the active view (and optional per-view `params`, e.g.
    the selected room) and refreshes the sidebar and content area. Views get
    the Shell so they can read `project_name`/`paths`/`params` and navigate onward.
    """

    def __init__(self, project_name: str, paths: EpaperPaths, leaves: dict[str, NavItem]):
        self.project_name = project_name
        self.paths = paths
        self._leaves = leaves
        self.active: str = next(iter(leaves))  # first leaf is the landing view
        self.params: dict = {}
        self._sidebar: Optional[ui.refreshable] = None
        self._content: Optional[ui.refreshable] = None

    def _bind(self, sidebar: 'ui.refreshable', content: 'ui.refreshable') -> None:
        self._sidebar, self._content = sidebar, content

    def navigate(self, item_id: str, **params) -> None:
        self.active = item_id
        self.params = params
        if self._sidebar:
            self._sidebar.refresh()
        if self._content:
            self._content.refresh()

    def render_active(self) -> None:
        item = self._leaves.get(self.active) or next(iter(self._leaves.values()))
        assert item.render is not None
        item.render(self)


def _flatten(nav: list[NavItem]) -> dict[str, NavItem]:
    """Map id -> NavItem for every leaf (view) in the tree, in order."""
    leaves: dict[str, NavItem] = {}
    for item in nav:
        if item.render is not None:
            leaves[item.id] = item
        for child in item.children:
            if child.render is not None:
                leaves[child.id] = child
    return leaves


def _user_menu() -> None:
    """Render nice4iot's standard user menu when running as an extension.

    `app.extensions.render_user_menu()` is nice4iot's public entry point for
    the top-right person-icon menu (Home, Preferences, dark mode, About, and
    every registered extension item). Deferred import: `app.*` exists only
    inside the nice4iot process. In standalone mode there is no logged-in
    user, so the menu is simply omitted -- the header's brand just stays
    left-aligned.
    """
    try:
        from app.extensions import render_user_menu
    except ImportError:
        return  # standalone: no user session, no menu
    render_user_menu()


def _nav_icon_label(item: NavItem, *, icon_active: bool) -> None:
    """The icon + label pair shared by leaf rows and group headers. Shrink
    Quasar's avatar section (default min-width 56px, padding-right 16px) so the
    icon sits close to its label; inline style beats Quasar's class rule, a
    small padding-right keeps a slight gap."""
    with ui.item_section().props('avatar').style('min-width: 0; padding-right: 12px'):
        ui.icon(item.icon).classes('' if icon_active else 'text-primary')
    with ui.item_section():
        ui.item_label(item.label)


def _nav_row(shell: Shell, item: NavItem, *, inset: bool) -> None:
    active = shell.active == item.id
    row = ui.item(on_click=lambda: shell.navigate(item.id)).props('clickable dense') \
        .classes('rounded-borders')
    if inset:
        row.props('inset-level=0.5')
    if active:
        row.classes('bg-primary text-white')
    with row:
        _nav_icon_label(item, icon_active=active)


def _group_header(item: NavItem) -> None:
    """A group (an item with children) as a plain, non-clickable header row --
    not a ui.expansion, so it never folds; its children render as slightly
    indented rows below it (see render_sidebar)."""
    with ui.item().props('dense').classes('rounded-borders'):
        _nav_icon_label(item, icon_active=False)


def render_sidebar(shell: Shell, nav: list[NavItem]) -> None:
    """The two-level sidebar body: leaf sections are rows; a group is a plain
    header row followed by its (slightly indented) child rows -- never an
    expansion, so the tree is always fully visible."""
    with ui.list().props('padding').classes('w-full'):
        for item in nav:
            if item.children:
                _group_header(item)
                for child in item.children:
                    _nav_row(shell, child, inset=True)
            else:
                _nav_row(shell, item, inset=False)


def build_page(project_name: str, paths: EpaperPaths, nav: list[NavItem]) -> None:
    """Assemble the header, drawer/sidebar and content area for one page.

    Header and drawer are top-level layout elements, so this must be called
    at the page top level (it is: the extension render_fn runs directly
    under nice4iot's @ui.page, with no wrapping element).
    """
    shell = Shell(project_name, paths, _flatten(nav))

    with ui.left_drawer(bordered=True).props(f'breakpoint={DRAWER_BREAKPOINT}') as drawer:
        @ui.refreshable
        def sidebar() -> None:
            render_sidebar(shell, nav)
        sidebar()

    with ui.header(elevated=True).classes('items-center gap-2'):
        # Hamburger only where the drawer has collapsed to an overlay.
        ui.button(icon='menu', on_click=drawer.toggle) \
            .props('flat color=white round dense').classes('lg:hidden')
        ui.icon('meeting_room').classes('text-2xl')
        ui.label('E-Paper Rooms').classes('text-h6 font-bold')
        ui.space()
        _user_menu()

    with ui.column().classes('w-full p-4 gap-4'):
        @ui.refreshable
        def content() -> None:
            shell.render_active()
        content()

    shell._bind(sidebar, content)
