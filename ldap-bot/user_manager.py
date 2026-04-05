import random
import string
from gql import gql

class UserManager:    
    def __init__(self, graphql_client, ldap_manager, ldap_base_dn):
        self.graphql_client = graphql_client
        self.ldap_manager = ldap_manager
        self.ldap_base_dn = ldap_base_dn

    @staticmethod
    def generate_temp_password(length=12):
        """Generates a random temporary password."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    async def check_email_exists(self, email):
        """Checks if an email is already associated with an LLDAP account."""
        normalized_email = email.lower()
        query = gql("""
        query GetUserByEmail($email: String!) {
            users(filters: { eq: { field: "email", value: $email } }) {
                id
            }
        }
        """)
        result = await self.graphql_client.execute_query(query, {"email": normalized_email})
        return len(result.get("users", [])) > 0

    async def check_discord_id_exists(self, discord_id):
        """Checks if a Discord ID is already linked to an LLDAP account."""
        query = gql("""
        query GetUserByDiscordId($discordid: String!) {
            users(filters: { eq: { field: "discordid", value: $discordid } }) {
                id
            }
        }
        """)
        result = await self.graphql_client.execute_query(query, {"discordid": discord_id})
        return len(result.get("users", [])) > 0

    async def create_user(self, display_name, email, discord_id):
        temp_password = self.generate_temp_password()
        create_user_mutation = gql("""
        mutation CreateUser($input: CreateUserInput!) {
            createUser(user: $input) {
                id
            }
        }
        """)
        variables = {
            "input": {
                "id": display_name,  # This is now the chosen username
                "displayName": display_name,
                "email": email,
                "attributes": [{"name": "discordid", "value": [discord_id]}]
            }
        }

        try:
            result = await self.graphql_client.execute_mutation(create_user_mutation, variables)
            user_id = result["createUser"]["id"]

            # Set LDAP password
            user_dn = f"uid={user_id},ou=people,{self.ldap_base_dn}"
            if not self.ldap_manager.set_password(user_dn, temp_password):
                return None, "Failed to set LDAP password"

            return temp_password, None
        except Exception as e:
            return None, str(e)
