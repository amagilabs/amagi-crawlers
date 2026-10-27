---
name: amagi-crawlers
description: Check which AI crawlers (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended, CCBot, Bytespider, Meta-ExternalAgent and more) can reach a list of websites. Reads robots.txt the way the crawlers do (RFC 9309), reads X-Robots-Tag and robots meta opt-outs (noai, noimageai, noindex), notes llms.txt and TDMRep, and fetches each page with each bot's user agent to catch the case where robots.txt allows a bot but the firewall or CDN answers it with a 403 or a challenge. Writes a text table, CSV, markdown grid or JSON. Use when asked whether a site is blocking or allowing AI bots, why a site doesn't show up in ChatGPT/Claude/Perplexity answers, to audit AI-crawler policy across a client list, or to confirm a robots.txt change actually took effect.
---

# amagi-crawlers

## What this skill does

Runs the `amagi-crawlers` CLI. For each site it:

1. fetches `/robots.txt` and decides each bot's access with RFC 9309 rules: the bot's own
   `User-agent` groups merged, else `*`; longest path match wins; `Allow` wins a tie;
   a 404 means allow all; a 5xx, 429 or no answer means disallow all;
2. fetches the page (home page by default) with an ordinary Chrome user agent as a baseline;
3. fetches `/llms.txt` and reports `yes`, `no (404)` or `no (HTML page)` (a soft 404);
4. fetches the page again once per bot with that bot's published user agent, following redirects
   with the same user agent, and compares the answer to the baseline;
5. reads `X-Robots-Tag` headers (including bot-scoped ones like `GPTBot: noindex`), robots meta
   tags, per-bot meta tags, and `tdm-reservation`.

Each bot gets one verdict:

| Verdict | Meaning |
|---|---|
| `ALLOW` | robots.txt allows it and the server answers it |
| `ALLOW noai/...` | allowed, but the page opts out with a header or meta tag |
| `BLOCK robots` | robots.txt disallows it |
| `BLOCK robots+403` | robots.txt disallows it and the server refuses it too |
| `CONFLICT 403` / `CONFLICT challenge` | robots.txt allows it, the server refuses it, a browser gets through |
| `UNKNOWN` | robots.txt allows it, but the site also blocks the browser baseline, so a bot-specific block can't be told apart |
| `ERROR` | the site could not be reached |

`Google-Extended` and `Applebot-Extended` are robots.txt tokens only (Google and Apple fetch with
Googlebot and Applebot), so they get a robots.txt verdict and no HTTP check.

## How to use it

1. Check it's installed: `amagi-crawlers --version` (else `pipx install amagi-crawlers`).
2. To see sample output first, run it offline: `amagi-crawlers --demo`.
3. One site or a few:
   ```
   amagi-crawlers example.com
   amagi-crawlers example.com https://example.org/blog/post
   amagi-crawlers example.com --bots GPTBot,ClaudeBot,PerplexityBot
   ```
4. A client list, with files to hand over:
   ```
   amagi-crawlers -f clients.txt -o crawlers.md -o crawlers.csv
   ```
   `clients.txt` holds one domain or URL per line; `#` starts a comment.
5. Exit code 0 = no conflicts, 1 = at least one conflict, 2 = bad input or no site reachable.

## Reading the result for the user

- Lead with `CONFLICT` rows. They mean the site owner's stated policy (robots.txt) and what the
  server does disagree. Usually a WAF or CDN bot rule (Cloudflare "Block AI bots", Akamai, Imperva)
  is refusing a bot the owner meant to allow. If the owner wants to appear in ChatGPT search,
  Perplexity or Claude answers, the fix is in the firewall rules, not robots.txt.
- `BLOCK robots` on training bots (GPTBot, ClaudeBot, CCBot, Google-Extended) with `ALLOW` on
  search and user bots (OAI-SearchBot, ChatGPT-User, PerplexityBot, Claude-User) is a common,
  deliberate policy: no training, still citable in AI answers.
- `UNKNOWN` usually means Cloudflare or another bot manager challenges every non-browser client,
  including this checker. The result can't say anything about that bot; check the CDN's own
  bot settings instead.
- The tool sends each bot's user agent from your own IP. Real crawlers come from their operators'
  IP ranges, and some firewalls verify that, so a site can treat the real bot differently from
  this check. Say so when reporting an `ALLOW` on a site behind a bot manager.
- It reads only. Never change a client's robots.txt or firewall rules on the strength of this
  report without the owner's OK.

## Options worth knowing

| Option | Effect |
|---|---|
| `-f FILE` | read sites from a file (repeatable) |
| `--bots LIST` | comma list of tokens; unknown names get a robots.txt-only check |
| `--path /page` | check this path on every site instead of `/` |
| `--format text\|csv\|markdown\|json` | stdout format |
| `-o FILE` | also write a report; the extension (.csv .md .json .txt) picks the format (repeatable) |
| `--no-fetch` | robots.txt and page tags only, no per-bot requests |
| `--delay S`, `--timeout S`, `--workers N` | politeness and speed (defaults 0.3, 10, 4) |
| `--list-bots` | print the crawler catalog with the user agents used |
| `--demo` | three local sample sites, no internet |
