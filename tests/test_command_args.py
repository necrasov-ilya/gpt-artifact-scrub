from __future__ import annotations

from aiogram.filters.command import CommandObject

import pytest

from src.app.handlers.commands import _get_command_args, _is_logs_whitelisted


def test_get_command_args_handles_none() -> None:
    assert _get_command_args(None) == ""


def test_get_command_args_trims_whitespace() -> None:
    command = CommandObject(prefix="/", command="padding", args="   3   ")
    assert _get_command_args(command) == "3"


@pytest.mark.parametrize(
    "whitelist,user_id,expected",
    [
        (frozenset(), 123, False),
        (frozenset({123}), 123, True),
        (frozenset({123}), 456, False),
        (frozenset({123}), None, False),
    ],
)
def test_is_logs_whitelisted(whitelist: frozenset[int], user_id: int | None, expected: bool) -> None:
    assert _is_logs_whitelisted(user_id, whitelist) is expected
