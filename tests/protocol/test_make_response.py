"""Tests for the make_response convenience helper."""

from datetime import datetime, timezone

import pytest

from agent_protocol.envelope import make_response


def test_make_response_happy_path():
    result = make_response(
        data={"id": "p1", "name": "Alice"},
        self_link="/people/p1",
        related=["/people"],
        suggested_next=[{"rel": "create", "href": "/people", "verb": "POST"}],
    )
    assert result["data"] == {"id": "p1", "name": "Alice"}
    assert result["_self"] == "/people/p1"
    assert result["_related"] == ["/people"]
    assert result["_suggested_next"] == [{"rel": "create", "href": "/people", "verb": "POST"}]
    assert "_generated_at" in result


def test_make_response_defaults_related_and_suggested_next():
    result = make_response(data={"id": "p1"}, self_link="/people/p1")
    assert result["_related"] == []
    assert result["_suggested_next"] == []


def test_make_response_correct_underscored_keys():
    result = make_response(data={}, self_link="/")
    expected_keys = {"data", "_self", "_related", "_suggested_next", "_generated_at"}
    assert set(result.keys()) == expected_keys


def test_make_response_generated_at_is_iso8601():
    result = make_response(data={}, self_link="/")
    generated_at = result["_generated_at"]
    # Must be parseable as an ISO-8601 datetime
    parsed = datetime.fromisoformat(generated_at)
    assert parsed.tzinfo is not None


def test_make_response_suggested_next_is_list():
    result = make_response(
        data={},
        self_link="/",
        suggested_next=[{"rel": "next", "href": "/page/2", "verb": "GET"}],
    )
    assert isinstance(result["_suggested_next"], list)
    assert result["_suggested_next"][0]["rel"] == "next"


def test_make_response_none_related_becomes_empty_list():
    result = make_response(data={}, self_link="/", related=None)
    assert result["_related"] == []


def test_make_response_none_suggested_next_becomes_empty_list():
    result = make_response(data={}, self_link="/", suggested_next=None)
    assert result["_suggested_next"] == []
