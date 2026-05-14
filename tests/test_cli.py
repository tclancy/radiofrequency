from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_help_lists_subcommands(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "send" in result.output
    assert "raw" in result.output


def test_send_posts_to_transmit_endpoint(runner):
    with patch("cli.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        mock_post.return_value.raise_for_status = MagicMock()

        result = runner.invoke(
            cli,
            ["send", "sofa_king_fan", "main", "light", "--host", "1.2.3.4"],
        )

    assert result.exit_code == 0, result.output
    assert mock_post.call_count == 1
    (url,) = mock_post.call_args.args
    assert url == "http://1.2.3.4:80/transmit"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["bits"] == "10001100111101101100000000111111"
    assert payload["timing"]["pulse_us"] == 560


def test_send_rejects_unknown_unit(runner):
    with patch("cli.httpx.post") as mock_post:
        result = runner.invoke(
            cli,
            ["send", "sofa_king_fan", "garage", "light", "--host", "1.2.3.4"],
        )
    assert result.exit_code != 0
    assert "unknown unit" in result.output.lower()
    assert mock_post.call_count == 0


def test_raw_posts_arbitrary_bits(runner):
    with patch("cli.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200, text="OK")
        mock_post.return_value.raise_for_status = MagicMock()

        result = runner.invoke(
            cli,
            [
                "raw",
                "01" * 16,
                "--device",
                "sofa_king_fan",
                "--host",
                "1.2.3.4",
            ],
        )

    assert result.exit_code == 0, result.output
    assert mock_post.call_count == 1
    payload = mock_post.call_args.kwargs["json"]
    assert payload["bits"] == "01" * 16
    assert payload["timing"]["pulse_us"] == 560


def test_raw_rejects_non_binary(runner):
    with patch("cli.httpx.post") as mock_post:
        result = runner.invoke(
            cli,
            ["raw", "01x0", "--device", "sofa_king_fan", "--host", "1.2.3.4"],
        )
    assert result.exit_code != 0
    assert mock_post.call_count == 0
