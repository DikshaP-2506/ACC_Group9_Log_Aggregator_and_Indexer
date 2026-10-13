import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest

from agent.agent import LogAgent
from agent.generator import generate_single_log


def test_generator_single_log_schema():
    log_json = generate_single_log("server-test")
    data = json.loads(log_json)

    assert data["source"] == "server-test"
    assert data["level"] in ["INFO", "WARNING", "ERROR"]
    assert "timestamp" in data
    assert "message" in data
    assert "metadata" in data
    assert data["metadata"]["source_host"] == "server-test"


def test_agent_parse_json_log_line():
    agent = LogAgent(source="server-1")
    line = json.dumps({
        "timestamp": "2026-10-12T12:00:00Z",
        "level": "ERROR",
        "source": "server-1",
        "message": "Out of memory",
        "metadata": {"mem": 95}
    })

    payload = agent.parse_log_line(line)
    assert payload["level"] == "ERROR"
    assert payload["message"] == "Out of memory"
    assert payload["source"] == "server-1"
    assert payload["metadata"]["mem"] == 95


def test_agent_parse_plaintext_log_line():
    agent = LogAgent(source="server-2")
    line = "2026-10-12 12:00:00 WARNING: disk space low"

    payload = agent.parse_log_line(line)
    assert payload["level"] == "WARNING"
    assert payload["source"] == "server-2"
    assert "disk space low" in payload["message"]


def test_agent_offset_persistence(tmp_path: Path):
    log_file = tmp_path / "test.log"
    state_file = tmp_path / "test.log.offset"

    agent = LogAgent(source="server-1", log_file_path=log_file, state_file_path=state_file)

    # Initially 0
    assert agent.load_offset() == 0

    # Save offset
    agent.save_offset(1024)
    assert agent.load_offset() == 1024


def test_agent_ship_duplicate_409_handled_safely():
    agent = LogAgent(source="server-1", max_retries=1, backoff_factor=0.01)

    mock_resp = MagicMock()
    mock_resp.status_code = 409
    mock_resp.json.return_value = {"error": "Duplicate Log"}

    with patch.object(agent._http_client, "post", return_value=mock_resp):
        shipped = agent.ship_log_entry({"message": "duplicate entry"})
        # Should return True so the offset advances and does not get stuck
        assert shipped is True


def test_agent_ship_retry_on_network_error():
    agent = LogAgent(source="server-1", max_retries=2, backoff_factor=0.01)

    with patch.object(
        agent._http_client,
        "post",
        side_effect=httpx.ConnectError("Connection refused")
    ) as mock_post:
        shipped = agent.ship_log_entry({"message": "test entry"})
        assert shipped is False
        # 1 initial attempt + 2 retries = 3 attempts
        assert mock_post.call_count == 3


def test_agent_process_available_logs_incremental(tmp_path: Path):
    log_file = tmp_path / "app.log"
    state_file = tmp_path / "app.log.offset"

    agent = LogAgent(
        source="server-1",
        log_file_path=log_file,
        state_file_path=state_file,
        max_retries=1
    )

    # 1. Write 2 lines to file
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"level": "INFO", "message": "Line 1"}) + "\n")
        f.write(json.dumps({"level": "INFO", "message": "Line 2"}) + "\n")

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"status": "success", "id": "test-id"}

    with patch.object(agent._http_client, "post", return_value=mock_resp):
        processed = agent.process_available_logs()
        assert processed == 2
        # Offset is past 0
        offset_after_first = agent.load_offset()
        assert offset_after_first > 0

        # Run again with no new lines: should process 0
        processed_again = agent.process_available_logs()
        assert processed_again == 0
        assert agent.load_offset() == offset_after_first

        # Append a 3rd line
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"level": "WARNING", "message": "Line 3"}) + "\n")

        processed_third = agent.process_available_logs()
        assert processed_third == 1
        assert agent.load_offset() > offset_after_first
