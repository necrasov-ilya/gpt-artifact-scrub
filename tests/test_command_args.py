from __future__ import annotations

from aiogram.filters.command import CommandObject

from src.app.handlers.commands import _get_command_args, _parse_key_value_args


def test_get_command_args_handles_none() -> None:
    assert _get_command_args(None) == ""


def test_get_command_args_trims_whitespace() -> None:
    command = CommandObject(prefix="/", command="settings", args="  grid=3x3 pad=2  ")
    assert _get_command_args(command) == "grid=3x3 pad=2"


def test_parse_key_value_args_normalizes_keys() -> None:
    args = "grid=3x3 PAD=4 extra=ignored"
    parsed = _parse_key_value_args(args)
    assert parsed == {"grid": "3x3", "pad": "4", "extra": "ignored"}


def test_parse_key_value_args_skips_invalid_tokens() -> None:
    args = "invalid grid=2x2 noequals pad=1"
    parsed = _parse_key_value_args(args)
    assert parsed == {"grid": "2x2", "pad": "1"}
