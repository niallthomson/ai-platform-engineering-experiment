import httpx
import boto3
from mcp.client.streamable_http import streamablehttp_client
from mcp_proxy_for_aws.sigv4_helper import SigV4HTTPXAuth
from mcp_proxy_for_aws.utils import get_service_name_and_region_from_endpoint


class PassthroughAuth(httpx.Auth):
    """Passes through authorization from incoming request."""
    
    def __init__(self, authorization_header: str, custom_header: str | None = None):
        if custom_header:
            self.header = custom_header
            self.value = authorization_header.split(" ", 1)[1]
        else:
            self.header = "Authorization"
            self.value = authorization_header
    
    def auth_flow(self, request: httpx.Request):
        request.headers[self.header] = self.value
        yield request


class StaticTokenAuth(httpx.Auth):
    """Static token authentication."""
    
    def __init__(self, token: str, header: str = "Authorization", use_bearer: bool = True):
        self.header = header
        self.value = f"Bearer {token}" if use_bearer else token
    
    def auth_flow(self, request: httpx.Request):
        request.headers[self.header] = self.value
        yield request


def create_auth(server_config, authorization_header: str | None) -> httpx.Auth | None:
    """Create auth handler based on server config."""
    
    auth = server_config.authentication
    
    if auth.mode == "passthrough" and authorization_header:
        return PassthroughAuth(authorization_header, auth.passthrough.header)
    elif auth.mode == "sigv4":
        service_name, region = get_service_name_and_region_from_endpoint(server_config.url)
        session = boto3.Session()
        credentials = session.get_credentials()
        return SigV4HTTPXAuth(credentials, service_name, region)
    elif auth.mode == "static":
        return StaticTokenAuth(auth.static.token, auth.static.header, auth.static.use_bearer)
    
    return None
