from amagi_crawlers.bots import BOTS, BY_TOKEN, select
from amagi_crawlers.check import (ALLOW, BOTH, CONFLICT, ERROR, OPT_OUT, ROBOTS, UNKNOWN, Target,
                                  check_site, verdict_for)

HTML = [("Content-Type", "text/html")]
TEXT = [("Content-Type", "text/plain")]


def run(url, bots=None, **kw):
    return check_site(Target.parse(url), select(bots), delay=0, timeout=5, **kw)


def by_bot(site):
    return {b.bot.token: b for b in site.bots}


def test_target_parse():
    t = Target.parse("Example.com")
    assert (t.label, t.base, t.path) == ("example.com", "https://example.com", "/")
    t = Target.parse("http://127.0.0.1:8080/blog/post?x=1")
    assert (t.label, t.base, t.path) == ("127.0.0.1:8080", "http://127.0.0.1:8080", "/blog/post?x=1")
    assert Target.parse("example.com/blog", path="/").path == "/"


def test_verdict_table():
    assert verdict_for(True, False, []) == ALLOW
    assert verdict_for(True, False, ["noai (meta)"]) == OPT_OUT
    assert verdict_for(False, False, []) == ROBOTS
    assert verdict_for(False, True, []) == BOTH
    assert verdict_for(True, True, []) == CONFLICT
    assert verdict_for(True, None, [], baseline_ok=False, fetched=True) == UNKNOWN
    assert verdict_for(False, None, [], baseline_ok=False, fetched=True) == ROBOTS


def test_shop_blocks_training_allows_search(demo):
    site = run(demo["shop.example"].url)
    r = by_bot(site)
    assert site.llms_txt == "yes" and site.robots_status == "200"
    for token in ("GPTBot", "ClaudeBot", "CCBot", "Bytespider", "Meta-ExternalAgent"):
        assert r[token].verdict == ROBOTS and r[token].http == "200", token
    for token in ("Google-Extended", "Applebot-Extended"):
        assert r[token].verdict == ROBOTS and r[token].http == "-", token
    for token in ("OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Claude-User", "DuckAssistBot"):
        assert r[token].verdict == ALLOW, token
    assert r["GPTBot"].robots_rule == "Disallow: / (own group)"
    assert site.conflicts == []


def test_news_firewall_contradicts_robots(demo):
    site = run(demo["news.example"].url)
    r = by_bot(site)
    assert site.vendor == "Cloudflare" and site.llms_txt == "no (HTML page)"
    assert {b.bot.token for b in site.conflicts} == {
        "GPTBot", "ClaudeBot", "PerplexityBot", "Bytespider", "Perplexity-User"}
    assert r["GPTBot"].label == "CONFLICT 403"
    assert r["Perplexity-User"].label == "CONFLICT challenge"
    assert r["GPTBot"].note == "browser gets 200, this bot gets 403 (Cloudflare)"
    assert r["OAI-SearchBot"].verdict == ALLOW


def test_blog_page_opt_outs(demo):
    site = run(demo["blog.example"].url)
    r = by_bot(site)
    assert site.robots_status == "404 (no robots.txt)" and site.tdm_reserved
    assert r["GPTBot"].verdict == OPT_OUT
    assert r["GPTBot"].label == "ALLOW noai/noimageai/noindex"
    assert r["ClaudeBot"].label == "ALLOW noai/noimageai"
    assert r["ClaudeBot"].robots_rule == "no robots.txt"


def test_robots_disallow_plus_server_block(serve):
    def route(path, ua):
        if "GPTBot" in ua:
            return 403, HTML, "denied"
        if path == "/robots.txt":
            return 200, TEXT, "User-agent: GPTBot\nDisallow: /\n"
        return 200, HTML, "<html>ok</html>"
    r = by_bot(run(serve(route).url, "GPTBot,ClaudeBot"))
    assert r["GPTBot"].verdict == BOTH and r["GPTBot"].label == "BLOCK robots+403"
    assert r["ClaudeBot"].verdict == ALLOW


