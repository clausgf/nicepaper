from extensions.epaper.core.datasources.ical import IcalStatus


def test_unreadable_items_banner_renders_nothing_when_zero():
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.cards import unreadable_items_banner

    with Client(page("/test-banner-zero"), request=None) as client:
        unreadable_items_banner(0, "room(s)")
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert not labels


def test_unreadable_items_banner_shows_the_count_and_subject():
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.cards import unreadable_items_banner

    with Client(page("/test-banner-nonzero"), request=None) as client:
        unreadable_items_banner(2, "room(s)")
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert any("2 room(s) failed to load" in t for t in labels)


def _status(failing: bool, events=None, error=None) -> IcalStatus:
    return IcalStatus(id="a", events=events, last_update=None, fresh=not failing,
                      failing=failing, fail_count=3 if failing else 0,
                      retry_after=None, error=error)


def test_datasource_health_rows_only_failing_stays_silent_when_healthy():
    """The simplified UI's Rooms landing view passes only_failing=True so it
    stays quiet unless something is actually down -- a healthy status must
    draw nothing at all, not even the title."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.cards import datasource_health_rows

    with Client(page("/test-health-quiet"), request=None) as client:
        count = datasource_health_rows(ical_statuses=[_status(failing=False, events=[])],
                                       only_failing=True, title="Data source issues")
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert count == 0
    assert not labels


def test_datasource_health_rows_only_failing_shows_failing_ones_with_title():
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.cards import datasource_health_rows

    with Client(page("/test-health-failing"), request=None) as client:
        count = datasource_health_rows(ical_statuses=[_status(failing=True, error="boom")],
                                       only_failing=True, title="Data source issues")
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert count == 1
    assert "Data source issues" in labels
    assert "iCal a: unavailable" in labels


def test_datasource_health_rows_default_shows_every_status_unconditionally():
    """dashboard_card()'s own contract: without only_failing, every status is
    listed regardless of health -- unchanged by the only_failing/title
    refactor."""
    from nicegui.client import Client
    from nicegui.page import page

    from extensions.epaper.ui.cards import datasource_health_rows

    with Client(page("/test-health-all"), request=None) as client:
        count = datasource_health_rows(ical_statuses=[_status(failing=False, events=[])])
        labels = {e.text for e in client.elements.values() if type(e).__name__ == "Label"}

    assert count == 1
    assert any("updated" in t for t in labels)
