import pytest

from root_agent.cli import _parse_inputs, build_parser


def test_parse_inputs():
    assert _parse_inputs(["a=b", "c=d=e"]) == {"a": "b", "c": "d=e"}


def test_parse_inputs_rejects_bad_pair():
    with pytest.raises(SystemExit):
        _parse_inputs(["bad"])


def test_parser_ask():
    args = build_parser().parse_args(["ask", "hello world", "--input", "x=1"])
    assert args.command == "ask"
    assert args.request == "hello world"
    assert args.input == ["x=1"]


def test_parser_remember_tiers():
    args = build_parser().parse_args(["remember", "note", "--local"])
    assert args.command == "remember"
    assert args.local is True


def test_parser_global_url_and_insecure():
    args = build_parser().parse_args(["--url", "https://h:9", "--insecure", "agents"])
    assert args.url == "https://h:9"
    assert args.insecure is True
