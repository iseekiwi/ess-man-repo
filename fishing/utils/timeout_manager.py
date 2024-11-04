import asyncio
import time
import weakref
from typing import Dict, Any, Optional
from .logging_config import get_logger

logger = get_logger('tmanager')

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
            self.logger.debug("TimeoutManager started with check task")
    
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
        try:
            view_id = self.generate_view_id(view)
            current_time = time.time()
            
            if view_id not in self._timeouts:
                self._timeouts[view_id] = {
                    'expiry': current_time + duration,
                    'duration': duration,
                    'last_interaction': current_time,
                    'paused': False
                }
                self._views[view_id] = view
                
                self.logger.debug(
                    f"Added view to timeout manager:\n"
                    f"  ID: {view_id}\n"
                    f"  Type: {view.__class__.__name__}\n"
                    f"  Duration: {duration}s\n"
                    f"  Expiry: +{duration}s"
                )
            else:
                self.logger.debug(f"View {view_id} already registered, resetting timeout")
                await self.reset_timeout(view)
                
            if not self._task or self._task.done():
                await self.start()
                
        except Exception as e:
            self.logger.error(f"Error adding view to timeout manager: {e}")
    
    async def remove_view(self, view):
        """Remove a view from timeout management"""
        view_id = self.generate_view_id(view)
        self._timeouts.pop(view_id, None)
        self._views.pop(view_id, None)
        self.logger.debug(f"Removed view {view_id}")
    
    async def reset_timeout(self, view):
        """Reset timeout for a view and all related views"""
        try:
            view_id = self.generate_view_id(view)
            self.logger.debug(f"Attempting to reset timeout for view {view_id}")
            
            if view_id in self._timeouts:
                # Reset this view's timeout
                current_time = time.time()
                duration = self._timeouts[view_id]['duration']
                new_expiry = current_time + duration
                
                self._timeouts[view_id].update({
                    'expiry': new_expiry,
                    'last_interaction': current_time
                })
                
                # Reset parent view if it exists
                parent_id = self._timeouts[view_id].get('parent_id')
                if parent_id and parent_id in self._timeouts:
                    self._timeouts[parent_id].update({
                        'expiry': new_expiry,
                        'last_interaction': current_time
                    })
                    self.logger.debug(f"Reset parent view {parent_id}")
                
                # Reset child views
                for tid, data in self._timeouts.items():
                    if data.get('parent_id') == view_id:
                        data.update({
                            'expiry': new_expiry,
                            'last_interaction': current_time
                        })
                        self.logger.debug(f"Reset child view {tid}")
                        
                self.logger.debug(
                    f"Reset timeout cascade:\n"
                    f"  View: {view_id}\n"
                    f"  Parent: {parent_id if parent_id else 'None'}\n"
                    f"  New expiry: {new_expiry}"
                )
            else:
                self.logger.warning(
                    f"View {view_id} not found in timeout manager, "
                    f"attempting to register"
                )
                await self.add_view(view, view.timeout)
                
        except Exception as e:
            self.logger.error(f"Error resetting timeout: {e}")
    
    async def _check_timeouts(self):
        """Background task to check for expired timeouts"""
        self.logger.debug("Starting timeout check loop")
        last_check = time.time()
        
        while self._running:
            try:
                now = time.time()
                elapsed = now - last_check
                self.logger.debug(f"Checking timeouts after {elapsed:.1f}s")
                last_check = now
                
                # Log current state
                self.logger.debug(f"Active timeouts: {len(self._timeouts)}")
                for view_id, data in self._timeouts.items():
                    time_left = data['expiry'] - now
                    last_interaction = data.get('last_interaction', 0)
                    interaction_age = now - last_interaction
                    
                    self.logger.debug(
                        f"View {view_id} status:\n"
                        f"  Time left: {time_left:.1f}s\n"
                        f"  Last interaction: {interaction_age:.1f}s ago\n"
                        f"  Duration: {data['duration']}s\n"
                        f"  Paused: {data.get('paused', False)}"
                    )
    
                # Check for expired timeouts
                expired_views = []
                for view_id, data in list(self._timeouts.items()):
                    if data.get('paused', False):
                        continue
                        
                    time_left = data['expiry'] - now
                    if time_left <= 0:
                        if view := self._views.get(view_id):
                            expired_views.append((view_id, view))
                            self.logger.debug(f"Marking view {view_id} for expiration")
    
                # Handle expired views
                for view_id, view in expired_views:
                    try:
                        self.logger.info(f"Expiring view {view_id}")
                        await self.remove_view(view)
                        await view.on_timeout()
                    except Exception as e:
                        self.logger.error(f"Error handling timeout for view {view_id}: {e}")
    
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                self.logger.debug("Timeout check loop cancelled")
                raise
            except Exception as e:
                self.logger.error(f"Error in timeout check loop: {e}")
                await asyncio.sleep(5)

    async def handle_view_transition(self, parent_view, child_view):
        """Handle timeout management for view transitions"""
        try:
            parent_id = self.generate_view_id(parent_view)
            child_id = self.generate_view_id(child_view)
            
            self.logger.debug(
                f"Processing view transition:\n"
                f"  Parent: {parent_id} ({parent_view.__class__.__name__})\n"
                f"  Child: {child_id} ({child_view.__class__.__name__})"
            )
            
            # Get parent timeout settings
            if parent_id in self._timeouts:
                parent_data = self._timeouts[parent_id]
                current_time = time.time()
                
                # Calculate remaining time from parent
                remaining_time = parent_data['expiry'] - current_time
                if remaining_time <= 0:
                    remaining_time = parent_data['duration']
                    
                # Add child with parent's remaining time
                self._timeouts[child_id] = {
                    'expiry': current_time + remaining_time,
                    'duration': parent_data['duration'],
                    'last_interaction': current_time,
                    'parent_id': parent_id,
                    'paused': False
                }
                self._views[child_id] = child_view
                
                # Pause parent but preserve its timeout
                parent_data['paused'] = True
                parent_data['last_interaction'] = current_time
                
                self.logger.debug(
                    f"View transition completed:\n"
                    f"  Parent {parent_id} paused with {remaining_time:.1f}s remaining\n"
                    f"  Child {child_id} inheriting timeout"
                )
            else:
                # If parent isn't found, log warning and register both
                self.logger.warning(f"Parent view {parent_id} not found, registering both views")
                await self.add_view(parent_view, parent_view.timeout)
                await self.add_view(child_view, child_view.timeout)
                
        except Exception as e:
            self.logger.error(f"Error in view transition: {e}")
            
    async def resume_parent_view(self, child_view):
        """Resume parent view timeout when returning from child view"""
        try:
            child_id = self.generate_view_id(child_view)
            
            if child_id in self._timeouts:
                parent_id = self._timeouts[child_id].get('parent_id')
                if parent_id and parent_id in self._timeouts:
                    # Transfer remaining time to parent
                    remaining_time = self._timeouts[child_id]['expiry'] - time.time()
                    if remaining_time > 0:
                        self._timeouts[parent_id].update({
                            'expiry': time.time() + remaining_time,
                            'paused': False
                        })
                        self.logger.debug(
                            f"Resumed parent view {parent_id} with {remaining_time:.1f}s remaining"
                        )
                    
                    # Clean up child view
                    self._timeouts.pop(child_id, None)
                    self._views.pop(child_id, None)
                    
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
