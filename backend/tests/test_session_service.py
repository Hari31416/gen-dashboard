from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from services.dashboard.session_service import (
    _strip_inline_data,
    delete_dashboard_session,
    get_dashboard_session,
    get_dashboard_sessions_collection,
    list_dashboard_sessions,
    save_dashboard_session,
    update_chart_customizations,
    update_dashboard_layout,
    update_dashboard_session,
)


@pytest.fixture
def mock_mongo_pool():
    with patch("services.dashboard.session_service.mongo_pool") as mock:
        yield mock


@pytest.fixture
def mock_collection(mock_mongo_pool):
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_coll = MagicMock()

    mock_mongo_pool.get_client.return_value = mock_client
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_coll

    return mock_coll


def test_get_dashboard_sessions_collection(mock_mongo_pool):
    client_mock = MagicMock()
    db_mock = MagicMock()
    coll_mock = MagicMock()

    mock_mongo_pool.get_client.return_value = client_mock
    client_mock.__getitem__.return_value = db_mock
    db_mock.__getitem__.return_value = coll_mock

    username = "testuser"
    result = get_dashboard_sessions_collection(username)

    mock_mongo_pool.get_client.assert_called_once()
    client_mock.__getitem__.assert_called_with("testuser_dashboard")
    db_mock.__getitem__.assert_called_with("sessions")
    assert result == coll_mock


def test_save_dashboard_session(mock_collection):
    username = "testuser"
    session_id = "sess-123"
    user_prompt = "show sales"
    connection_name = "conn1"
    dashboard_spec = {
        "title": "Sales Dashboard",
        "individual_specs": [{"data": {"values": [1, 2, 3]}}],
    }
    chart_goals = [{"goal": "Goal 1"}]
    sql_queries = [{"sql": "SELECT * FROM sales"}]
    generation_time_ms = 1500.0

    # Mock update_one
    mock_collection.update_one.return_value = MagicMock()

    result = save_dashboard_session(
        username,
        session_id,
        user_prompt,
        connection_name,
        dashboard_spec,
        chart_goals,
        sql_queries,
        generation_time_ms,
    )

    assert result["session_id"] == session_id
    assert result["user_prompt"] == user_prompt
    # Check if data was stripped
    assert result["dashboard_spec"]["individual_specs"][0]["data"]["values"] == []

    mock_collection.update_one.assert_called_once()
    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"session_id": session_id}
    assert call_args[1]["upsert"] is True


def test_strip_inline_data():
    spec = {
        "individual_specs": [
            {"data": {"values": [1, 2, 3]}},  # Should be stripped
            {
                "data": {
                    "url": "http://example.com",
                    "values": [1, 2],
                }  # URL exists, keep values? No, logic says pass if url exists
            },
        ],
        "vega_lite_spec": {
            "vconcat": [{"data": {"values": [4, 5, 6]}}]  # Should be stripped
        },
    }

    cleaned = _strip_inline_data(spec)

    assert cleaned["individual_specs"][0]["data"]["values"] == []
    assert cleaned["individual_specs"][1]["data"]["values"] == [1, 2]

    assert cleaned["vega_lite_spec"]["vconcat"][0]["data"]["values"] == []


def test_get_dashboard_session_found(mock_collection):
    mock_collection.find_one.return_value = {
        "_id": "mongo_id",
        "session_id": "sess-123",
        "user_prompt": "hello",
    }

    result = get_dashboard_session("testuser", "sess-123")

    assert result is not None
    assert result["session_id"] == "sess-123"
    assert "_id" not in result  # data should be popped
    mock_collection.find_one.assert_called_with({"session_id": "sess-123"})


def test_get_dashboard_session_not_found(mock_collection):
    mock_collection.find_one.return_value = None
    result = get_dashboard_session("testuser", "unknown")
    assert result is None


def test_update_dashboard_session(mock_collection):
    mock_collection.update_one.return_value.modified_count = 1

    success = update_dashboard_session(
        "testuser",
        "sess-123",
        {"new_spec": True},
        refinement_feedback="Make it blue",
        chart_goals=[{"new_goal": 1}],
    )

    assert success is True
    mock_collection.update_one.assert_called_once()
    args = mock_collection.update_one.call_args[0]
    update_doc = args[1]

    assert update_doc["$set"]["dashboard_spec"] == {"new_spec": True}
    assert update_doc["$set"]["chart_goals"] == [{"new_goal": 1}]
    assert update_doc["$push"]["refinement_history"]["feedback"] == "Make it blue"


def test_update_dashboard_layout(mock_collection):
    mock_collection.update_one.return_value.modified_count = 1

    layout = {"w": 10, "h": 5}
    success = update_dashboard_layout("testuser", "sess-123", layout)

    assert success is True
    assert layout["custom"] is True

    mock_collection.update_one.assert_called_once()
    update_doc = mock_collection.update_one.call_args[0][1]
    assert update_doc["$set"]["dashboard_spec.layout_config"] == layout


def test_list_dashboard_sessions(mock_collection):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = [{"session_id": "s1"}, {"session_id": "s2"}]
    mock_collection.find.return_value = mock_cursor

    result = list_dashboard_sessions("testuser", limit=10, skip=5)

    assert len(result) == 2
    assert result[0]["session_id"] == "s1"

    mock_collection.find.assert_called_once()
    mock_cursor.skip.assert_called_with(5)
    mock_cursor.limit.assert_called_with(10)


def test_delete_dashboard_session(mock_collection):
    mock_collection.delete_one.return_value.deleted_count = 1
    success = delete_dashboard_session("testuser", "sess-123")
    assert success is True
    mock_collection.delete_one.assert_called_with({"session_id": "sess-123"})


def test_update_chart_customizations(mock_collection):
    mock_collection.update_one.return_value.modified_count = 1
    customs = {"chart1": {"color": "red"}}

    success = update_chart_customizations("testuser", "sess-123", customs)

    assert success is True
    mock_collection.update_one.assert_called_once()
    update_doc = mock_collection.update_one.call_args[0][1]
    assert update_doc["$set"]["chart_customizations"] == customs
