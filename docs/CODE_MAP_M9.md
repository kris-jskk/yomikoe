# YomiKoe M9 code map: hosting

This document explains how the M9 additions work end to end and what every file M9 added or changed
does. It is written for an engineer who has read `docs/PRD.md` (what; Domains table, Milestones item 9,
HOST-1..3) and `docs/TECHNICAL_DESIGN.md` (how; D52, D54). The step-by-step account settings at GitHub
and at the registrar are in `docs/HOSTING.md`; this map covers the files.

Guide: `docs/guide/m9-hosting-map.html` ("YomiKoe M9 Hosting Map").

## Scope and status

Updated 2026-10-21 on branch `m9-hosting`, phase 1 (landing page). Built: the static site in `site/`
(commit `a5cc810`, merge `6e0798f`, checks `_agent/results/1231_site_parse.txt` to
`1240_site_commit.txt`) and the GitHub Pages workflow with its docs (commit `feb4b6a`, merge `5b7321e`,
checks `1246_site_yaml.txt` to `1250_deploy_commit.txt`). Not done: the GitHub Pages settings, the DNS
records and the getyomikoe.com redirect, which are user actions (`docs/HOSTING.md` sections b, c, d). A
call-to-action follow-up on the page is running in parallel and is not recorded here yet. Phase 2
(app. and api. hosting, HOST-4 and later) and phase 3 (backups and the gate) are not planned yet.

Nothing in M9 phase 1 touches `api/` or `web/`: the reader and the API still run only locally via Docker
Compose (D30).

### Status words

| Word | Meaning |
| --- | --- |
| implemented | Real file; exercised only by hand or not at all. |
| tested by results N | Real file plus a saved check under `_agent/results/` that exercises it. |
| pending user action | The file is in place but has no effect until the user changes a setting outside the repo. |
| planned | Named in the PRD, not built yet. |

## Code flows

### a. A push to `main` becomes https://yomikoe.app (HOST-1, HOST-2, D54)

1. A commit reaches `main` that changes a path under `site/**` or `.github/workflows/site.yml`
   (the `on.push.paths` filter), or someone clicks "Run workflow" on the "site" workflow
   (`workflow_dispatch`). Pushes that touch only `api/` or `web/` do not run it.
2. GitHub Actions starts job `deploy` on `ubuntu-latest` with permissions `contents: read`,
   `pages: write`, `id-token: write`, in concurrency group `pages` (one deploy at a time, a running one is
   not cancelled), in environment `github-pages`.
3. `actions/checkout@v4` checks out the repository.
4. `actions/configure-pages@v5` reads the repository's Pages configuration. It needs Settings > Pages >
   Source set to "GitHub Actions" (HOSTING.md b.1; pending user action).
5. `actions/upload-pages-artifact@v3` with `path: site` packs the `site/` folder as it is. There is no
   build step (HOST-1): the files served are the files committed. `site/CNAME` (`yomikoe.app`) travels
   with them and names the custom domain.
6. `actions/deploy-pages@v4` publishes the artifact; its `page_url` output becomes the environment URL.
7. Pages serves the files from its CDN. Once the registrar has the four A and four AAAA records for the
   apex (`_agent/results/1248_pages_dns.txt`; HOSTING.md c) and the custom domain is saved in the
   settings (HOSTING.md b.3), Pages issues a Let's Encrypt certificate and "Enforce HTTPS" can be ticked
   (b.4), which is HOST-2.

Status: the workflow parses and its triggers and pins are as above (`1246_site_yaml.txt`); the action
tags were checked against their releases pages, and the floating `upload-pages-artifact@v3` tag is
unverified, with `@v3.0.1` as the documented fallback (`1247_actions_tags.txt`). The workflow has never
run: it runs only from `main`, and the branch is not merged to `main` or pushed.

### b. A visitor opens the page (HOST-1)

1. The browser resolves `yomikoe.app` through the registrar's DNS to the GitHub Pages addresses
   (pending user action), then requests `/` over HTTPS (`.app` is HSTS-preloaded, so HTTP is never used).
2. Pages returns `site/index.html`. Its `<head>` loads `styles.css` and `favicon.svg` from the same
   origin and the Inter and Libre Baskerville fonts from Google Fonts (`fonts.googleapis.com`, with a
   preconnect to `fonts.gstatic.com`). Those are the only external fetches
   (`_agent/results/1233_site_external.txt`).
