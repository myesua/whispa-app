import logging
import asyncio
import inspect
from typing import Dict, List, Callable, Any, Set, Optional, Union, Coroutine
from enum import Enum, auto
import threading
import uuid
import time
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

class EventType(Enum):
    """Enum for standard event types in the application"""
    # Transcription events
    TRANSCRIPTION_STARTED = auto()
    TRANSCRIPTION_COMPLETED = auto()
    TRANSCRIPTION_FAILED = auto()
    
    # Summarization events
    SUMMARIZATION_STARTED = auto()
    SUMMARIZATION_COMPLETED = auto()
    SUMMARIZATION_FAILED = auto()
    
    # Screen capture events
    CAPTURE_STARTED = auto()
    CAPTURE_COMPLETED = auto()
    CAPTURE_FAILED = auto()
    PERIODIC_CAPTURE_STARTED = auto()
    PERIODIC_CAPTURE_STOPPED = auto()
    
    # Storage events
    CONTENT_SAVED = auto()
    CONTENT_DELETED = auto()
    
    # Integration events
    LINEAR_TICKET_CREATED = auto()
    NOTION_PAGE_CREATED = auto()
    INTEGRATION_CONFIGURED = auto()
    
    # Session events
    SESSION_CREATED = auto()
    SESSION_UPDATED = auto()
    SESSION_ENDED = auto()
    
    # Custom event type for user-defined events
    CUSTOM = auto()


class Event:
    """Event object that gets published to subscribers"""
    
    def __init__(
        self, 
        event_type: Union[EventType, str], 
        data: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None
    ):
        """
        Initialize an event
        
        Args:
            event_type: Type of event (from EventType enum or custom string)
            data: Optional data payload for the event
            source: Optional source identifier for the event
        """
        self.id = str(uuid.uuid4())
        self.event_type = event_type
        self.data = data or {}
        self.source = source
        self.timestamp = datetime.utcnow()
    
    def __str__(self):
        return f"Event(type={self.event_type}, source={self.source}, id={self.id})"


