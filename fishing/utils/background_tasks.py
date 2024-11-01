# utils/background_tasks.py

import asyncio
import datetime
import random
import logging
from typing import Dict, Any

logger = logging.getLogger('fishing.tasks')

class BackgroundTasks:
    def __init__(self, bot, config, data):
        self.bot = bot
        self.config = config
        self.data = data
        self.tasks = []
        self.last_stock_reset = None
        self.logger = logging.getLogger('fishing.tasks')

    async def weather_change_task(self):
        """Periodically change the weather."""
        while True:
            try:
                await asyncio.sleep(3600)  # Change weather every hour
                weather = random.choice(list(self.data["weather"].keys()))
                await self.config.current_weather.set(weather)
                logger.debug(f"Weather changed to {weather}")
                
            except asyncio.CancelledError:
                logger.info("Weather change task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in weather_change_task: {e}", exc_info=True)
                await asyncio.sleep(60)  # Retry after 1 minute on error

    async def daily_stock_reset(self):
        """Reset the daily stock of shop items at midnight."""
        while True:
            try:
                now = datetime.datetime.now()
                midnight = datetime.datetime.combine(
                    now.date() + datetime.timedelta(days=1),
                    datetime.time()
                )
                
                # Log current stock before reset
                current_stock = await self.config.bait_stock()
                self.logger.debug(f"Current stock before reset: {current_stock}")
                
                await asyncio.sleep((midnight - now).total_seconds())
                
                # Use atomic operation for stock reset
                async with self.config.bait_stock() as bait_stock:
                    for bait, data in self.data["bait"].items():
                        bait_stock[bait] = data["daily_stock"]
                
                self.last_stock_reset = datetime.datetime.now()
                new_stock = await self.config.bait_stock()
                self.logger.info(f"Daily stock reset completed. New stock: {new_stock}")
                
            except asyncio.CancelledError:
                self.logger.info("Daily stock reset task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in daily_stock_reset: {e}", exc_info=True)
                await asyncio.sleep(300)  # Retry after 5 minutes on error
                
    def start_tasks(self):
        """Initialize and start background tasks."""
        try:
            if self.tasks:  # Cancel any existing tasks
                self.logger.debug("Cancelling existing tasks")
                for task in self.tasks:
                    task.cancel()
            self.tasks = []

            # Create new tasks
            self.tasks.append(
                self.bot.loop.create_task(self.weather_change_task())
            )
            self.tasks.append(
                self.bot.loop.create_task(self.daily_stock_reset())
            )
            self.logger.info(f"Background tasks started successfully. Total tasks: {len(self.tasks)}")
            
        except Exception as e:
            self.logger.error(f"Error starting background tasks: {e}", exc_info=True)

    def cancel_tasks(self):
        """Cancel all running background tasks."""
        try:
            for task in self.tasks:
                task.cancel()
            self.tasks = []
            logger.info("Background tasks cancelled successfully")
        except Exception as e:
            logger.error(f"Error cancelling tasks: {e}", exc_info=True)
