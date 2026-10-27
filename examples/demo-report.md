# AI crawler access report

Checked 2026-10-27T19:01:25Z with amagi-crawlers 0.1.0. 3 sites, 48 bot checks: 36 allowed, 7 blocked by robots.txt, 5 refused by the server, 5 conflicts.

| Site | robots.txt | llms.txt | GPTBot | OAI-SearchBot | ChatGPT-User | ClaudeBot | Claude-SearchBot | Claude-User | PerplexityBot | Perplexity-User | Google-Extended | Applebot-Extended | CCBot | Bytespider | Meta-ExternalAgent | Amazonbot | DuckAssistBot | MistralAI-User |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| shop.example | 200 | yes | BLOCK robots | ALLOW | ALLOW | BLOCK robots | ALLOW | ALLOW | ALLOW | ALLOW | BLOCK robots | BLOCK robots | BLOCK robots | BLOCK robots | BLOCK robots | ALLOW | ALLOW | ALLOW |
| news.example | 200 | no (HTML page) | **CONFLICT 403** | ALLOW | ALLOW | **CONFLICT 403** | ALLOW | ALLOW | **CONFLICT 403** | **CONFLICT challenge** | ALLOW | ALLOW | ALLOW | **CONFLICT 403** | ALLOW | ALLOW | ALLOW | ALLOW |
| blog.example | 404 (no robots.txt) | no (404) | ALLOW noai/noimageai/noindex | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai | ALLOW noai/noimageai |

ALLOW = robots.txt allows the bot and the server answers it. BLOCK robots = robots.txt disallows it. CONFLICT = robots.txt allows it but the server refuses that user agent (403, a challenge page, or a dropped connection) while a browser gets through. ALLOW noai/noindex = allowed, but the page opts out with an X-Robots-Tag header or robots meta tag. UNKNOWN = robots.txt allows it, but the site also blocks a plain browser request from this checker, so a bot-specific block cannot be told apart. ERROR = the site could not be reached.

## Conflicts

- **news.example**, GPTBot: robots.txt `allowed (*)`, browser gets 200, this bot gets 403 (Cloudflare)
- **news.example**, ClaudeBot: robots.txt `allowed (*)`, browser gets 200, this bot gets 403 (Cloudflare)
- **news.example**, PerplexityBot: robots.txt `allowed (*)`, browser gets 200, this bot gets 403 (Cloudflare)
- **news.example**, Perplexity-User: robots.txt `allowed (*)`, browser gets 200, this bot gets challenge (Cloudflare)
- **news.example**, Bytespider: robots.txt `allowed (*)`, browser gets 200, this bot gets 403 (Cloudflare)

## shop.example

URL `http://127.0.0.1:62136/`. robots.txt 200, llms.txt yes, browser baseline 200.

| Bot | Operator | Use | robots.txt | HTTP | Page opt-outs | Verdict | Note |
|---|---|---|---|---|---|---|---|
| GPTBot | OpenAI | training | Disallow: / (own group) | 200 | - | BLOCK robots | - |
| OAI-SearchBot | OpenAI | search | Allow: / (*) | 200 | - | ALLOW | - |
| ChatGPT-User | OpenAI | user | Allow: / (*) | 200 | - | ALLOW | - |
| ClaudeBot | Anthropic | training | Disallow: / (own group) | 200 | - | BLOCK robots | - |
| Claude-SearchBot | Anthropic | search | Allow: / (*) | 200 | - | ALLOW | - |
| Claude-User | Anthropic | user | Allow: / (*) | 200 | - | ALLOW | - |
| PerplexityBot | Perplexity | search | Allow: / (*) | 200 | - | ALLOW | - |
| Perplexity-User | Perplexity | user | Allow: / (*) | 200 | - | ALLOW | - |
| Google-Extended | Google | training | Disallow: / (own group) | - | - | BLOCK robots | robots.txt token only; Google fetches with Googlebot |
| Applebot-Extended | Apple | training | Disallow: / (own group) | - | - | BLOCK robots | robots.txt token only; Apple fetches with Applebot |
| CCBot | Common Crawl | training | Disallow: / (own group) | 200 | - | BLOCK robots | - |
| Bytespider | ByteDance | training | Disallow: / (own group) | 200 | - | BLOCK robots | - |
| Meta-ExternalAgent | Meta | training | Disallow: / (own group) | 200 | - | BLOCK robots | - |
| Amazonbot | Amazon | search | Allow: / (*) | 200 | - | ALLOW | - |
| DuckAssistBot | DuckDuckGo | search | Allow: / (*) | 200 | - | ALLOW | - |
| MistralAI-User | Mistral | user | Allow: / (*) | 200 | - | ALLOW | - |

