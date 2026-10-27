import csv
import io
import json

import pytest

from amagi_crawlers import __version__
from amagi_crawlers.cli import main

FEW = "GPTBot,ClaudeBot,PerplexityBot,Perplexity-User,Google-Extended"


def test_demo_reports_conflicts_and_exits_1(capsys):
    assert main(["--demo", "--bots", FEW]) == 1
    out = capsys.readouterr().out
    assert "news.example" in out and "CONFLICT 403" in out and "CONFLICT challenge" in out
    assert "3 sites, 15 bot checks" in out


def test_demo_writes_csv_markdown_and_json(tmp_path, capsys):
    csv_path, md_path, js_path = tmp_path / "r.csv", tmp_path / "r.md", tmp_path / "r.json"
    rc = main(["--demo", "-q", "--bots", FEW, "-o", str(csv_path), "-o", str(md_path), "-o", str(js_path)])
    assert rc == 1
    assert capsys.readouterr().out == ""

    rows = list(csv.DictReader(io.StringIO(csv_path.read_text(encoding="utf-8"))))
    assert len(rows) == 15
    gpt_news = next(r for r in rows if r["site"] == "news.example" and r["bot"] == "GPTBot")
    assert gpt_news["verdict"] == "conflict" and gpt_news["http"] == "403"

    md = md_path.read_text(encoding="utf-8")
    assert md.startswith("# ") and "| Site |" in md and "**CONFLICT 403**" in md

    data = json.loads(js_path.read_text(encoding="utf-8"))
    news = next(s for s in data["sites"] if s["site"] == "news.example")
    assert news["vendor"] == "Cloudflare"


def test_format_flag_controls_stdout(capsys):
    assert main(["--demo", "--bots", "GPTBot", "--format", "csv"]) == 1
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("site,")


def test_no_fetch_finds_no_conflicts(capsys):
    assert main(["--demo", "--no-fetch", "--bots", FEW]) == 0
    assert "CONFLICT" not in capsys.readouterr().out.split("conflicts")[0]


def test_sites_from_file_and_bad_file(tmp_path, demo, capsys):
    f = tmp_path / "sites.txt"
    f.write_text("# my sites\n%s   # shop\n\n" % demo["shop.example"].url, encoding="utf-8")
    assert main(["-f", str(f), "--bots", "GPTBot", "--delay", "0"]) == 0
    assert "BLOCK robots" in capsys.readouterr().out
    assert main(["-f", str(tmp_path / "missing.txt")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_no_sites_is_a_usage_error(capsys):
    assert main([]) == 2
    assert "--demo" in capsys.readouterr().err


def test_bad_numbers_are_usage_errors(capsys):
    assert main(["--demo", "--workers", "0"]) == 2


def test_all_sites_unreachable_exits_2(dead_url, capsys):
    assert main([dead_url, "--bots", "GPTBot"]) == 2
    out = capsys.readouterr().out
    assert "unreachable: connection refused" in out
    assert "1 not checked (site unreachable)" in out and "unknown" not in out


def test_list_bots(capsys):
    assert main(["--list-bots"]) == 0
    out = capsys.readouterr().out
    for token in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"):
        assert token in out


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out
