import asyncio
from .environment import EnvironmentConfig

from .discord_bot import DiscordBot

async def main():
    # Load environment variables
    config = EnvironmentConfig()

    # Initialize Discord bot with Lifetime parameters
    bot = DiscordBot(
        config
    )

    # Start the bot within the same event loop
    await bot.start(config.lldap_login_url, config.public_url)

if __name__ == "__main__":
    asyncio.run(main())