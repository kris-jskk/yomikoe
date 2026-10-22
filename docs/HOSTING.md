# Hosting (M9 phase 1)

Status: proposed (D54, awaiting user confirmation). This file lists what is hosted where and the steps you do by hand
at GitHub and at the registrar. Nothing here is done by code.

## a. What is hosted where

| Name | Points at | Status today (2026-10-21) |
|---|---|---|
| yomikoe.app | Landing page, `site/`, GitHub Pages | Page built; Pages settings and DNS pending (sections b and c) |
| app.yomikoe.app | The reader (`web/`) | Not hosted; runs locally via Docker Compose |
| api.yomikoe.app | The API (`api/`) | Not hosted; runs locally via Docker Compose |
| getyomikoe.com | 301 to https://yomikoe.app | Redirect not set (section d) |

## b. Landing page on GitHub Pages

GitHub Pages is GitHub's free static-file hosting. The repository is public, so it costs nothing. The workflow
`.github/workflows/site.yml` copies the `site/` folder to Pages on every push to `main` that touches `site/` or the
workflow file (you can also run it by hand from the repository's Actions tab, "site", "Run workflow").
`site/CNAME` tells Pages the custom domain is `yomikoe.app`.

One-time settings, in the GitHub repository (github.com/kris-jskk/yomikoe):

1. Settings > Pages > Build and deployment > Source: choose "GitHub Actions".
2. Merge the branch containing the workflow to `main` (the workflow only runs from `main`), or run it by hand once.
3. Settings > Pages > Custom domain: enter `yomikoe.app` and save. GitHub checks the DNS from section c; this can show
   an error until the records exist and propagate.
4. When the certificate has been issued (can take up to about an hour after DNS works), tick "Enforce HTTPS".
   `.app` domains require HTTPS in browsers anyway.

## c. DNS for yomikoe.app at the registrar

At the registrar (or the DNS host), add these records for the apex (the bare name `yomikoe.app`, shown as `@` by many
panels). Values are from GitHub's page "Managing a custom domain for your GitHub Pages site" (fetched 2026-10-21;
`_agent/results/1248_pages_dns.txt`).

| Type | Name | Value |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |

TTL: use the registrar's default or 3600 seconds; a low value (300) helps while you are setting up. Delete any other
A, AAAA or CNAME record for `@` that the registrar pre-created (a parking page). No `www` record: the brand prints the
bare domain.

Verify (DNS can take minutes to hours to propagate):

```
dig +short yomikoe.app
dig +short AAAA yomikoe.app
curl -sI https://yomikoe.app | head -5
```

The first should list the four A addresses, the second the four AAAA addresses, the third should start with `HTTP/2 200`.

## d. getyomikoe.com redirects (301) to yomikoe.app

This is a setting at the registrar or Cloudflare, not code. Either way: permanent (301), destination
`https://yomikoe.app`, do not append the path.

Cloudflare (if the domain's nameservers are on Cloudflare): Rules > Redirect Rules (or Bulk Redirects), create a rule
matching hostname equals `getyomikoe.com`, action "Static" redirect to `https://yomikoe.app`, status 301, "Preserve
query string" and path forwarding off. The domain needs a proxied (orange cloud) DNS record to act on, for example an A
record `@` to `192.0.2.1`, which is a placeholder address that is never contacted (unverified: Cloudflare's
current wording; check their Redirect Rules page).

Registrar "domain forwarding" (GoDaddy, Namecheap, Porkbun and similar call it forwarding or URL redirect): set the
type to Permanent (301), forward to `https://yomikoe.app`, not "masking" or "frame". Panel names vary (unverified for
any specific registrar).

Verify:

```
curl -sI https://getyomikoe.com | grep -i "^location\|^HTTP"
```

Expected: `HTTP/... 301` and `location: https://yomikoe.app` (with or without a trailing slash).

## e. Later phases

app., api. and backups: not planned yet; see PRD item 9 gate (b)-(d).

## Notes

- Action pins in the workflow: configure-pages@v5, upload-pages-artifact@v3, deploy-pages@v4. Newer majors exist (v6, v5,
  v5 respectively); the floating v3 tag of upload-pages-artifact was not confirmed on its releases page
  (`_agent/results/1247_actions_tags.txt`). If a run fails resolving it, use `@v3.0.1`.
