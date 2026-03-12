# utils/timeout_manager.py

import asyncio
import time
import weakref
from typing import Dict, Any, Optional
from .logging_config import get_logger

logger = get_logger('tmanager')


class KiwisinoTimeoutManager:
    """Centralized timeout management for Kiwisino views.

    Separate singleton from the fishing cog's TimeoutManager so both cogs
    can be loaded simultaneously.  Identical in behaviour.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KiwisinoTimeoutManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._initialized = True
            self._timeouts: Dict[str, Dict[str, Any]] = {}
            self._task: Optional[asyncio.Task] = None
            self._running = False
            self._views = weakref.WeakValueDictionary()
            self.logger = get_logger('timeout_manager')
            self.logger.debug("KiwisinoTimeoutManager initialized")

    async def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._check_timeouts())
            self.logger.debug("KiwisinoTimeoutManager started")

    async def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._timeouts.clear()
        self._views.clear()
        self.logger.debug("KiwisinoTimeoutManager stopped")

    def generate_view_id(self, view) -> str:
        return f"{view.__class__.__name__}_{id(view)}"

    async def add_view(self, view, duration: int):
        try:
            view_id = self.generate_view_id(view)
            current_time = time.time()

            if view_id not in self._timeouts:
                self._timeouts[view_id] = {
                    'expiry': current_time + duration,
                    'duration': duration,
                    'last_interaction': current_time,
                    'paused': False,
                }
                self._views[view_id] = view
                self.logger.debug(f"Added view {view_id}, duration={duration}s")
            else:
                self.logger.debug(f"View {view_id} already registered, resetting")
                await self.reset_timeout(view)

            if not self._task or self._task.done():
                await self.start()
        except Exception as e:
            self.logger.error(f"Error adding view: {e}")

    async def remove_view(self, view):
        view_id = self.generate_view_id(view)
        self._timeouts.pop(view_id, None)
        self._views.pop(view_id, None)
        self.logger.debug(f"Removed view {view_id}")

    async def reset_timeout(self, view):
        try:
            view_id = self.generate_view_id(view)
            if view_id in self._timeouts:
                current_time = time.time()
                duration = self._timeouts[view_id]['duration']
                new_expiry = current_time + duration

                self._timeouts[view_id].update({
                    'expiry': new_expiry,
                    'last_interaction': current_time,
                })

                parent_id = self._timeouts[view_id].get('parent_id')
                if parent_id and parent_id in self._timeouts:
                    self._timeouts[parent_id].update({
                        'expiry': new_expiry,
                        'last_interaction': current_time,
                    })

                for tid, data in self._timeouts.items():
                    if data.get('parent_id') == view_id:
                        data.update({
                            'expiry': new_expiry,
                            'last_interaction': current_time,
                        })
            else:
                self.logger.warning(f"View {view_id} not found, re-adding")
                custom_timeout = getattr(view, '_custom_timeout', view.timeout) or 300
                await self.add_view(view, custom_timeout)
        except Exception as e:
            self.logger.error(f"Error resetting timeout: {e}")

    async def _check_timeouts(self):
        while self._running:
            try:
                now = time.time()
                expired_views = []
                for view_id, data in list(self._timeouts.items()):
                    if data.get('paused', False):
                        continue
                    if data['expiry'] - now <= 0:
                        if view := self._views.get(view_id):
                            expired_views.append((view_id, view))

                for view_id, view in expired_views:
                    try:
                        self.logger.info(f"Expiring view {view_id}")
                        await view.on_timeout()
                    except Exception as e:
                        self.logger.error(f"Error expiring {view_id}: {e}")
                        self._timeouts.pop(view_id, None)
                        self._views.pop(view_id, None)

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"Error in timeout loop: {e}")
                await asyncio.sleep(5)

    async def handle_view_transition(self, parent_view, child_view):
        try:
            parent_id = self.generate_view_id(parent_view)
            child_id = self.generate_view_id(child_view)
            current_time = time.time()

            if parent_id in self._timeouts:
                parent_data = self._timeouts[parent_id]
                remaining_time = max(0, parent_data['expiry'] - current_time)
                if remaining_time <= 0:
                    remaining_time = parent_data['duration']

                parent_data.update({
                    'paused': True,
                    'last_interaction': current_time,
                    'expiry': current_time + remaining_time,
                })

                self._timeouts[child_id] = {
                    'expiry': current_time + remaining_time,
                    'duration': parent_data['duration'],
                    'last_interaction': current_time,
                    'parent_id': parent_id,
                    'paused': False,
                }
                self._views[child_id] = child_view
                self.logger.debug(
                    f"Transition: parent {parent_id} paused, "
                    f"child {child_id} inheriting {remaining_time:.0f}s"
                )
            else:
                self.logger.warning(f"Parent {parent_id} not found, registering both")
                parent_timeout = getattr(parent_view, '_custom_timeout', parent_view.timeout) or 300
                child_timeout = getattr(child_view, '_custom_timeout', child_view.timeout) or 300
                await self.add_view(parent_view, parent_timeout)
                await self.add_view(child_view, child_timeout)
        except Exception as e:
            self.logger.error(f"Error in view transition: {e}")

    async def resume_parent_view(self, child_view):
        try:
            child_id = self.generate_view_id(child_view)
            if child_id in self._timeouts:
                parent_id = self._timeouts[child_id].get('parent_id')
                if parent_id and parent_id in self._timeouts:
                    remaining_time = self._timeouts[child_id]['expiry'] - time.time()
                    if remaining_time > 0:
                        self._timeouts[parent_id].update({
                            'expiry': time.time() + remaining_time,
                            'paused': False,
                        })
                    self._timeouts.pop(child_id, None)
                    self._views.pop(child_id, None)
                    self.logger.debug(f"Resumed parent {parent_id}")
        except Exception as e:
            self.logger.error(f"Error resuming parent: {e}")

    async def cleanup(self):
        for view_id, view in list(self._views.items()):
            try:
                await view.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up {view_id}: {e}")
        await self.stop()

    @classmethod
    def reset(cls):
        """Reset the singleton — call on cog unload."""
        if cls._instance is not None:
            cls._instance._running = False
            if cls._instance._task and not cls._instance._task.done():
                cls._instance._task.cancel()
            cls._instance._timeouts.clear()
            cls._instance._views.clear()
            cls._instance = None
            cls._initialized = False
