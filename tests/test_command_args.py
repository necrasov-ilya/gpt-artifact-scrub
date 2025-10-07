from __future__ import annotations

from aiogram.filters.command import CommandObject

import pytest

from src.app.handlers.commands import _get_command_args, _is_logs_admin, _parse_key_value_args


def test_get_command_args_handles_none() -> None:
    assert _get_command_args(None) == ""


def test_get_command_args_trims_whitespace() -> None:
    command = CommandObject(prefix="/", command="padding", args="  padding=3  ")
    assert _get_command_args(command) == "padding=3"


def test_parse_key_value_args_extracts_pairs() -> None:
    args = "padding=3 pad=1 extra=value"
    parsed = _parse_key_value_args(args)
    assert parsed == {"padding": "3", "pad": "1", "extra": "value"}


def test_parse_key_value_args_skips_invalid_tokens() -> None:
    args = "padding=3 invalid another=4 noequals"
    parsed = _parse_key_value_args(args)
    assert parsed == {"padding": "3", "another": "4"}


@pytest.mark.parametrize(
    "admins,user_id,expected",
    [
        (frozenset(), 123, False),
        (frozenset({123}), 123, True),
        (frozenset({123}), 456, False),
        (frozenset({123}), None, False),
    ],
)
def test_is_logs_admin(admins: frozenset[int], user_id: int | None, expected: bool) -> None:
    assert _is_logs_admin(user_id, admins) is expected