## news.example

URL `http://127.0.0.1:62137/`. robots.txt 200, llms.txt no (HTML page), browser baseline 200 (Cloudflare).

| Bot | Operator | Use | robots.txt | HTTP | Page opt-outs | Verdict | Note |
|---|---|---|---|---|---|---|---|
| GPTBot | OpenAI | training | allowed (*) | 403 | - | CONFLICT 403 | browser gets 200, this bot gets 403 (Cloudflare) |
| OAI-SearchBot | OpenAI | search | allowed (*) | 200 | - | ALLOW | - |
| ChatGPT-User | OpenAI | user | allowed (*) | 200 | - | ALLOW | - |
| ClaudeBot | Anthropic | training | allowed (*) | 403 | - | CONFLICT 403 | browser gets 200, this bot gets 403 (Cloudflare) |
| Claude-SearchBot | Anthropic | search | allowed (*) | 200 | - | ALLOW | - |
| Claude-User | Anthropic | user | allowed (*) | 200 | - | ALLOW | - |
| PerplexityBot | Perplexity | search | allowed (*) | 403 | - | CONFLICT 403 | browser gets 200, this bot gets 403 (Cloudflare) |
| Perplexity-User | Perplexity | user | allowed (*) | challenge | - | CONFLICT challenge | browser gets 200, this bot gets challenge (Cloudflare) |
| Google-Extended | Google | training | allowed (*) | - | - | ALLOW | robots.txt token only; Google fetches with Googlebot |
| Applebot-Extended | Apple | training | allowed (*) | - | - | ALLOW | robots.txt token only; Apple fetches with Applebot |
| CCBot | Common Crawl | training | allowed (*) | 200 | - | ALLOW | - |
| Bytespider | ByteDance | training | allowed (*) | 403 | - | CONFLICT 403 | browser gets 200, this bot gets 403 (Cloudflare) |
| Meta-ExternalAgent | Meta | training | allowed (*) | 200 | - | ALLOW | - |
| Amazonbot | Amazon | search | allowed (*) | 200 | - | ALLOW | - |
| DuckAssistBot | DuckDuckGo | search | allowed (*) | 200 | - | ALLOW | - |
| MistralAI-User | Mistral | user | allowed (*) | 200 | - | ALLOW | - |

## blog.example

URL `http://127.0.0.1:62138/`. robots.txt 404 (no robots.txt), llms.txt no (404), browser baseline 200, tdm-reservation: 1.

| Bot | Operator | Use | robots.txt | HTTP | Page opt-outs | Verdict | Note |
|---|---|---|---|---|---|---|---|
| GPTBot | OpenAI | training | no robots.txt | 200 | noai (meta), noimageai (meta), noindex (header) | ALLOW noai/noimageai/noindex | - |
| OAI-SearchBot | OpenAI | search | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| ChatGPT-User | OpenAI | user | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| ClaudeBot | Anthropic | training | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| Claude-SearchBot | Anthropic | search | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| Claude-User | Anthropic | user | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| PerplexityBot | Perplexity | search | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| Perplexity-User | Perplexity | user | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| Google-Extended | Google | training | no robots.txt | - | noai (meta), noimageai (meta) | ALLOW noai/noimageai | robots.txt token only; Google fetches with Googlebot |
| Applebot-Extended | Apple | training | no robots.txt | - | noai (meta), noimageai (meta) | ALLOW noai/noimageai | robots.txt token only; Apple fetches with Applebot |
| CCBot | Common Crawl | training | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| Bytespider | ByteDance | training | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| Meta-ExternalAgent | Meta | training | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| Amazonbot | Amazon | search | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| DuckAssistBot | DuckDuckGo | search | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
| MistralAI-User | Mistral | user | no robots.txt | 200 | noai (meta), noimageai (meta) | ALLOW noai/noimageai | - |
