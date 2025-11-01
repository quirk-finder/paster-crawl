"""Tests for text filters."""

from unfiltered_paste_index.utils.datetime import has_password_word, has_url


def test_has_url() -> None:
    assert has_url("visit http://example.com now")
    assert not has_url("no link here")


def test_has_password_word() -> None:
    assert has_password_word("password: 1234")
    assert has_password_word("合言葉は秘密")
    assert not has_password_word("no secret")