3. One inline script runs: the theme toggle. On load it reads `localStorage['yomikoe-theme']` and, if it
   is `light` or `dark`, sets `data-theme` on `<html>`; otherwise the CSS follows
   `prefers-color-scheme`. Clicking `#theme-toggle` flips the theme and stores the choice. Storage
   errors are caught, so the page renders without it. There is no other JavaScript.
4. The page sections, in order: header nav, hero (`#top`), three modes (`#who`), pipeline (`#how`),
   features (`#features`, nine cards), "Open, and yours" (`#open`), getting started (`#start`), FAQ
   (`#faq`), footer. Each section's HTML comment names the PRD row or doc its claims come from (see the
   guide, section 5). All in-page anchors resolve (`1232_site_anchors.txt`).
5. Outbound links go to the GitHub repository, the PRD on GitHub, and `https://app.yomikoe.app`, which is
   not hosted yet (phase 2).
6. A path that does not exist gets `site/404.html`, which Pages serves for any missing path; it uses
   root-relative `/styles.css` and `/favicon.svg` so it renders at any depth.

Status: both pages have balanced tags (`1231_site_parse.txt`); no horizontal overflow at 1440 and
390 px in either theme (`1238_site_overflow.txt`, screenshots `1234`..`1237`); every text/fill colour
pair passes WCAG AA in both themes (`1239_site_contrast.txt`).

## Files

| File | Responsibility | Reads / writes | Status |
| --- | --- | --- | --- |
| `site/index.html` | The landing page: hero, three modes, pipeline, nine feature cards, open-source comparison, getting started, FAQ; HTML comments cite the PRD rows; inline theme-toggle script | Reads `styles.css`, `favicon.svg`, Google Fonts; writes `localStorage['yomikoe-theme']` | tested by results 1231_site_parse, 1232_site_anchors, 1233, 1234–1239 |
| `site/styles.css` | All styling: colour tokens on `:root`, dark mode under `prefers-color-scheme` and `[data-theme]`, responsive layout | Read by both pages | tested by results 1234–1239 |
| `site/favicon.svg` | Browser-tab icon (wordmark initial on the page colour) | Read by both pages | implemented |
| `site/404.html` | Not-found page served by Pages for any missing path; links back to `/` | Reads `/styles.css`, `/favicon.svg`, Google Fonts | tested by result 1231_site_parse |
| `site/CNAME` | Tells GitHub Pages the custom domain is `yomikoe.app` | Read by Pages at deploy | pending user action (HOSTING.md b.3, c) |
| `.github/workflows/site.yml` | Deploys `site/` to GitHub Pages on a push to `main` touching `site/**` or itself, or by hand | Reads `site/`; writes the Pages deployment | tested by results 1246, 1247 (parse and pins only; never run); pending user action (HOSTING.md b.1, b.2) |
| `docs/HOSTING.md` | What is hosted where, and the hand steps: Pages settings (b), apex DNS records (c), getyomikoe.com 301 (d), verify commands | Values from result 1248 | implemented (steps pending user action) |
| `docs/PRD.md` (changed) | Domains table status for yomikoe.app; Milestones item 9 phase 1 paragraph; HOST-1..3; proposed gate (a)–(d) | none | tested by result 1249 (grep) |
| `docs/TECHNICAL_DESIGN.md` (changed) | Row D54, landing page hosting, proposed | none | tested by result 1249 (grep) |
| `README.md` (changed) | Domains line: the landing page in `site/` is deployed by GitHub Pages, see `docs/HOSTING.md` | none | implemented (commit `feb4b6a`, result 1250) |
| `docs/guide/m9-hosting-map.html` | The M9 architectural guide (this milestone's status page) | none | implemented |
| `docs/CODE_MAP_M9.md` | This file | none | implemented |

### Planned (phase 2 and 3)

| Item | Requirement | Status |
| --- | --- | --- |
| app.yomikoe.app serving `web/`, api.yomikoe.app serving `api/` | HOST-4 and later, gate (a)–(c) | planned; provider undecided |
| getyomikoe.com 301 to https://yomikoe.app | HOST-3, gate (a) | pending user action (no file; registrar or Cloudflare rule) |
| Backups of the library volume and a restore test | gate (d) | planned |
