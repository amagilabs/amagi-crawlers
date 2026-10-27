"""The AI crawlers amagi-crawlers knows about.

User-agent strings were checked against each operator's own documentation on 2026-10-27
(``source="published"``). Where an operator documents the robots.txt token but not the full
user-agent header, the header follows the operator's other published bots and is marked
``source="pattern"``. WAF rules match on the token (``GPTBot``, ``ClaudeBot``), not on the
rest of the string.

Google-Extended and Applebot-Extended are robots.txt tokens only. Google and Apple crawl with
Googlebot and Applebot, and read those tokens to decide whether the content may be used for AI,
so there is no separate user agent to fetch with (``ua=None``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# A current desktop Chrome. Used for the baseline fetch, robots.txt and llms.txt.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TRAINING = "training"
SEARCH = "search"
USER = "user"


@dataclass(frozen=True)
class Bot:
    token: str            # the name robots.txt rules use
    operator: str
    use: str              # training | search | user
    ua: Optional[str]     # None = robots.txt token only, nothing to fetch with
    source: str = "published"  # published | pattern | token-only
    note: str = ""


BOTS = [
    Bot("GPTBot", "OpenAI", TRAINING,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.4; +https://openai.com/gptbot"),
    Bot("OAI-SearchBot", "OpenAI", SEARCH,
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36; compatible; OAI-SearchBot/1.4; +https://openai.com/searchbot"),
    Bot("ChatGPT-User", "OpenAI", USER,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"),
    Bot("ClaudeBot", "Anthropic", TRAINING,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)"),
    Bot("Claude-SearchBot", "Anthropic", SEARCH,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +https://www.anthropic.com)",
        source="pattern"),
    Bot("Claude-User", "Anthropic", USER,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +https://www.anthropic.com)",
        source="pattern"),
    Bot("PerplexityBot", "Perplexity", SEARCH,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
    Bot("Perplexity-User", "Perplexity", USER,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)"),
    Bot("Google-Extended", "Google", TRAINING, None, source="token-only",
        note="robots.txt token only; Google fetches with Googlebot"),
    Bot("Applebot-Extended", "Apple", TRAINING, None, source="token-only",
        note="robots.txt token only; Apple fetches with Applebot"),
    Bot("CCBot", "Common Crawl", TRAINING, "CCBot/2.0 (https://commoncrawl.org/faq/)"),
    Bot("Bytespider", "ByteDance", TRAINING,
        "Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 "
        "(compatible; Bytespider; spider-feedback@bytedance.com)"),
    Bot("Meta-ExternalAgent", "Meta", TRAINING,
        "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    Bot("Amazonbot", "Amazon", SEARCH,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amazonbot/0.1) Chrome/131.0.0.0 Safari/537.36"),
    Bot("DuckAssistBot", "DuckDuckGo", SEARCH,
        "DuckAssistBot/1.2; (+http://duckduckgo.com/duckassistbot.html)"),
    Bot("MistralAI-User", "Mistral", USER,
        "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; MistralAI-User/1.0; +https://docs.mistral.ai/robots)"),
]

BY_TOKEN = {b.token.lower(): b for b in BOTS}


def select(names: Optional[str]) -> list:
    """Pick bots from a comma list ("GPTBot,claudebot"), case-insensitive. None = all.

    A name that is not in the catalog becomes a robots.txt-only token, so any crawler can be
    checked against robots.txt and meta tags even if we hold no user agent for it.
    """
    if not names:
        return list(BOTS)
    out = []
    for raw in names.split(","):
        name = raw.strip()
        if not name:
            continue
        bot = BY_TOKEN.get(name.lower()) or Bot(name, "?", "?", None, source="token-only",
                                                 note="not in the catalog; robots.txt and meta only")
        if bot not in out:
            out.append(bot)
    return out
