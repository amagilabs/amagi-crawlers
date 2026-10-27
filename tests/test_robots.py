from amagi_crawlers.robots import Robots, product_token


def decide(text, token, path="/"):
    return Robots.parse(text).decide(token, path)


def test_own_group_beats_star():
    txt = "User-agent: *\nDisallow: /\n\nUser-agent: GPTBot\nAllow: /\n"
    assert decide(txt, "GPTBot").allowed
    assert not decide(txt, "ClaudeBot").allowed


def test_star_not_merged_into_own_group():
    # RFC 9309: a bot with its own group ignores the * group entirely
    txt = "User-agent: *\nDisallow: /private\n\nUser-agent: GPTBot\nDisallow: /drafts\n"
    assert decide(txt, "GPTBot", "/private/x").allowed
    assert not decide(txt, "GPTBot", "/drafts/x").allowed


def test_grouped_user_agents_share_rules():
    txt = "User-agent: GPTBot\nUser-agent: CCBot\nDisallow: /\n"
    assert not decide(txt, "GPTBot").allowed
    assert not decide(txt, "CCBot").allowed
    assert decide(txt, "ClaudeBot").allowed


def test_same_agent_groups_are_merged():
    txt = "User-agent: GPTBot\nDisallow: /a\n\nUser-agent: other\nDisallow: /\n\nUser-agent: gptbot\nDisallow: /b\n"
    r = Robots.parse(txt)
    assert not r.decide("GPTBot", "/a").allowed
    assert not r.decide("GPTBot", "/b").allowed
    assert r.decide("GPTBot", "/c").allowed


def test_case_insensitive_token_and_version_suffix():
    txt = "User-agent: gptbot/1.1\nDisallow: /\n"
    assert not decide(txt, "GPTBot").allowed
    assert product_token("GPTBot/1.1 (+https://openai.com/gptbot)") == "gptbot"


def test_longest_match_wins():
    txt = "User-agent: *\nDisallow: /docs\nAllow: /docs/public\n"
    assert not decide(txt, "x", "/docs/secret").allowed
    assert decide(txt, "x", "/docs/public/page").allowed


def test_allow_wins_a_tie():
    txt = "User-agent: *\nDisallow: /page\nAllow: /page\n"
    assert decide(txt, "x", "/page").allowed


def test_wildcard_and_end_anchor():
    txt = "User-agent: *\nDisallow: /*.pdf$\nDisallow: /search*q=\n"
    assert not decide(txt, "x", "/files/report.pdf").allowed
    assert decide(txt, "x", "/files/report.pdf?dl=1").allowed
    assert not decide(txt, "x", "/search?lang=en&q=tents").allowed
    assert decide(txt, "x", "/searching").allowed


def test_empty_disallow_is_not_a_rule():
    txt = "User-agent: GPTBot\nDisallow:\n\nUser-agent: *\nDisallow: /\n"
    d = decide(txt, "GPTBot")
    assert d.allowed and d.group == "GPTBot" and d.rule is None


def test_no_matching_group_and_no_star_allows():
    d = decide("User-agent: CCBot\nDisallow: /\n", "GPTBot")
    assert d.allowed and d.group == "" and d.explain() == "no rules for this bot"


def test_robots_txt_itself_always_allowed():
    assert decide("User-agent: *\nDisallow: /\n", "x", "/robots.txt").allowed


def test_comments_crlf_bom_and_rules_before_any_agent():
    txt = "﻿Disallow: /ignored\r\n# comment\r\nUser-agent: * # everyone\r\nDisallow: /tmp # temp\r\n"
    r = Robots.parse(txt)
    assert r.decide("x", "/ignored").allowed
    assert not r.decide("x", "/tmp/a").allowed


def test_crawl_delay_does_not_split_a_group():
    txt = "User-agent: a\nCrawl-delay: 10\nUser-agent: b\nDisallow: /\n"
    assert not decide(txt, "a").allowed and not decide(txt, "b").allowed


def test_path_without_leading_slash():
    assert not decide("User-agent: *\nDisallow: private\n", "x", "/private").allowed


def test_percent_encoding_normalised():
    txt = "User-agent: *\nDisallow: /caf%c3%a9\n"
    assert not decide(txt, "x", "/café").allowed


def test_explain_and_names_and_sitemaps():
    txt = "User-agent: GPTBot\nDisallow: /\nUser-agent: *\nAllow: /\nSitemap: https://shop.example/sitemap.xml\n"
    r = Robots.parse(txt)
    assert r.decide("GPTBot").explain() == "Disallow: / (own group)"
    assert r.decide("ClaudeBot").explain() == "Allow: / (*)"
    assert r.names() == ["GPTBot", "*"]
    assert r.sitemaps == ["https://shop.example/sitemap.xml"]
