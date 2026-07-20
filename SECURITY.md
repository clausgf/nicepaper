# Security Policy

## Supported versions

nicepaper is developed on `main`. Security fixes go into `main` and the next
release; older releases are not patched separately.

## Reporting a vulnerability

Please report security issues **privately**, not as a public GitHub issue.

Use [GitHub's private vulnerability reporting](https://github.com/clausgf/nicepaper/security/advisories/new)
for this repository. Include what you found, how to reproduce it, and what an
attacker could achieve with it.

Expect an initial response within a few days. This is a spare-time project, so
please allow reasonable time for a fix before disclosing publicly.

## Security model — what is and is not protected

Understanding the intended boundaries helps judge whether something is a bug:

- **No built-in authentication.** nicepaper ships without any authentication on
  either the display API or the management UI. This is deliberate for local
  trials and for running behind nice4iot, not a claim that the app is safe to
  expose. Put it behind an authenticating reverse proxy if it shouldn't be open
  to anyone who can reach it — an unauthenticated instance reachable from a
  network is a deployment mistake rather than a vulnerability in nicepaper.
- **Display API** (`/api`) — currently expected to be protected by external
  middleware or a reverse proxy in front of the app (see the [planned in-app
  API-key scheme](docs/development.md#api-keys-for-the-display-api)). Image
  URLs are otherwise unauthenticated: anyone who can reach the endpoint can
  fetch a rendered screen.
- **Outbound fetches** — nicepaper fetches iCal feeds and Open-Meteo weather
  data over the network on behalf of a screen's configuration. Treat the
  configured feed URLs as trusted input; a malicious feed is a configuration
  problem rather than a bypass of a boundary.
- **Filesystem storage** — screens, schedules, aliases and cached images live in
  plain files under `data/`. Anyone with read access to that directory can read
  the full configuration and rendered images.

Reports about the defaults above are welcome as regular issues; reports about
ways to bypass a boundary that *is* meant to hold — path traversal through
screen ids or file paths, injection through iCal/weather input, escaping the
`data/` directory — belong in a private advisory.
