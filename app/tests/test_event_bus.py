"""
Tests for the event bus system
"""
import asyncio
import pytest
from unittest.mock import MagicMock

from app.services.event_bus import (
    EventType, Event, get_event_bus, subscribe, unsubscribe, 
    publish, publish_async, get_event_history
)
from app.services.event_patterns import track_workflow, create_event_logger, chain_events

# Test synchronous event publishing and subscription
def test_sync_publish_subscribe():
    # Setup
    handler = MagicMock()
    subscribe(EventType.TRANSCRIPTION_COMPLETED, handler)
    
    # Action
    event_data = {"transcription_id": "123", "text": "Test transcription"}
    publish(EventType.TRANSCRIPTION_COMPLETED, event_data)
    
    # Assert
    handler.assert_called_once()
    event = handler.call_args[0][0]
    assert isinstance(event, Event)
    assert event.event_type == EventType.TRANSCRIPTION_COMPLETED
    assert event.data == event_data
    
    # Cleanup
    unsubscribe(EventType.TRANSCRIPTION_COMPLETED, handler)

# Test asynchronous event publishing and subscription
@pytest.mark.asyncio
async def test_async_publish_subscribe():
    # Setup
    handler = MagicMock()
    subscribe(EventType.SUMMARIZATION_COMPLETED, handler)
    
    # Action
    event_data = {"summary_id": "456", "text": "Test summary"}
    await publish_async(EventType.SUMMARIZATION_COMPLETED, event_data)
    
    # Assert
    handler.assert_called_once()
    event = handler.call_args[0][0]
    assert isinstance(event, Event)
    assert event.event_type == EventType.SUMMARIZATION_COMPLETED
    assert event.data == event_data
    
    # Cleanup
    unsubscribe(EventType.SUMMARIZATION_COMPLETED, handler)

# Test event history
def test_event_history():
    # Setup
    event_bus = get_event_bus()
    initial_history_length = len(get_event_history())
    
    # Action
    publish(EventType.SCREEN_CAPTURE_COMPLETED, {"capture_id": "789"})
    publish(EventType.CONTENT_SAVED, {"storage_id": "abc"})
    
    # Assert
    history = get_event_history()
    assert len(history) == initial_history_length + 2
    assert history[-2].event_type == EventType.SCREEN_CAPTURE_COMPLETED
    assert history[-1].event_type == EventType.CONTENT_SAVED

# Test wildcard subscription
def test_wildcard_subscription():
    # Setup
    handler = MagicMock()
    subscribe(None, handler)  # Subscribe to all events
    
    # Action
    publish(EventType.SESSION_STARTED, {"session_id": "session1"})
    publish(EventType.CUSTOM, {"message": "Custom event"})
    
    # Assert
    assert handler.call_count == 2
    
    # Cleanup
    unsubscribe(None, handler)

# Test track_workflow decorator
@pytest.mark.asyncio
async def test_track_workflow_decorator():
    # Setup
    start_handler = MagicMock()
    complete_handler = MagicMock()
    fail_handler = MagicMock()
    
    subscribe(EventType.SUMMARIZATION_STARTED, start_handler)
    subscribe(EventType.SUMMARIZATION_COMPLETED, complete_handler)
    subscribe(EventType.SUMMARIZATION_FAILED, fail_handler)
    
    # Define test function with decorator
    @track_workflow(
        EventType.SUMMARIZATION_STARTED,
        EventType.SUMMARIZATION_COMPLETED,
        EventType.SUMMARIZATION_FAILED
    )
    async def test_summarize(summary_id, text):
        return {"summary": f"Summary of {text}", "summary_id": summary_id}
    
    # Action - successful case
    result = await test_summarize(summary_id="123", text="Test content")
    
    # Assert - successful case
    assert start_handler.call_count == 1
    assert complete_handler.call_count == 1
    assert fail_handler.call_count == 0
    assert result["summary"] == "Summary of Test content"
    
    # Setup for failure case
    @track_workflow(
        EventType.SUMMARIZATION_STARTED,
        EventType.SUMMARIZATION_COMPLETED,
        EventType.SUMMARIZATION_FAILED
    )
    async def test_summarize_fail(summary_id):
        raise ValueError("Test error")
    
    # Action - failure case
    with pytest.raises(ValueError):
        await test_summarize_fail(summary_id="456")
    
    # Assert - failure case
    assert start_handler.call_count == 2
    assert complete_handler.call_count == 1
    assert fail_handler.call_count == 1
    
    # Cleanup
    unsubscribe(EventType.SUMMARIZATION_STARTED, start_handler)
    unsubscribe(EventType.SUMMARIZATION_COMPLETED, complete_handler)
    unsubscribe(EventType.SUMMARIZATION_FAILED, fail_handler)

# Test chain_events utility
def test_chain_events():
    # Setup
    action_func = MagicMock(return_value={"result_id": "789"})
    output_handler = MagicMock()
    
    subscribe(EventType.CUSTOM, output_handler)
    unsubscribe_chain = chain_events(
        EventType.TRANSCRIPTION_COMPLETED,
        action_func,
        EventType.CUSTOM
    )
    
    # Action
    publish(EventType.TRANSCRIPTION_COMPLETED, {"transcription_id": "123"})
    
    # Assert
    action_func.assert_called_once()
    output_handler.assert_called_once()
    
    # Cleanup
    unsubscribe_chain()
    unsubscribe(EventType.CUSTOM, output_handler)

# Test event logger
def test_event_logger(caplog):
    # Setup
    unsubscribe_logger = create_event_logger([EventType.SESSION_STARTED])
    
    # Action
    publish(EventType.SESSION_STARTED, {"session_id": "session1"})
    publish(EventType.TRANSCRIPTION_COMPLETED, {"transcription_id": "123"})  # Should not be logged
    
    # Assert
    assert "SESSION_STARTED" in caplog.text
    assert "session1" in caplog.text
    assert "TRANSCRIPTION_COMPLETED" not in caplog.text
    
    # Cleanup
    unsubscribe_logger()