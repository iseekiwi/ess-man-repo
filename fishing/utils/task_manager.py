# utils/task_manager.py

import asyncio
import datetime
import random
from typing import Dict, List, Optional
from .logging_config import get_logger

class TaskManager:
    """Enhanced task management system"""
    def __init__(self, bot, config, data):
        self.bot = bot
        self.config = config
        self.data = data
        self.tasks: Dict[str, asyncio.Task] = {}
        self.last_reset = None
        self.last_weather_change = None
        self.logger = get_logger('task_manager')
        self._running = False
        
    async def start(self):
        """Start all registered tasks"""
        if self._running:
            return
            
        self._running = True
        self.tasks = {
            'weather': self.bot.loop.create_task(self._weather_task()),
            'stock': self.bot.loop.create_task(self._stock_task())
        }
        self.logger.info("Task manager started")
        
    async def stop(self):
        """Stop all running tasks"""
        if not self._running:
            return
            
        self._running = False
        for name, task in self.tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.error(f"Error cancelling task {name}: {e}")
                    
        self.tasks.clear()
        self.logger.info("Task manager stopped")
        
    async def _weather_task(self):
        """Weather change task with enhanced error handling"""
        while self._running:
            try:
                await asyncio.sleep(10)
                weather = random.choice(list(self.data["weather"].keys()))
                await self.config.update_global_setting("current_weather", weather)
                self.last_weather_change = datetime.datetime.now()
                self.logger.debug(f"Weather changed to {weather}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in weather task: {e}")
                await asyncio.sleep(60)
                
    async def _stock_task(self):
        """Stock reset task with enhanced error handling"""
        while self._running:
            try:
                now = datetime.datetime.now()
                midnight = datetime.datetime.combine(
                    now.date() + datetime.timedelta(days=1),
                    datetime.time()
                )
                
                await asyncio.sleep((midnight - now).total_seconds())
                
                async with self.config.bait_stock() as bait_stock:
                    for bait, data in self.data["bait"].items():
                        bait_stock[bait] = data["daily_stock"]
                        
                self.last_reset = datetime.datetime.now()
                self.logger.info("Daily stock reset completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in stock reset task: {e}")
                await asyncio.sleep(300)
                
    @property
    def status(self) -> Dict[str, dict]:
        """Get current status of all tasks"""
        return {
            name: {
                'running': not task.done(),
                'failed': task.done() and task.exception() is not None,
                'exception': str(task.exception()) if task.done() and task.exception() else None
            }
            for name, task in self.tasks.items()
        }