def test_robots_5xx_means_disallow_all(serve):
    def route(path, ua):
        if path == "/robots.txt":
            return 503, TEXT, "busy"
        return 200, HTML, "<html>ok</html>"
    site = run(serve(route).url, "GPTBot")
    assert site.robots_status == "503 (treated as disallow all)"
    assert site.bots[0].verdict == ROBOTS


def test_robots_403_is_unreadable_and_allows(serve):
    def route(path, ua):
        if path == "/robots.txt":
            return 403, TEXT, "no"
        return 200, HTML, "<html>ok</html>"
    site = run(serve(route).url, "GPTBot")
    assert site.robots_status.startswith("403 (unreadable")
    assert site.bots[0].robots_rule == "robots.txt unreadable (403)"
    assert site.bots[0].verdict == ALLOW


def test_site_blocking_everyone_gives_unknown_not_conflict(serve):
    def route(path, ua):
        if "GPTBot" in ua:
            return 403, HTML, "<html><title>Forbidden</title></html>"
        return 403, [("cf-mitigated", "challenge")] + HTML, "<title>Just a moment...</title>"
    site = run(serve(route).url, "GPTBot,OAI-SearchBot,Google-Extended")
    r = by_bot(site)
    assert not site.baseline_ok and site.baseline == "challenge"
    assert r["GPTBot"].verdict == UNKNOWN and r["GPTBot"].label == "UNKNOWN"
    assert r["GPTBot"].note == ("the site blocks this checker too (browser gets challenge); "
                                "this bot gets 403 instead")
    assert r["OAI-SearchBot"].note == "the site blocks this checker too (browser gets challenge)"
    assert r["Google-Extended"].verdict == ALLOW
    assert site.conflicts == []


def test_dropped_connection_for_one_bot_is_a_conflict(serve):
    def route(path, ua):
        if "ClaudeBot" in ua:
            return 200, HTML, None
        if path == "/robots.txt":
            return 404, TEXT, "nope"
        return 200, HTML, "<html>ok</html>"
    r = by_bot(run(serve(route).url, "ClaudeBot"))
    assert r["ClaudeBot"].verdict == CONFLICT
    assert r["ClaudeBot"].http_status is None


def test_redirects_are_followed_with_the_bot_user_agent(serve):
    def route(path, ua):
        if path == "/robots.txt":
            return 200, TEXT, "User-agent: *\nAllow: /\n"
        if path == "/":
            return 301, [("Location", "/home")], ""
        if path == "/home" and "GPTBot" in ua:
            return 403, HTML, "denied"
        return 200, HTML, "<html>home</html>"
    s = serve(route)
    r = by_bot(run(s.url, "GPTBot"))
    assert r["GPTBot"].verdict == CONFLICT
    assert ("/home", BY_TOKEN["gptbot"].ua) in s.seen


def test_no_fetch_skips_bot_requests(serve):
    def route(path, ua):
        if path == "/robots.txt":
            return 200, TEXT, "User-agent: *\nDisallow: /\n"
        return 200, HTML, "<html>ok</html>"
    s = serve(route)
    site = run(s.url, fetch_bots=False)
    assert len(s.seen) == 3  # robots.txt, the page, llms.txt
    assert all(b.http == "-" and b.verdict == ROBOTS for b in site.bots)


def test_unreachable_site_is_error(dead_url):
    site = run(dead_url, "GPTBot")
    assert site.error == "connection refused"
    assert site.bots[0].verdict == ERROR and site.bots[0].label == "ERROR"


def test_unknown_bot_name_is_robots_only(demo):
    r = by_bot(run(demo["shop.example"].url, "SomeNewBot,GPTBot"))
    assert r["SomeNewBot"].http == "-" and r["SomeNewBot"].verdict == ALLOW
    assert r["GPTBot"].verdict == ROBOTS


def test_catalog_is_consistent():
    tokens = [b.token.lower() for b in BOTS]
    assert len(tokens) == len(set(tokens))
    for b in BOTS:
        assert b.use in ("training", "search", "user")
        if b.ua is None:
            assert b.source == "token-only"
        else:
            assert b.token.lower() in b.ua.lower()
