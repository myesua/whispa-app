"""
Event pattern utilities for common event-driven workflows
"""
import logging
from typing import Dict, Any, Optional, List, Callable, Union
from functools import wraps

from app.services.event_bus import EventType, subscribe, publish, publish_async, Event

logger = logging.getLogger(__name__)

def track_workflow(start_event: EventType, complete_event: EventType, fail_event: EventType):
    """
    Decorator to track a workflow by publishing start, complete, and fail events
    
    Args:
        start_event: Event type to publish when the function starts
        complete_event: Event type to publish when the function completes successfully
        fail_event: Event type to publish when the function fails
        
    Returns:
        Decorated function
    
    Example:
        @track_workflow(
            EventType.SUMMARIZATION_STARTED,
            EventType.SUMMARIZATION_COMPLETED,
            EventType.SUMMARIZATION_FAILED
        )
        async def generate_summary(summary_id, ...):
            # Function implementation
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract relevant data for events
            event_data = {k: v for k, v in kwargs.items() if not k.startswith('_')}
            
            # Publish start event
            await publish_async(start_event, event_data)
            
            try:
                # Call the original function
                result = await func(*args, **kwargs)
                
                # Add result to event data if it's a dict
                if isinstance(result, dict):
                    event_data.update({k: v for k, v in result.items() if k != 'error'})
                
                # Publish complete event
                await publish_async(complete_event, event_data)
                
                return result
            except Exception as e:
                # Add error to event data
                event_data['error'] = str(e)
                
                # Publish fail event
                await publish_async(fail_event, event_data)
                
                # Re-raise the exception
                raise
                
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract relevant data for events
            event_data = {k: v for k, v in kwargs.items() if not k.startswith('_')}
            
            # Publish start event
            publish(start_event, event_data)
            
            try:
                # Call the original function
                result = func(*args, **kwargs)
                
                # Add result to event data if it's a dict
                if isinstance(result, dict):
                    event_data.update({k: v for k, v in result.items() if k != 'error'})
                
                # Publish complete event
                publish(complete_event, event_data)
                
                return result
            except Exception as e:
                # Add error to event data
                event_data['error'] = str(e)
                
                # Publish fail event
                publish(fail_event, event_data)
                
                # Re-raise the exception
                raise
        
        # Return appropriate wrapper based on whether the function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator

def create_event_logger(event_types: Optional[List[EventType]] = None):
    """
    Create a logger that subscribes to specified events
    
    Args:
        event_types: List of event types to log, or None for all events
        
    Returns:
        Function that can be used to unsubscribe the logger
    
    Example:
        # Log all events
        unsubscribe_logger = create_event_logger()
        
        # Log only transcription events
        unsubscribe_logger = create_event_logger([
            EventType.TRANSCRIPTION_STARTED,
            EventType.TRANSCRIPTION_COMPLETED,
            EventType.TRANSCRIPTION_FAILED
        ])
    """
    def log_event(event: Event):
        event_name = event.event_type.name if isinstance(event.event_type, EventType) else event.event_type
        logger.info(f"Event: {event_name} | Source: {event.source} | Data: {event.data}")
    
    # Subscribe to events
    if event_types:
        for event_type in event_types:
            subscribe(event_type, log_event)
    else:
        subscribe(None, log_event)  # Subscribe to all events
    
    # Return function to unsubscribe
    def unsubscribe_logger():
        if event_types:
            for event_type in event_types:
                unsubscribe(event_type, log_event)
        else:
            unsubscribe(None, log_event)
    
    return unsubscribe_logger

def chain_events(trigger_event: Union[EventType, str], action_func: Callable, output_event: Optional[Union[EventType, str]] = None):
    """
    Chain events by triggering an action when an event occurs and optionally publishing a new event
    
    Args:
        trigger_event: Event type that triggers the action
        action_func: Function to call when the event occurs
        output_event: Optional event type to publish after the action completes
        
    Returns:
        Function that can be used to unsubscribe the handler
    
    Example:
        # When transcription completes, start summarization
        unsubscribe_chain = chain_events(
            EventType.TRANSCRIPTION_COMPLETED,
            lambda event: start_summarization(event.data['transcription_id']),
            EventType.SUMMARIZATION_STARTED
        )
    """
    @subscribe(trigger_event)
    def event_handler(event: Event):
        try:
            # Call the action function
            result = action_func(event)
            
            # Publish output event if specified
            if output_event and result:
                if isinstance(result, dict):
                    publish(output_event, result)
                else:
                    publish(output_event, {"result": result})
        except Exception as e:
            logger.error(f"Error in chained event handler: {str(e)}")
    
    # Return function to unsubscribe
    def unsubscribe_chain():
        unsubscribe(trigger_event, event_handler)
    
    return unsubscribe_chain

# Import asyncio at the end to avoid circular imports
import asyncio