class EventBus:
    """
    Event bus for publishing and subscribing to events
    
    This implementation supports both synchronous and asynchronous event handlers.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure only one event bus exists"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the event bus if not already initialized"""
        if self._initialized:
            return
            
        self._subscribers: Dict[Union[EventType, str], List[Callable]] = {}
        self._wildcard_subscribers: List[Callable] = []
        self._event_history: List[Event] = []
        self._max_history_size = 100
        self._initialized = True
        self._loop = None
        logger.info("EventBus initialized")
    
    def subscribe(
        self, 
        event_type: Optional[Union[EventType, str, List[Union[EventType, str]]]] = None, 
        handler: Optional[Callable] = None
    ) -> Callable:
        """
        Subscribe to an event type or use as a decorator
        
        Args:
            event_type: Type of event to subscribe to, or list of event types.
                       If None, subscribes to all events (wildcard).
            handler: Function to call when event is published
            
        Returns:
            The handler function (for use as a decorator)
            
        Examples:
            # Direct subscription
            def handle_event(event):
                print(f"Received event: {event}")
            
            event_bus.subscribe(EventType.TRANSCRIPTION_COMPLETED, handle_event)
            
            # As a decorator for a specific event
            @event_bus.subscribe(EventType.TRANSCRIPTION_COMPLETED)
            def handle_transcription(event):
                print(f"Transcription completed: {event.data}")
                
            # As a decorator for multiple events
            @event_bus.subscribe([EventType.TRANSCRIPTION_STARTED, EventType.TRANSCRIPTION_COMPLETED])
            def handle_transcription_events(event):
                print(f"Transcription event: {event.event_type}")
                
            # As a wildcard subscriber (all events)
            @event_bus.subscribe()
            def handle_all_events(event):
                print(f"Event occurred: {event}")
        """
        def decorator(handler_func):
            if event_type is None:
                # Wildcard subscription
                self._wildcard_subscribers.append(handler_func)
                logger.debug(f"Added wildcard subscriber: {handler_func.__name__}")
            elif isinstance(event_type, list):
                # Multiple event types
                for evt_type in event_type:
                    if evt_type not in self._subscribers:
                        self._subscribers[evt_type] = []
                    self._subscribers[evt_type].append(handler_func)
                    logger.debug(f"Added subscriber for {evt_type}: {handler_func.__name__}")
            else:
                # Single event type
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                self._subscribers[event_type].append(handler_func)
                logger.debug(f"Added subscriber for {event_type}: {handler_func.__name__}")
            return handler_func
        
        # If handler is provided directly, subscribe immediately
        if handler is not None:
            return decorator(handler)
        
        # Otherwise return the decorator for use with @syntax
        return decorator
    
    def unsubscribe(
        self, 
        event_type: Optional[Union[EventType, str, List[Union[EventType, str]]]] = None, 
        handler: Callable = None
    ) -> None:
        """
        Unsubscribe a handler from an event type
        
        Args:
            event_type: Type of event to unsubscribe from, or list of event types.
                       If None, unsubscribes from all events (wildcard).
            handler: Function to unsubscribe
        """
        if handler is None:
            return
            
        if event_type is None:
            # Remove from wildcard subscribers
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)
                logger.debug(f"Removed wildcard subscriber: {handler.__name__}")
        elif isinstance(event_type, list):
            # Multiple event types
            for evt_type in event_type:
                if evt_type in self._subscribers and handler in self._subscribers[evt_type]:
                    self._subscribers[evt_type].remove(handler)
                    logger.debug(f"Removed subscriber for {evt_type}: {handler.__name__}")
        else:
            # Single event type
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                logger.debug(f"Removed subscriber for {event_type}: {handler.__name__}")
    
    def publish(self, event: Union[Event, EventType, str], data: Optional[Dict[str, Any]] = None, source: Optional[str] = None) -> None:
        """
        Publish an event to subscribers
        
        Args:
            event: Event object or event type
            data: Optional data payload if event is not an Event object
            source: Optional source identifier if event is not an Event object
        """
        # Convert to Event object if needed
        if not isinstance(event, Event):
            event = Event(event, data, source)
        
        # Add to history
        self._add_to_history(event)
        
        # Get subscribers for this event type
        subscribers = self._subscribers.get(event.event_type, []).copy()
        
        # Add wildcard subscribers
        subscribers.extend(self._wildcard_subscribers)
        
        if not subscribers:
            logger.debug(f"No subscribers for event: {event}")
            return
            
        logger.debug(f"Publishing event {event} to {len(subscribers)} subscribers")
        
        # Call each subscriber
        for subscriber in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    # Async handler
                    if self._loop is None:
                        try:
                            self._loop = asyncio.get_event_loop()
                        except RuntimeError:
                            # No event loop in this thread, create a new one
                            self._loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(self._loop)
                    
                    # Schedule the coroutine to run
                    asyncio.create_task(subscriber(event))
                else:
                    # Sync handler
                    subscriber(event)
            except Exception as e:
                logger.error(f"Error in event subscriber {subscriber.__name__}: {str(e)}")
    
    async def publish_async(self, event: Union[Event, EventType, str], data: Optional[Dict[str, Any]] = None, source: Optional[str] = None) -> None:
        """
        Publish an event to subscribers asynchronously
        
        Args:
            event: Event object or event type
            data: Optional data payload if event is not an Event object
            source: Optional source identifier if event is not an Event object
        """
        # Convert to Event object if needed
        if not isinstance(event, Event):
            event = Event(event, data, source)
        
        # Add to history
        self._add_to_history(event)
        
        # Get subscribers for this event type
        subscribers = self._subscribers.get(event.event_type, []).copy()
        
        # Add wildcard subscribers
        subscribers.extend(self._wildcard_subscribers)
        
        if not subscribers:
            logger.debug(f"No subscribers for event: {event}")
            return
            
        logger.debug(f"Publishing event {event} to {len(subscribers)} subscribers asynchronously")
        
        # Call each subscriber
        for subscriber in subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    # Async handler - await it
                    await subscriber(event)
                else:
                    # Sync handler - run directly
                    subscriber(event)
            except Exception as e:
                logger.error(f"Error in event subscriber {subscriber.__name__}: {str(e)}")
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining maximum size"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history.pop(0)
    
    def get_history(self, limit: int = None, event_type: Union[EventType, str] = None) -> List[Event]:
        """
        Get event history
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type
            
        Returns:
            List of events
        """
        if event_type is not None:
            history = [e for e in self._event_history if e.event_type == event_type]
        else:
            history = self._event_history.copy()
            
        if limit is not None:
            history = history[-limit:]
            
        return history
    
    def clear_history(self) -> None:
        """Clear event history"""
        self._event_history.clear()


# Global instance
_event_bus = None

def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Convenience functions
def subscribe(event_type=None, handler=None):
    """Subscribe to an event type"""
    return get_event_bus().subscribe(event_type, handler)

def unsubscribe(event_type=None, handler=None):
    """Unsubscribe from an event type"""
    return get_event_bus().unsubscribe(event_type, handler)

def publish(event, data=None, source=None):
    """Publish an event"""
    return get_event_bus().publish(event, data, source)

async def publish_async(event, data=None, source=None):
    """Publish an event asynchronously"""
    return await get_event_bus().publish_async(event, data, source)

def get_history(limit=None, event_type=None):
    """Get event history"""
    return get_event_bus().get_history(limit, event_type)

def clear_history():
    """Clear event history"""
    return get_event_bus().clear_history()