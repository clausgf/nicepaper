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
  fetch a rendered screen. See
  [Serving display images over plain HTTP](#serving-display-images-over-plain-http)
  for exposing just the images to displays that can't do TLS.
- **Outbound fetches** — nicepaper fetches iCal feeds, Open-Meteo weather data,
  images and Home Assistant entity states over the network on behalf of a
  screen's configuration. Treat the configured URLs as trusted input; a
  malicious feed is a configuration problem rather than a bypass of a boundary.
- **Filesystem storage** — screens, schedules, aliases and cached images live in
  plain files under `data/`. Anyone with read access to that directory can read
  the full configuration and rendered images.
- **Credentials in the config file** — the Home Assistant long-lived access
  token is stored in plain text in the global config file, like every other
  setting. Give nicepaper a token of a dedicated, least-privileged Home
  Assistant user, and protect the config file with filesystem permissions.

## Serving display images over plain HTTP

E-paper displays are not browsers: a firmware polling `image.png` usually has no
certificate store worth the name, so putting the whole deployment behind HTTPS
can make the images unreachable for the very devices they exist for. The
supported answer is a second, plain-HTTP listener **in the reverse proxy** that
serves nothing but the image endpoint, restricted to the LAN the displays are
on — not a second listener inside nicepaper, which would have to duplicate what
the proxy already does well.

With Caddy:

```caddyfile
# HTTPS as usual for the API and the management UI
epaper.example.com {
	reverse_proxy 127.0.0.1:8000
}

# plain HTTP for the displays: images only, LAN only
http://:8081 {
	@image {
		remote_ip 192.168.2.0/24
		path_regexp ^/api/(screen/[^/]+|ext/epaper/[^/]+/screens/[^/]+)/image\.png$
	}
	handle @image {
		reverse_proxy 127.0.0.1:8000
	}
	respond 404
}
```

Adapt `192.168.2.0/24` to the network your displays sit on, and the path pattern
to the mode you run: `/api/screen/<id>/image.png` standalone,
`/api/ext/epaper/<project>/screens/<id>/image.png` as a nice4iot extension. Both
conditions are ANDed, and everything else on that port — the management UI, the
rest of the API, requests from outside the LAN — gets a flat `404`.

This **adds** a way to reach the images, it does not move them: `image.png`
stays available over HTTPS as well, on the normal site, subject to whatever
protects it there. That is intended — the management UI loads the preview from
its own origin with a relative URL, so excluding the image path from the HTTPS
site to "have only one way in" breaks the editor preview. The practical
consequence is that the weakest path to a rendered screen is now "be on the
right subnet".

What this does and does not buy you:

- **Not confidentiality.** The images travel unencrypted and unauthenticated;
  anyone on that LAN can fetch any screen. That is fine for a weather panel and
  a deliberate decision for a room calendar, whose rendered image shows meeting
  subjects and organisers.
- **`remote_ip` is not authentication.** It matches the address of the directly
  connecting peer, which anything on the same LAN can hold. It keeps the plain
  port off the internet; it does not keep a compromised device off it.
- **The editor views come along.** `?raw=true` and `?boxes=true` live on the
  same path. Add `not query raw=*` and `not query boxes=*` to the matcher if
  that bothers you.
- **Port 80 works too**, by defining an explicit `http://<host>` block that
  proxies the image path and redirects everything else. Note that taking over
  port 80 for a host means Caddy no longer adds its own HTTP→HTTPS redirect
  there — the block has to do it — and verify certificate renewal still works,
  or switch that site to the TLS-ALPN or DNS challenge.

Reports about the defaults above are welcome as regular issues; reports about
ways to bypass a boundary that *is* meant to hold — path traversal through
screen ids or file paths, injection through iCal/weather input, escaping the
`data/` directory — belong in a private advisory.
