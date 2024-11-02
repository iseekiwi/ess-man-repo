if not isinstance(settings, dict):
                self.logger.warning("Invalid settings format, resetting to default")
                validated["settings"] = DEFAULT_USER_DATA["settings"].copy()
            else:
                validated["settings"] = {
                    "notifications": bool(settings.get("notifications", True)),
                    "auto_sell": bool(settings.get("auto_sell", False))
                }
                
            # Validate equipped bait exists in inventory
            if validated["equipped_bait"] and validated["equipped_bait"] not in validated["bait"]:
                self.logger.warning("Equipped bait not in inventory, resetting")
                validated["equipped_bait"] = None
                
            # Validate rod exists in purchased rods
            if validated["rod"] not in validated["purchased_rods"]:
                self.logger.warning("Invalid rod equipped, resetting to Basic Rod")
                validated["rod"] = "Basic Rod"
                
            return validated
            
        except Exception as e:
            self.logger.error(f"Error in user data validation: {e}")
            return DEFAULT_USER_DATA.copy()

    async def get_user_data(self, user_id: int) -> ConfigResult[Dict[str, Any]]:
        """
        Get user data with enhanced validation and caching.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            ConfigResult containing user data or error information
        """
        try:
            cache_key = f"user_{user_id}"
            
            # Check cache first
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])
                
            # Fetch data from config
            try:
                data = await self.config.user_from_id(user_id).all()
            except Exception as e:
                self.logger.error(f"Error fetching user data: {e}")
                return ConfigResult(False, error=str(e), error_code="FETCH_ERROR")
                
            # Validate and repair data
            try:
                validated_data = await self._validate_user_data(data)
            except Exception as e:
                self.logger.error(f"Error validating user data: {e}")
                return ConfigResult(False, error=str(e), error_code="VALIDATION_ERROR")
                
            # Update cache
            self._cache[cache_key] = validated_data
            
            return ConfigResult(True, validated_data)
            
        except Exception as e:
            self.logger.error(f"Error in get_user_data: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def update_user_data(
        self,
        user_id: int,
        updates: Dict[str, Any],
        fields: Optional[List[str]] = None
    ) -> ConfigResult[bool]:
        """
        Update user data with enhanced validation and field filtering.
        
        Args:
            user_id: Discord user ID
            updates: Dictionary of updates
            fields: Optional list of fields to update
            
        Returns:
            ConfigResult indicating success or failure
        """
        try:
            self.logger.debug(f"Updating user data for {user_id}")
            self.logger.debug(f"Updates: {updates}")
            self.logger.debug(f"Fields: {fields}")
            
            # Get current data
            current_result = await self.get_user_data(user_id)
            if not current_result.success:
                return ConfigResult(False, error="Failed to get current data", error_code="GET_ERROR")
                
            current_data = current_result.data
            
            # Create working copy
            update_data = current_data.copy()
            
            # Process updates
            if fields:
                # Update only specified fields
                for field in fields:
                    if field not in updates:
                        continue
                        
                    if field == "bait":
                        # Special handling for bait dictionary
                        current_bait = update_data.get("bait", {})
                        new_bait = updates["bait"]
                        if isinstance(new_bait, dict):
                            merged_bait = await self._validate_dictionary_merge(
                                current_bait,
                                new_bait,
                                "bait"
                            )
                            update_data["bait"] = merged_bait
                    elif isinstance(updates[field], dict):
                        if not isinstance(update_data.get(field), dict):
                            update_data[field] = {}
                        update_data[field] = await self._validate_dictionary_merge(
                            update_data[field],
                            updates[field],
                            field
                        )
                    else:
                        update_data[field] = updates[field]
            else:
                # Update all fields
                for key, value in updates.items():
                    if isinstance(value, dict):
                        if not isinstance(update_data.get(key), dict):
                            update_data[key] = {}
                        update_data[key] = await self._validate_dictionary_merge(
                            update_data[key],
                            value,
                            key
                        )
                    else:
                        update_data[key] = value
                        
            # Validate updated data
            validated_data = await self._validate_user_data(update_data)
            
            # Save to config
            group = self.config.user_from_id(user_id)
            for key, value in validated_data.items():
                if key in updates or not fields:
                    try:
                        await group.set_raw(key, value=value)
                    except Exception as e:
                        self.logger.error(f"Error saving {key}: {e}")
                        return ConfigResult(False, error=f"Failed to save {key}", error_code="SAVE_ERROR")
                        
            # Invalidate cache
            await self.invalidate_cache(f"user_{user_id}")
            
            # Verify update
            verify_result = await self.get_user_data(user_id)
            if not verify_result.success:
                return ConfigResult(False, error="Failed to verify update", error_code="VERIFY_ERROR")
                
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in update_user_data: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def get_global_setting(self, key: str) -> ConfigResult[Any]:
        """Get global setting with caching"""
        try:
            cache_key = f"global_{key}"
            if cache_key in self._cache:
                return ConfigResult(True, self._cache[cache_key])
                
            try:
                value = await self.config.get_raw(key)
                self._cache[cache_key] = value
                return ConfigResult(True, value)
            except Exception as e:
                return ConfigResult(False, error=str(e), error_code="FETCH_ERROR")
                
        except Exception as e:
            self.logger.error(f"Error in get_global_setting: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def update_global_setting(self, key: str, value: Any) -> ConfigResult[bool]:
        """Update global setting with validation"""
        try:
            # Validate value based on key
            if key == "bait_stock" and not isinstance(value, dict):
                return ConfigResult(False, error="Invalid bait stock format", error_code="VALIDATION_ERROR")
                
            await self.config.set_raw(key, value=value)
            await self.invalidate_cache(f"global_{key}")
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in update_global_setting: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def get_all_global_settings(self) -> ConfigResult[Dict[str, Any]]:
        """Get all global settings with caching"""
        try:
            if "global_all" in self._cache:
                return ConfigResult(True, self._cache["global_all"])
                
            data = await self.config.all()
            self._cache["global_all"] = data
            return ConfigResult(True, data)
            
        except Exception as e:
            self.logger.error(f"Error in get_all_global_settings: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def reset_user_data(self, user_id: int) -> ConfigResult[bool]:
        """Reset user data to defaults"""
        try:
            await self.config.user_from_id(user_id).clear()
            await self.config.user_from_id(user_id).set(DEFAULT_USER_DATA)
            await self.invalidate_cache(f"user_{user_id}")
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in reset_user_data: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    async def invalidate_cache(self, key: Optional[str] = None):
        """Invalidate specific cache key or entire cache"""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    async def refresh_cache(self, user_id: int) -> ConfigResult[bool]:
        """Force refresh of user data cache"""
        try:
            cache_key = f"user_{user_id}"
            data = await self.config.user_from_id(user_id).all()
            validated_data = await self._validate_user_data(data)
            self._cache[cache_key] = validated_data
            return ConfigResult(True, True)
            
        except Exception as e:
            self.logger.error(f"Error in refresh_cache: {e}")
            return ConfigResult(False, error=str(e), error_code="GENERAL_ERROR")

    @asynccontextmanager
    async def config_transaction(self):
        """Context manager for handling configuration transactions"""
        transaction_cache = {}
        try:
            yield transaction_cache
            # On successful completion, apply changes
            for key, value in transaction_cache.items():
                if key.startswith("user_"):
                    user_id = int(key.split("_")[1])
                    await self.update_user_data(user_id, value)
                elif key.startswith("global_"):
                    setting_key = key.replace("global_", "")
                    await self.update_global_setting(setting_key, value)
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            raise
        finally:
            transaction_cache.clear()
