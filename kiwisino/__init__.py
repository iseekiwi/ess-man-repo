from .main import Kiwisino


async def setup(bot):
    await bot.add_cog(Kiwisino(bot))
