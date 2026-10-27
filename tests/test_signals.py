from amagi_crawlers import signals
from amagi_crawlers.fetch import Response


def resp(status=200, headers=(), body=b"", ctype="text/html"):
    hs = [("content-type", ctype)] + [(k.lower(), v) for k, v in headers]
    return Response("https://site.example/", status, hs, body)


def test_x_robots_scopes():
    got = signals.x_robots(["noai, noimageai", "GPTBot: noindex, nofollow", "unavailable_after: 25 Jun 2030 15:00:00 PST"])
    assert got[""] == {"noai", "noimageai", "unavailable_after"}
    assert got["gptbot"] == {"noindex", "nofollow"}


def test_page_opt_outs_header_and_meta_scoped_to_bot():
    html = b'<html><head><meta name="robots" content="noai"><meta name="ClaudeBot" content="noindex"></head></html>'
    r = resp(headers=[("X-Robots-Tag", "GPTBot: none")], body=html)
    assert signals.page_opt_outs(r, "GPTBot") == ["noai (meta)", "none (header)"]
    assert signals.page_opt_outs(r, "ClaudeBot") == ["noai (meta)", "noindex (meta)"]
    assert signals.page_opt_outs(r, "CCBot") == ["noai (meta)"]


def test_page_opt_outs_ignore_unrelated_and_failed_pages():
    r = resp(body=b'<meta name="description" content="noai"><meta name="robots" content="index, follow">')
    assert signals.page_opt_outs(r, "GPTBot") == []
    assert signals.page_opt_outs(resp(status=403, body=b'<meta name="robots" content="noai">'), "GPTBot") == []
    assert signals.page_opt_outs(None, "GPTBot") == []


def test_meta_parser_survives_broken_html():
    assert signals.metas('<meta name="robots" content="noai"><div <<<') == [("robots", "noai")]


def test_tdm_reservation():
    assert signals.tdm_reserved(resp(headers=[("tdm-reservation", "1")]))
    assert signals.tdm_reserved(resp(body=b'<meta name="tdm-reservation" content="1">'))
    assert not signals.tdm_reserved(resp(body=b'<meta name="tdm-reservation" content="0">'))


def test_challenge_detection():
    assert signals.is_challenge(resp(403, [("cf-mitigated", "challenge")]))
    assert signals.is_challenge(resp(403, body=b"<html><title>Just a moment...</title></html>"))
    assert not signals.is_challenge(resp(403, body=b"<html><title>Forbidden</title></html>"))
    assert not signals.is_challenge(Response("https://x.example/", None, error="timeout"))


def test_vendor_fingerprints():
    assert signals.vendor(resp(headers=[("cf-ray", "abc-ATL")])) == "Cloudflare"
    assert signals.vendor(resp(headers=[("server", "AkamaiGHost")])) == "Akamai"
    assert signals.vendor(resp(headers=[("x-sucuri-id", "1")])) == "Sucuri"
    assert signals.vendor(resp(headers=[("x-amz-cf-id", "1")])) == "CloudFront"
    assert signals.vendor(resp(headers=[("x-served-by", "cache-atl1")])) == "Fastly"
    assert signals.vendor(resp(headers=[("server", "nginx")])) == ""


def test_is_html_sniffs_body_without_content_type():
    assert signals.is_html(Response("u", 200, [], b"  <!DOCTYPE html><html>"))
    assert not signals.is_html(Response("u", 200, [("content-type", "text/plain")], b"# llms.txt"))
