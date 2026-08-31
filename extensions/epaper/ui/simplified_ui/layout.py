"""
Page frame and navigation for the simplified UI.

The simplified UI is a standalone extension page (register_project_page,
see extensions/epaper/__init__.py). nice4iot routes the whole subtree under
the page's own URL to it, not just its exact base URL (see docs/extensions.md
in the nice4iot repo, "Deep links within a standalone page"), so this module
builds real, bookmarkable routing with nicegui's ui.sub_pages: a header
(hamburger + brand + nice4iot user menu), a two-level sidebar in a
responsive left drawer, and a content area whose URL reflects the active
section. See docs/simplified-ui.md.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from nicegui import context, ui

from extensions.epaper.paths import EpaperPaths

# Sidebar shows inline at >=1024px (Tailwind `lg`) and collapses to a
# toggled overlay below it. This is NiceGUI's default drawer breakpoint
# (value=None -> show-if-above 1024px); the hamburger uses the matching
# `lg:hidden` so the two never disagree. Bump both together to move to `xl`.
DRAWER_BREAKPOINT = 1024


@dataclass(frozen=True)
class NavItem:
    """One entry in the sidebar. A leaf carries a `render` (it is a view,
    addressed by its own URL -- see _paths()); a group carries `children`
    and no render (clicking only folds it)."""
    id: str
    label: str
    icon: str
    render: Optional[Callable[['Shell'], None]] = None
    children: tuple['NavItem', ...] = field(default_factory=tuple)


class Shell:
    """Page context, one instance per rendered page. Views get the Shell so
    they can read project_name/paths/image_base_url."""

    def __init__(self, project_name: str, paths: EpaperPaths, image_base_url: str = ''):
        self.project_name = project_name
        self.paths = paths
        # the display API's screen-image prefix (e.g. '/api/ext/epaper/<project>/screens'
        # as an extension, '/../api/screen' standalone) -- append '/<id>/image.png'.
        # Needed by Templates (screen previews); other sections don't render images.
        self.image_base_url = image_base_url


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


def _paths(nav: list[NavItem]) -> dict[str, str]:
    """id -> its route path, relative to root_path: a top-level leaf is
    '/{id}', a group's child is '/{parent_id}/{id}'."""
    item_paths: dict[str, str] = {}
    for item in nav:
        if item.render is not None:
            item_paths[item.id] = f'/{item.id}'
        for child in item.children:
            if child.render is not None:
                item_paths[child.id] = f'/{item.id}/{child.id}'
    return item_paths


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


def _current_relative_path(root_path: str) -> str:
    """The browser's current path, relative to root_path -- same stripping
    ui.sub_pages itself does (see nicegui's SubPages._find_matching_path)."""
    router = context.client.sub_pages_router
    relative = router.current_path[len(root_path):] if root_path else router.current_path
    if not relative.startswith('/'):
        relative = '/' + relative
    return relative


def _is_active(item_path: str, current: str) -> bool:
    """Exact match, or -- for Rooms -- a room-detail sub-path under it
    (/rooms/{id})."""
    return current == item_path or current.startswith(item_path + '/')


def _nav_row(root_path: str, item: NavItem, item_path: str, current: str, *, inset: bool) -> None:
    active = _is_active(item_path, current)
    row = ui.item(on_click=lambda: ui.navigate.to(f'{root_path}{item_path}')).props('clickable dense') \
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


def render_sidebar(nav: list[NavItem], root_path: str, item_paths: dict[str, str],
                   landing_path: str) -> None:
    """The two-level sidebar body: leaf sections are rows; a group is a plain
    header row followed by its (slightly indented) child rows -- never an
    expansion, so the tree is always fully visible. The active row is
    computed fresh from the browser's current URL on every render, so it
    stays correct after a client-side ui.sub_pages navigation. The bare '/'
    (build_page's alias for the landing leaf) counts as that leaf's own path."""
    current = _current_relative_path(root_path)
    if current == '/':
        current = landing_path
    with ui.list().props('padding').classes('w-full'):
        for item in nav:
            if item.children:
                _group_header(item)
                for child in item.children:
                    _nav_row(root_path, child, item_paths[child.id], current, inset=True)
            else:
                _nav_row(root_path, item, item_paths[item.id], current, inset=False)


def _leaf_route(fn: Callable[[Shell], None], shell: Shell) -> Callable[[], None]:
    return lambda: fn(shell)


def build_page(project_name: str, paths: EpaperPaths, nav: list[NavItem],
               image_base_url: str = '', root_path: str = '',
               extra_routes: Optional[Callable[[Shell], dict[str, Callable[..., Any]]]] = None) -> None:
    """Assemble the header, drawer/sidebar and content area for one page.

    Header and drawer are top-level layout elements, so this must be called
    at the page top level (it is: the extension render_fn runs directly
    under nice4iot's @ui.page, with no wrapping element).

    root_path is the extension page's own base URL (e.g.
    '/ui/project/<project>/ext/epaper' as an extension, '/simplified'
    standalone) -- every section's route is relative to it. extra_routes, if
    given, is called with the Shell and merged into the ui.sub_pages routes
    (e.g. the room-detail deep link, see ui/simplified_ui/__init__.py).
    """
    shell = Shell(project_name, paths, image_base_url)
    leaves = _flatten(nav)
    item_paths = _paths(nav)
    landing_id = next(iter(leaves))
    landing_path = item_paths[landing_id]

    with ui.left_drawer(bordered=True).props(f'breakpoint={DRAWER_BREAKPOINT}') as drawer:
        @ui.refreshable
        def sidebar() -> None:
            render_sidebar(nav, root_path, item_paths, landing_path)
        sidebar()

    with ui.header(elevated=True).classes('items-center gap-2'):
        # Hamburger only where the drawer has collapsed to an overlay.
        ui.button(icon='menu', on_click=drawer.toggle) \
            .props('flat color=white round dense').classes('lg:hidden')
        ui.icon('meeting_room').classes('text-2xl')
        ui.label('E-Paper Rooms').classes('text-h6 font-bold')
        ui.space()
        _user_menu()

    with ui.column().classes('w-full h-full p-4 gap-4'):
        routes: dict[str, Callable[..., Any]] = {}
        for leaf_id, leaf in leaves.items():
            assert leaf.render is not None
            routes[item_paths[leaf_id]] = _leaf_route(leaf.render, shell)
        routes['/'] = routes[landing_path]
        if extra_routes is not None:
            routes.update(extra_routes(shell))
        ui.sub_pages(routes, root_path=root_path).classes('w-full h-full')

    def _resync_sidebar(_: str) -> None:
        sidebar.refresh()

    context.client.sub_pages_router.on_path_changed(_resync_sidebar)
