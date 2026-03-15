from .main import WordCloudCog


async def setup(bot):
    await bot.add_cog(WordCloudCog(bot))
