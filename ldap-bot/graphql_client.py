from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportServerError

class GraphQLClient:
    """Handles GraphQL client setup and operations for LLDAP API."""
    
    class UnauthorizedError(Exception):
        """Custom exception for 401 Unauthorized errors."""
        pass

    def __init__(self, login_url, auth_manager):
        self.login_url = login_url
        self.auth_manager = auth_manager
        self.client = None  # Initialized in initialize()

    async def initialize(self):
        """Initializes the GraphQL client with the current JWT token."""
        jwt_token = await self.auth_manager.get_jwt_token()
        transport = AIOHTTPTransport(
            url=f"{self.login_url}/api/graphql",
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        self.client = Client(transport=transport, 
                             fetch_schema_from_transport=True,
                             introspection_args={
                                 "input_value_deprecation": False
                             })

    async def execute_query(self, query, variables=None):
        """Executes a GraphQL query and returns the result."""
        try:
            async with self.client as session:
                return await session.execute(query, variable_values=variables or {})
        except TransportServerError as e:
            if e.code == 401:
                print("JWT token expired. Refreshing token and retrying...")
                await self.auth_manager.refresh()
                await self.initialize()  # Reinitialize client with new token
                async with self.client as session:
                    return await session.execute(query, variable_values=variables or {})
            print(f"GraphQL query error: {e}")
            raise

    async def execute_mutation(self, mutation, variables):
        """Executes a GraphQL mutation and returns the result."""
        try:
            async with self.client as session:
                return await session.execute(mutation, variable_values=variables)
        except TransportServerError as e:
            if e.code == 401:
                print("JWT token expired. Refreshing token and retrying...")
                await self.auth_manager.refresh()
                await self.initialize()  # Reinitialize client with new token
                async with self.client as session:
                    return await session.execute(mutation, variable_values=variables)
            print(f"GraphQL mutation error: {e}")
            raise