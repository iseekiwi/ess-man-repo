import asyncio
import time
import weakref
from typing import Dict, Any, Optional
from .logging_config import get_logger

logger = get_logger('timeout_manager')

class TimeoutManager:
    """
    Centralized timeout management system for views.
    
    This class manages timeouts for all views in the application using a single
    background task and efficient timeout tracking.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TimeoutManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._timeouts: Dict[str, Dict[str, Any]] = {}
            self._task: Optional[asyncio.Task] = None
            self._running = False
            # Use weak references to prevent memory leaks
            self._views = weakref.WeakValueDictionary()
            self.logger = get_logger('timeout_manager')
            self.logger.debug("TimeoutManager initialized")
    
    async def start(self):
        """Start the timeout manager"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._check_timeouts())
            self.logger.debug("TimeoutManager started")
    
    async def stop(self):
        """Stop the timeout manager"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._timeouts.clear()
        self._views.clear()
        self.logger.debug("TimeoutManager stopped")
    
    def generate_view_id(self, view) -> str:
        """Generate a unique identifier for a view"""
        return f"{view.__class__.__name__}_{id(view)}"
    
    async def add_view(self, view, duration: int):
        """Add a view to timeout management"""
        view_id = self.generate_view_id(view)
        self._timeouts[view_id] = {
            'expiry': time.time() + duration,
            'duration': duration,
            'last_interaction': time.time()  # Add this to track last interaction
        }
        self._views[view_id] = view
        self.logger.debug(
            f"Added view {view_id} with duration {duration}s. "
            f"View type: {view.__class__.__name__}"
        )
        
        if not self._task or self._task.done():
            await self.start()
    
    async def remove_view(self, view):
        """Remove a view from timeout management"""
        view_id = self.generate_view_id(view)
        self._timeouts.pop(view_id, None)
        self._views.pop(view_id, None)
        self.logger.debug(f"Removed view {view_id}")
    
    async def reset_timeout(self, view):
        """Reset a view's timeout"""
        view_id = self.generate_view_id(view)
        if view_id in self._timeouts:
            duration = self._timeouts[view_id]['duration']
            current_time = time.time()
            self._timeouts[view_id].update({
                'expiry': current_time + duration,
                'last_interaction': current_time
            })
            self.logger.debug(
                f"Reset timeout for view {view_id}. "
                f"New expiry in {duration}s. "
                f"View type: {view.__class__.__name__}"
            )
    
    async def _check_timeouts(self):
        """Background task to check for expired timeouts"""
        self.logger.debug("Starting timeout check loop")
        while self._running:
            try:
                now = time.time()
                expired_views = []
                
                # Check for expired timeouts
                for view_id, data in self._timeouts.items():
                    if data.get('paused', False):
                        continue
                        
                    time_left = data['expiry'] - now
                    last_interaction = data.get('last_interaction', 0)
                    interaction_age = now - last_interaction
                    
                    self.logger.debug(
                        f"View {view_id} status: "
                        f"Time left: {time_left:.1f}s, "
                        f"Last interaction: {interaction_age:.1f}s ago"
                    )
                    
                    if time_left <= 0:
                        if view := self._views.get(view_id):
                            expired_views.append((view_id, view))
                    elif time_left < 5:
                        await asyncio.sleep(0.5)
                        continue

                # Handle expired views
                for view_id, view in expired_views:
                    try:
                        self.logger.info(f"View {view_id} timeout triggered")
                        self._timeouts.pop(view_id, None)
                        self._views.pop(view_id, None)
                        await view.on_timeout()
                    except Exception as e:
                        self.logger.error(f"Error handling timeout for view {view_id}: {e}")

                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Error in timeout check loop: {e}")
                await asyncio.sleep(5)

    async def handle_view_transition(self, parent_view, child_view):
        """Handle timeout management for view transitions"""
        try:
            parent_id = self.generate_view_id(parent_view)
            child_id = self.generate_view_id(child_view)
            
            # Store parent view timeout settings
            if parent_id in self._timeouts:
                parent_timeout = self._timeouts[parent_id]['duration']
                
                # Add child view with same timeout duration
                await self.add_view(child_view, parent_timeout)
                
                # Link child to parent
                self._timeouts[child_id]['parent_id'] = parent_id
                
                # Pause parent view timeout without removing it
                self._timeouts[parent_id]['paused'] = True
                
        except Exception as e:
            self.logger.error(f"Error in handle_view_transition: {e}")
            
    async def resume_parent_view(self, child_view):
        """Resume parent view timeout when returning from child view"""
        try:
            child_id = self.generate_view_id(child_view)
            if child_id in self._timeouts:
                parent_id = self._timeouts[child_id].get('parent_id')
                if parent_id and parent_id in self._timeouts:
                    # Unpause parent view
                    self._timeouts[parent_id]['paused'] = False
                    
                    # Reset parent view timeout
                    if parent_view := self._views.get(parent_id):
                        self._timeouts[parent_id]['expiry'] = time.time() + self._timeouts[parent_id]['duration']
                        self.logger.debug(f"Reset timeout for parent view {parent_id}")
                        
        except Exception as e:
            self.logger.error(f"Error in resume_parent_view: {e}")
    
    async def cleanup(self):
        """Clean up all managed views"""
        for view_id, view in list(self._views.items()):
            try:
                await view.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up view {view_id}: {e}")
        await self.stop()
