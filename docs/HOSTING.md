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

## c. DNS for yomikoe.app at Cloudflare

Both domains use Cloudflare for DNS. Cloudflare dashboard facts below are from fetched pages
(`_agent/results/1261_cloudflare_docs.txt`); GitHub facts from `_agent/results/1260_github_proxy.txt` and
`_agent/results/1248_pages_dns.txt`.

1. Log in to the Cloudflare dashboard, click the domain `yomikoe.app`, open **DNS** > **Records**.
2. Delete any existing A, AAAA or CNAME record whose name is `@` (a leftover or parking record). No `www` record: the
   brand prints the bare domain.
3. Click **Add record** eight times, one per row below. For each: choose the Type, type `@` as the Name, paste the
   value, set **Proxy status** to **DNS only** (grey cloud), TTL Auto, Save.

| Type | Name | Value | Proxy status |
|---|---|---|---|
| A | @ | 185.199.108.153 | DNS only |
| A | @ | 185.199.109.153 | DNS only |
| A | @ | 185.199.110.153 | DNS only |
| A | @ | 185.199.111.153 | DNS only |
| AAAA | @ | 2606:50c0:8000::153 | DNS only |
| AAAA | @ | 2606:50c0:8001::153 | DNS only |
| AAAA | @ | 2606:50c0:8002::153 | DNS only |
| AAAA | @ | 2606:50c0:8003::153 | DNS only |

Why DNS only: Cloudflare says that with DNS only "Cloudflare responds with your server's actual IP address", while
proxied records answer with "Cloudflare anycast IP addresses" (results 1261, item 4). GitHub's DNS check compares the
answer to the GitHub Pages addresses ("Confirm that the results match the IP addresses for GitHub Pages"), and GitHub's
pages do not mention proxies or CDNs at all (results 1260). So the documentation does not settle whether a proxied
record works with GitHub Pages; use DNS only (grey cloud) until the certificate is issued. Everything beyond that is
unverified.

After GitHub shows the certificate (up to about an hour after DNS works, per GitHub's troubleshooting page), tick
"Enforce HTTPS" (section b). Leave the records grey. If you later turn the orange cloud on anyway (unverified that it
works with GitHub Pages), set **SSL/TLS** > **Overview** to **Full** or **Full (strict)**: Cloudflare's Flexible mode
talks to the origin without HTTPS, and Cloudflare's too-many-redirects page says to "update your SSL/TLS Encryption
Mode to be Full or higher" (results 1261, items 5 and 6). If you use CAA records, one must be `letsencrypt.org`
(results 1260).

Verify (DNS can take minutes to hours to propagate):

```
dig +short yomikoe.app
dig +short AAAA yomikoe.app
curl -sI https://yomikoe.app | head -5
```

The first should list the four A addresses, the second the four AAAA addresses, the third should start with `HTTP/2 200`.

## d. getyomikoe.com redirects (301) to yomikoe.app

Cloudflare only. Cloudflare's own tutorial for redirecting one domain to another (results 1261, item 3) needs a
proxied DNS record so the rule has traffic to act on.

1. Cloudflare dashboard > click the domain `getyomikoe.com` > **DNS** > **Records** > **Add record**.
2. Type A, Name `@`, IPv4 address `192.0.2.1`, Proxy status **Proxied** (orange cloud), Save. Cloudflare's docs say this
   address "doesn't route to an origin server"; it only lets Cloudflare apply rules to incoming traffic.
3. Add a second record: Type A, Name `www`, IPv4 address `192.0.2.1`, **Proxied**, Save. (An AAAA record with `100::` is
   the documented IPv6 equivalent; not needed for the redirect.)
4. Go to the Rules **Overview** page (in the domain's left menu), select **Create rule** > **Redirect Rule**.
5. Rule name: `getyomikoe to yomikoe.app`. Under **When incoming requests match** choose **Custom filter expression**
   and use the expression editor with
   `(http.host eq "getyomikoe.com") or (http.host eq "www.getyomikoe.com")`.
6. Under **Then**: choose a static redirect, Target URL `https://yomikoe.app`, Status code `301`, and leave
   **Preserve query string** off (path is not forwarded with a static target). Select **Deploy**.

Unverified: the exact labels of the "static" choice and the status-code dropdown, and the Custom filter expression
option's `or` form for two hostnames (the fetched page lists the fields and a single-host example, not these
details; results 1261, items 2 and 3). The rule is a Cloudflare dashboard setting, not code.

Verify:

```
curl -sI https://getyomikoe.com | grep -i "^location\|^HTTP"
curl -sI https://www.getyomikoe.com | grep -i "^location\|^HTTP"
```

Expected: `HTTP/... 301` and `location: https://yomikoe.app` (with or without a trailing slash).

## e. Later phases

app., api. and backups: not planned yet; see PRD item 9 gate (b)-(d).

## Notes

- Action pins in the workflow: configure-pages@v5, upload-pages-artifact@v3, deploy-pages@v4. Newer majors exist (v6, v5,
  v5 respectively); the floating v3 tag of upload-pages-artifact was not confirmed on its releases page
  (`_agent/results/1247_actions_tags.txt`). If a run fails resolving it, use `@v3.0.1`.
