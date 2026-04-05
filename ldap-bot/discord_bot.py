import discord
from discord.ext import tasks
from discord import app_commands
from .auth_manager import AuthManager
from .graphql_client import GraphQLClient
from .ldap_manager import LDAPManager
from .user_manager import UserManager

class DiscordBot:
    """Handles Discord bot setup, commands, and background tasks."""
    
    def __init__(self, config):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True

        self.config = config
        self.bot = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.bot)
        self.token = config.discord_bot_token

        self.approved_role_name = config.approved_role_name

        self.user_manager = None
        self.auth_manager = None
        self.graphql_client = None

        self.lldap_login_url = None
        self.service_name = config.service_name
        self.public_url = None

    async def start(self, lldap_login_url, public_url):
        """Starts the Discord bot within the existing event loop."""
        # Extract username from LDAP_BIND_DN
        ldap_username = self.config.get_ldap_username()

        # Initialize AuthManager for token-based authentication
        self.auth_manager = AuthManager(self.config.lldap_login_url, ldap_username, self.config.ldap_bind_password)
        await self.auth_manager.initialize()

        # Initialize GraphQL client with AuthManager
        self.graphql_client = GraphQLClient(self.config.lldap_login_url, self.auth_manager)
        await self.graphql_client.initialize()

        # Initialize LDAP manager
        self.ldap_manager = LDAPManager(self.config.ldap_server, self.config.ldap_bind_dn, self.config.ldap_bind_password)

        # Initialize user manager
        self.user_manager = UserManager(self.graphql_client, self.ldap_manager, self.config.ldap_base_dn)

        self.lldap_login_url = lldap_login_url
        self.public_url = public_url
        self.setup_commands()
        self.bot.event(self.on_ready)
        
        try:
            await self.bot.start(self.token)
        finally:
            self.auth_manager.close()

    async def on_ready(self):
        """Handles bot startup, syncs commands, and starts background tasks."""
        print(f"{self.bot.user} is online!")
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")

        except Exception as e:
            print(f"Failed to sync commands: {e}")

    async def register_command(self, interaction: discord.Interaction, email: str, name: str = None):
        """Handles the /register command to create a new LLDAP user with appropriate group assignment."""
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        member = guild.get_member(interaction.user.id)
        approved_role = discord.utils.get(guild.roles, name=self.approved_role_name)

        has_approved = approved_role and approved_role in member.roles

        if not has_approved:
            await interaction.followup.send(
                f"❌ You must have the **{self.approved_role_name}** role to register an account.", ephemeral=True
            )
            return

        # Normalize email and extract user details
        normalized_email = email.lower()
        user_id = str(interaction.user.id)
        # Use provided username if given, otherwise default to Discord username
        chosen_username = name if name else interaction.user.name

        # Validate username (alphanumeric and max 20 characters)
        if not chosen_username or not chosen_username.isalnum() or len(chosen_username) > 20:
            await interaction.followup.send(
                "❌ Username must be alphanumeric (letters and numbers only) and no longer than 20 characters.", ephemeral=True
            )
            return
        
        # Check if email is already associated with an LLDAP account
        if await self.user_manager.check_email_exists(normalized_email):
            await interaction.followup.send(
                "❌ This email is already associated with an account.", ephemeral=True
            )
            return
        
        # Check if Discord ID is already linked to an LLDAP account
        if await self.user_manager.check_discord_id_exists(user_id):
            await interaction.followup.send(
                "❌ You have already linked your Discord to an account.", ephemeral=True
            )
            return
        
        # Create user in LLDAP with appropriate group assignments
        temp_password, error = await self.user_manager.create_user(
            chosen_username, normalized_email, user_id
        )

        if temp_password:
            await interaction.followup.send(
                f":white_check_mark: **__Account Created!__**\n\n"
                f"__**Use this link to log in and change your password:**__ {self.public_url}\n\n"
                f"**Username**: `{chosen_username}`\n"
                f"**Temporary Password**: `{temp_password}`",
                ephemeral=True
            )
        else:
            if "UNIQUE constraint failed" in str(error):
                await interaction.followup.send(
                    "❌ This username or Discord ID is already in use.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to create an account: {error}", ephemeral=True
                )

    def setup_commands(self):
        """Sets up slash commands for the bot."""
        @self.tree.command(name="register", description="Register a new LLDAP account based on your Discord roles")
        @app_commands.describe(
            email="Your email address",
            name="🔧 Choose your LLDAP username (optional, defaults to Discord username, max 30 chars, alphanumeric)"
        )
        async def register(interaction: discord.Interaction, email: str, name: str = None):
            await self.register_command(interaction, email, name)

        print("Setup bot commands")