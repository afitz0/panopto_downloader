from oauth.client import GenericOAuth2Client
import json
import os

# Typical scope for accessing Panopto API.
DEFAULT_SCOPE = ['openid', 'api']


class PanoptoOAuth2:
    def __init__(self, server: str, client_secrets_file: str) -> None:
        if client_secrets_file == '' or client_secrets_file is None:
            raise ValueError(
                "Empty credentials file. Cannot continue. Create and pass in a file containing Panopto API tokens.")  # noqa: E501

        creds = {}
        with open(os.path.expanduser(client_secrets_file)) as f:
            creds = json.loads(f.read())

        if creds['client_id'] is None or creds['client_secret'] is None:
            raise ValueError(
                "Could not parse Panopto API credentials from file "
                + client_secrets_file)

        self.authorization_endpoint = \
            'https://{0}/Panopto/oauth2/connect/authorize'.format(server)
        self.access_token_endpoint = \
            'https://{0}/Panopto/oauth2/connect/token'.format(server)

        # Create OAuth2 client
        self.client = GenericOAuth2Client(
            auth_endpoint=self.authorization_endpoint,
            client_id=creds['client_id'],
            client_secret=creds['client_secret'],
            token_endpoint=self.access_token_endpoint,
            scopes=DEFAULT_SCOPE,
            server=server)

    def refresh_access_token(self) -> str:
        return self.client.get_access_token_authorization_code_grant()
