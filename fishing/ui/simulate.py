# ui/simulate.py

import discord
from discord.ui import Button, Select
from typing import Dict, Optional
from .base import BaseView
from ..utils.logging_config import get_logger
from ..utils.profit_simulator import ProfitSimulator

logger = get_logger('simulate')

TIME_CYCLE = ["Dawn", "Day", "Dusk", "Night"]


class SimulationMenuView(BaseView):
    """Interactive simulation menu for analyzing fishing setups"""

    def __init__(self, cog, ctx):
        super().__init__(cog, ctx, timeout=300)
        self.logger = get_logger('simulate.view')

        # Defaults
        self.selected_rod = "Basic Rod"
        self.selected_bait = "Worm"
        self.selected_location = "Pond"
        self.selected_weather = "Sunny"
        self.selected_time = "Day"
        self.selected_level = 99
        self.duration_hours = 1
        self.catches_per_hour = 360
        self.results = None

    async def setup(self):
        """Async setup to initialize the view"""
        try:
            self.logger.debug(f"Setting up SimulationMenuView for {self.ctx.author.name}")
            await self.initialize_view()
            return self
        except Exception as e:
            self.logger.error(f"Error in SimulationMenuView setup: {e}", exc_info=True)
            raise

    async def initialize_view(self):
        """Build the view components based on current state"""
        try:
            self.clear_items()

            if self.results is not None:
                # Results mode — show navigation buttons
                back_btn = Button(
                    label="Back to Config",
                    custom_id="back_config",
                    style=discord.ButtonStyle.grey,
                    row=0
                )
                back_btn.callback = self.handle_button
                self.add_item(back_btn)

                run_again_btn = Button(
                    label="Run Again",
                    custom_id="run_sim",
                    style=discord.ButtonStyle.green,
                    row=0
                )
                run_again_btn.callback = self.handle_button
                self.add_item(run_again_btn)
                return

            # Config mode — 4 selects + 1 button row

            # Row 0: Rod select
            rod_select = Select(
                custom_id="rod_select",
                placeholder="Select Rod",
                row=0
            )
            for rod_name, rod_data in self.cog.data["rods"].items():
                rod_select.add_option(
                    label=rod_name,
                    value=rod_name,
                    description=f"Catch bonus: +{rod_data['chance']*100:.0f}%",
                    default=(rod_name == self.selected_rod)
                )
            rod_select.callback = self.handle_select
            self.add_item(rod_select)

            # Row 1: Bait select
            bait_select = Select(
                custom_id="bait_select",
                placeholder="Select Bait",
                row=1
            )
            for bait_name, bait_data in self.cog.data["bait"].items():
                bait_select.add_option(
                    label=bait_name,
                    value=bait_name,
                    description=f"+{bait_data['catch_bonus']*100:.0f}% catch | Cost: {bait_data['cost']}/use",
                    default=(bait_name == self.selected_bait)
                )
            bait_select.callback = self.handle_select
            self.add_item(bait_select)

            # Row 2: Location select
            loc_select = Select(
                custom_id="location_select",
                placeholder="Select Location",
                row=2
            )
            for loc_name, loc_data in self.cog.data["locations"].items():
                loc_select.add_option(
                    label=loc_name,
                    value=loc_name,
                    description=loc_data["description"][:100],
                    default=(loc_name == self.selected_location)
                )
            loc_select.callback = self.handle_select
            self.add_item(loc_select)

            # Row 3: Weather select
            weather_select = Select(
                custom_id="weather_select",
                placeholder="Select Weather",
                row=3
            )
            for w_name, w_data in self.cog.data["weather"].items():
                bonus_str = f"{w_data['catch_bonus']*100:+.0f}% catch"
                if w_data.get("rare_bonus"):
                    bonus_str += f" | {w_data['rare_bonus']*100:+.0f}% rare"
                weather_select.add_option(
                    label=w_name,
                    value=w_name,
                    description=bonus_str[:100],
                    default=(w_name == self.selected_weather)
                )
            weather_select.callback = self.handle_select
            self.add_item(weather_select)

            # Row 4: Time cycle, duration controls, run button
            time_btn = Button(
                label=f"Time: {self.selected_time}",
                custom_id="time_cycle",
                style=discord.ButtonStyle.blurple,
                row=4
            )
            time_btn.callback = self.handle_button
            self.add_item(time_btn)

            dur_minus = Button(
                label="-",
                custom_id="dur_minus",
                style=discord.ButtonStyle.grey,
                row=4,
                disabled=(self.duration_hours <= 1)
            )
            dur_minus.callback = self.handle_button
            self.add_item(dur_minus)

            dur_label = Button(
                label=f"{self.duration_hours}h | {self.catches_per_hour}/hr",
                custom_id="dur_display",
                style=discord.ButtonStyle.grey,
                row=4,
                disabled=True
            )
            self.add_item(dur_label)

            dur_plus = Button(
                label="+",
                custom_id="dur_plus",
                style=discord.ButtonStyle.grey,
                row=4,
                disabled=(self.duration_hours >= 24)
            )
            dur_plus.callback = self.handle_button
            self.add_item(dur_plus)

            run_btn = Button(
                label="Run Simulation",
                custom_id="run_sim",
                style=discord.ButtonStyle.green,
                row=4
            )
            run_btn.callback = self.handle_button
            self.add_item(run_btn)

        except Exception as e:
            self.logger.error(f"Error in initialize_view: {e}", exc_info=True)
            raise

    async def generate_embed(self) -> discord.Embed:
        """Generate embed for config or results mode"""
        try:
            if self.results is not None:
                return self._build_results_embed()
            return self._build_config_embed()
        except Exception as e:
            self.logger.error(f"Error generating embed: {e}", exc_info=True)
            return discord.Embed(
                title="Error",
                description="Failed to generate simulation embed.",
                color=discord.Color.red()
            )

    def _build_config_embed(self) -> discord.Embed:
        """Build the configuration overview embed"""
        rod_data = self.cog.data["rods"][self.selected_rod]
        bait_data = self.cog.data["bait"][self.selected_bait]
        weather_data = self.cog.data["weather"][self.selected_weather]
        time_data = self.cog.data["time"][self.selected_time]
        loc_data = self.cog.data["locations"][self.selected_location]

        # Check if weather affects selected location
        weather_applies = self.selected_location in weather_data.get("affects_locations", [])

        # Calculate total catch chance (with bait effectiveness and level bonus)
        from ..data.fishing_data import level_catch_bonus
        lvl_bonus = level_catch_bonus(self.selected_level)
        rod_bonus = rod_data["chance"]
        bait_effectiveness = bait_data.get("effectiveness", {}).get(self.selected_location, 1.0)
        bait_bonus = bait_data["catch_bonus"] * bait_effectiveness
        weather_bonus = 0
        if weather_applies:
            weather_bonus = weather_data.get("catch_bonus", 0)
            weather_bonus += weather_data.get("location_bonus", {}).get(self.selected_location, 0)
            weather_bonus += weather_data.get("time_multiplier", {}).get(self.selected_time, 0)
        time_bonus = time_data.get("catch_bonus", 0)
        total_chance = max(0.0, min(1.0, lvl_bonus + rod_bonus + bait_bonus + weather_bonus + time_bonus))

        embed = discord.Embed(
            title="Fishing Simulation Setup",
            description="Configure your simulation parameters, then press **Run Simulation**.",
            color=discord.Color.blue()
        )

        bait_line = f"Bait: **{self.selected_bait}** (+{bait_bonus*100:.0f}%)"
        if bait_effectiveness != 1.0:
            bait_line += f" ({bait_effectiveness}x eff.)"
        embed.add_field(
            name="Equipment",
            value=(
                f"Level: **{self.selected_level}** (+{lvl_bonus*100:.1f}%)\n"
                f"Rod: **{self.selected_rod}** (+{rod_bonus*100:.0f}%)\n"
                f"{bait_line}\n"
                f"Location: **{self.selected_location}**"
            ),
            inline=True
        )

        weather_status = f"**{self.selected_weather}**"
        if not weather_applies:
            weather_status += " (no effect here)"
        embed.add_field(
            name="Conditions",
            value=(
                f"Weather: {weather_status}\n"
                f"Time: **{self.selected_time}** ({time_bonus*100:+.0f}%)\n"
                f"Duration: **{self.duration_hours}h** ({self.catches_per_hour}/hr)"
            ),
            inline=True
        )

        # Catch chance breakdown
        bait_str = f"Bait: `{bait_bonus*100:+.1f}%`"
        if bait_effectiveness != 1.0:
            bait_str += f" (base {bait_data['catch_bonus']*100:.0f}% x {bait_effectiveness})"
        breakdown = [
            f"Level: `{lvl_bonus*100:+.1f}%`",
            f"Rod: `{rod_bonus*100:+.1f}%`",
            bait_str,
        ]
        if weather_applies:
            breakdown.append(f"Weather: `{weather_bonus*100:+.1f}%`")
        else:
            breakdown.append("Weather: `+0.0%` (location not affected)")
        breakdown.append(f"Time: `{time_bonus*100:+.1f}%`")
        breakdown.append(f"**Total: `{total_chance*100:.1f}%`**")

        embed.add_field(
            name="Catch Chance Preview",
            value="\n".join(breakdown),
            inline=False
        )

        # Rarity modifier preview
        loc_mods = loc_data["fish_modifiers"]
        rare_bonus = 0
        if weather_applies:
            rare_bonus = weather_data.get("rare_bonus", 0)
        time_rare = time_data.get("rare_bonus", 0)

        rarity_lines = []
        for fish_type, fish_data_item in self.cog.data["fish"].items():
            base = fish_data_item["chance"]
            loc_mod = loc_mods[fish_type]
            multiplier = 1.0
            if weather_applies and fish_data_item["rarity"] in ["rare", "legendary"]:
                multiplier += rare_bonus + time_rare
                specific = weather_data.get("specific_rarity_bonus", {}).get(fish_type, 0)
                multiplier += specific
            final = base * loc_mod * multiplier * 100
            rarity_lines.append(f"{fish_type}: `{final:.2f}%` (loc: {loc_mod}x)")

        embed.add_field(
            name="Rarity Weights",
            value="\n".join(rarity_lines),
            inline=False
        )

        total_catches = self.duration_hours * self.catches_per_hour
        embed.set_footer(text=f"Total simulated catches: {total_catches:,}")

        return embed

    def _build_results_embed(self) -> discord.Embed:
        """Build the simulation results embed"""
        r = self.results
        total_attempts = r["duration_hours"] * r["catches_per_hour"]
        total_fish = sum(r["rarity_breakdown"].values())
        total_items = total_fish + r.get("junk_caught", 0)

        embed = discord.Embed(
            title="Fishing Simulation Results",
            description=(
                f"**{r['rod']}** + **{r['bait']}** at **{r['location']}**\n"
                f"Weather: **{r['weather']}** | Time: **{r['time_of_day']}** | "
                f"Duration: **{r['duration_hours']}h**"
            ),
            color=discord.Color.green()
        )

        # Catch statistics
        fish_rate = (total_fish / total_attempts * 100) if total_attempts else 0
        junk_rate = (r.get("junk_caught", 0) / total_attempts * 100) if total_attempts else 0
        nothing_rate = (r.get("nothing_caught", 0) / total_attempts * 100) if total_attempts else 0
        catch_lines = [
            f"Total Fish: **{total_fish:,}** ({fish_rate:.1f}%)",
            f"Junk: **{r.get('junk_caught', 0):,}** ({junk_rate:.1f}%)",
            f"Nothing: **{r.get('nothing_caught', 0):,}** ({nothing_rate:.1f}%)",
        ]
        if r.get("bonus_catches", 0):
            catch_lines.append(f"Bonus Catches: **{r['bonus_catches']:,}** (from weather)")
        embed.add_field(
            name="Catch Statistics",
            value="\n".join(catch_lines),
            inline=False
        )

        # Rarity distribution: expected vs actual
        expected = r.get("expected_rarity", {})
        rarity_lines = []
        for rarity, count in r["rarity_breakdown"].items():
            actual_pct = (count / total_fish * 100) if total_fish > 0 else 0
            expect_pct = expected.get(rarity, 0)
            diff = actual_pct - expect_pct
            diff_str = f"{diff:+.1f}%" if diff != 0 else "0.0%"
            per_hour = count / r["duration_hours"] if r["duration_hours"] else 0
            rarity_lines.append(
                f"{rarity.title()}: **{count:,}** (~{per_hour:.0f}/hr)\n"
                f"  Expected: `{expect_pct:.1f}%` | Actual: `{actual_pct:.1f}%` | Diff: `{diff_str}`"
            )
        embed.add_field(
            name="Rarity Distribution (Expected vs Actual)",
            value="\n".join(rarity_lines),
            inline=False
        )

        # Financial analysis
        profit_per_hour = r["net_profit"] / r["duration_hours"] if r["duration_hours"] else 0
        profit_per_catch = r["net_profit"] / total_fish if total_fish else 0
        avg_fish_value = r.get("gross_profit", 0) / total_items if total_items else 0
        embed.add_field(
            name="Financial Analysis",
            value=(
                f"Gross Revenue: **{r['gross_profit']:,}** coins\n"
                f"Bait Cost: **{r['bait_cost']:,}** coins\n"
                f"Net Profit: **{r['net_profit']:,}** coins\n"
                f"Profit/Hour: **{profit_per_hour:,.0f}** coins\n"
                f"Profit/Catch: **{profit_per_catch:.1f}** coins\n"
                f"Avg Value/Item: **{avg_fish_value:.1f}** coins"
            ),
            inline=True
        )

        # XP estimate
        xp_per_hour = r['estimated_xp'] // r['duration_hours'] if r['duration_hours'] else 0
        xp_per_catch = r['estimated_xp'] / total_fish if total_fish else 0
        embed.add_field(
            name="XP Estimate",
            value=(
                f"Total XP: **{r['estimated_xp']:,}**\n"
                f"XP/Hour: **{xp_per_hour:,}**\n"
                f"XP/Catch: **{xp_per_catch:.1f}**"
            ),
            inline=True
        )

        # Active modifiers
        bait_eff = r['modifiers'].get('bait_effectiveness', 1.0)
        bait_mod = f"Bait: `{r['modifiers']['bait_bonus']*100:+.1f}%`"
        if bait_eff != 1.0:
            bait_mod += f" ({bait_eff}x eff.)"
        mod_lines = [
            f"Level: `{r['modifiers']['level_bonus']*100:+.1f}%`",
            f"Rod: `{r['modifiers']['rod_bonus']*100:+.1f}%`",
            bait_mod,
        ]
        if r["modifiers"]["weather_applies"]:
            mod_lines.append(f"Weather: `{r['modifiers']['weather_bonus']*100:+.1f}%`")
            if r["modifiers"].get("weather_rare_bonus"):
                mod_lines.append(f"Weather Rare: `{r['modifiers']['weather_rare_bonus']*100:+.1f}%`")
        else:
            mod_lines.append("Weather: `N/A` (location not affected)")
        mod_lines.append(f"Time: `{r['modifiers']['time_bonus']*100:+.1f}%`")
        if r["modifiers"].get("time_rare_bonus"):
            mod_lines.append(f"Time Rare: `{r['modifiers']['time_rare_bonus']*100:+.1f}%`")
        mod_lines.append(f"**Total Catch: `{r['modifiers']['total_chance']*100:.1f}%`**")
        embed.add_field(
            name="Active Modifiers",
            value="\n".join(mod_lines),
            inline=False
        )

        embed.set_footer(
            text=f"Simulated {total_attempts:,} attempts over {r['duration_hours']}h at {r['catches_per_hour']}/hr"
        )

        return embed

    async def handle_select(self, interaction: discord.Interaction):
        """Handle select menu interactions"""
        try:
            custom_id = interaction.data["custom_id"]
            value = interaction.data["values"][0]

            if custom_id == "rod_select":
                self.selected_rod = value
            elif custom_id == "bait_select":
                self.selected_bait = value
            elif custom_id == "location_select":
                self.selected_location = value
            elif custom_id == "weather_select":
                self.selected_weather = value

            self.logger.debug(f"Selection changed: {custom_id} = {value}")
            await self.initialize_view()
            embed = await self.generate_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            self.logger.error(f"Error in handle_select: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred.", ephemeral=True, delete_after=2
                )

    async def handle_button(self, interaction: discord.Interaction):
        """Handle button interactions"""
        try:
            custom_id = interaction.data["custom_id"]

            if custom_id == "time_cycle":
                idx = TIME_CYCLE.index(self.selected_time)
                self.selected_time = TIME_CYCLE[(idx + 1) % len(TIME_CYCLE)]

            elif custom_id == "dur_minus":
                self.duration_hours = max(1, self.duration_hours - 1)

            elif custom_id == "dur_plus":
                self.duration_hours = min(24, self.duration_hours + 1)

            elif custom_id == "run_sim":
                await interaction.response.defer()
                await self.run_simulation(interaction)
                return

            elif custom_id == "back_config":
                self.results = None

            await self.initialize_view()
            embed = await self.generate_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            self.logger.error(f"Error in handle_button: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An error occurred.", ephemeral=True, delete_after=2
                )

    async def run_simulation(self, interaction: discord.Interaction):
        """Execute the simulation and display results"""
        try:
            self.logger.debug(
                f"Running simulation: {self.selected_rod} + {self.selected_bait} "
                f"@ {self.selected_location}, {self.selected_weather}, {self.selected_time}, "
                f"{self.duration_hours}h"
            )

            simulator = ProfitSimulator(self.cog.data)
            self.results = simulator.analyze_full_setup(
                rod=self.selected_rod,
                bait=self.selected_bait,
                location=self.selected_location,
                weather=self.selected_weather,
                time_of_day=self.selected_time,
                duration_hours=self.duration_hours,
                catches_per_hour=self.catches_per_hour,
                level=self.selected_level,
            )

            await self.initialize_view()
            embed = await self.generate_embed()
            await self.message.edit(embed=embed, view=self)

        except Exception as e:
            self.logger.error(f"Error running simulation: {e}", exc_info=True)
            msg = await interaction.followup.send(
                "An error occurred while running the simulation.",
                ephemeral=True, wait=True
            )
            self.cog.bot.loop.create_task(self.delete_after_delay(msg))
