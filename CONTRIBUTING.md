# Contributing

Thanks for your interest in nicepaper. Issues and pull requests are welcome.

## Before you start

For anything larger than a bug fix, please open an issue first. nicepaper can
run standalone or as a [nice4iot](https://github.com/clausgf/nice4iot) extension
(`extensions.epaper`), and that dual role shapes its structure — a short
discussion up front saves rework.

## Development setup

```bash
uv sync --group dev
mkdir -p data/screens data/schedules data/images data/ical
cp examples/schedules/default.json data/schedules/
cp examples/screens/simple.json data/screens/
uv run uvicorn main:app --reload
```

See the [README](README.md) for the full picture, including standalone vs.
extension mode.

## Project rules

These keep the codebase consistent and are checked in review:

- **Display API changes go into [CHANGELOG.md](CHANGELOG.md).** Displays in the
  field poll that contract (image URLs, query parameters such as `color_model`,
  `ETag`/`Cache-Control` behaviour), so every change to it must be recorded.
- **Acceptance tests** (`tests/test_acceptance.py`) exercise the HTTP API
  end-to-end and encode the display-facing contract. Don't change them to make a
  change pass — if a change genuinely requires touching them, say so explicitly
  in the pull request and explain why.
- **Charts are drawn with Pillow**, not a plotting library, so they stay crisp
  on bilevel/limited e-paper palettes. Keep new rendering on the same footing
  rather than pulling in a dithering-prone dependency.

## Before opening a pull request

```bash
uv run ruff check
uv run pytest
```

Both must pass; CI runs the same two commands. Keep commits focused and explain
*why* in the commit message, not just what.

## Extensions

nicepaper itself is packaged as a nice4iot extension. If you want to add
functionality that isn't screen rendering, consider whether it belongs in a
separate extension instead — see nice4iot's
[docs/extensions.md](https://github.com/clausgf/nice4iot/blob/main/docs/extensions.md).

## Licence

nicepaper is licensed under the **GNU Affero General Public License v3.0 or
later**. By contributing, you agree that your contributions are licensed under
the same terms. Note that the AGPL's network clause applies: if you run a
modified version as a network service, you must offer its source to its users.
