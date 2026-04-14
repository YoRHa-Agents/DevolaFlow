"""Tests for devolaflow.template_engine.nines_bridge."""

from __future__ import annotations

from devolaflow.template_engine.nines_bridge import (
    extract_nines_commands,
    format_nines_context,
    nines_commands_to_dispatch_context,
)


class TestExtractNinesCommands:
    def test_none_config(self) -> None:
        assert extract_nines_commands(None) == []

    def test_empty_config(self) -> None:
        assert extract_nines_commands({}) == []

    def test_no_nines_commands_key(self) -> None:
        assert extract_nines_commands({"other": "value"}) == []

    def test_single_string_command(self) -> None:
        config = {"nines_commands": "nines -f json collect --source github"}
        result = extract_nines_commands(config)
        assert result == ["nines -f json collect --source github"]

    def test_list_of_commands(self) -> None:
        config = {
            "nines_commands": [
                "nines -f json collect --source github",
                "nines -f json analyze --target-path .",
            ]
        }
        result = extract_nines_commands(config)
        assert len(result) == 2
        assert "collect" in result[0]
        assert "analyze" in result[1]

    def test_non_string_list_items(self) -> None:
        config = {"nines_commands": [123, True]}
        result = extract_nines_commands(config)
        assert result == ["123", "True"]


class TestFormatNinesContext:
    def test_empty_commands(self) -> None:
        assert format_nines_context([]) == ""

    def test_with_commands_no_stage(self) -> None:
        result = format_nines_context(["nines -f json collect"])
        assert "NineS commands:" in result
        assert "1. nines -f json collect" in result
        assert "Execute these" in result

    def test_with_stage_name(self) -> None:
        result = format_nines_context(["cmd1"], stage_name="research")
        assert "stage 'research'" in result

    def test_multiple_commands_numbered(self) -> None:
        result = format_nines_context(["cmd1", "cmd2", "cmd3"])
        assert "1. cmd1" in result
        assert "2. cmd2" in result
        assert "3. cmd3" in result


class TestNinesCommandsToDispatchContext:
    def test_no_commands(self) -> None:
        result = nines_commands_to_dispatch_context(None)
        assert result == {"nines_context": ""}

    def test_with_commands(self) -> None:
        config = {"nines_commands": ["nines -f json collect"]}
        result = nines_commands_to_dispatch_context(config, "research")
        assert "nines_context" in result
        assert "nines -f json collect" in result["nines_context"]
        assert "research" in result["nines_context"]
