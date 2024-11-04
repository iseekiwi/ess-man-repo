import asyncio
import time
import weakref
from typing import Dict, Any, Optional
from .logging_config import get_logger

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
            'duration': duration
        }
        self._views[view_id] = view
        self.logger.debug(f"Added view {view_id} with duration {duration}s")
        
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
            self._timeouts[view_id]['expiry'] = time.time() + duration
            self.logger.debug(f"Reset timeout for view {view_id}")
    
    async def _check_timeouts(self):
        """Background task to check for expired timeouts"""
        self.logger.debug("Starting timeout check loop")
        while self._running:
            try:
                now = time.time()
                expired_views = []
                
                # Check for expired timeouts
                for view_id, data in self._timeouts.items():
                    if data['expiry'] <= now:
                        if view := self._views.get(view_id):
                            expired_views.append((view_id, view))
                
                # Handle expired views
                for view_id, view in expired_views:
                    try:
                        self._timeouts.pop(view_id, None)
                        self._views.pop(view_id, None)
                        await view.on_timeout()
                        self.logger.debug(f"View {view_id} timed out")
                    except Exception as e:
                        self.logger.error(f"Error handling timeout for view {view_id}: {e}")
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Error in timeout check loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error
                
    async def cleanup(self):
        """Clean up all managed views"""
        for view_id, view in list(self._views.items()):
            try:
                await view.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up view {view_id}: {e}")
        await self.stop()
