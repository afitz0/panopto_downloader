#!python3
import os
import time
import logging
from typing import List
from requests_oauthlib import OAuth2Session
import pickle
import pprint
import webbrowser
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingTCPServer
import datetime

from oauth2client.client import OAuth2Credentials

# This code uses this local URL as redirect target for Authorization Code
# Grant (Server-side Web Application)
REDIRECT_PORT = 9127
REDIRECT_URL = 'http://localhost:{}/redirect'.format(REDIRECT_PORT)


class GenericOAuth2Client():
    def __init__(self,
                 server: str,
                 client_id: str,
                 client_secret: str,
                 scopes: List[str],
                 auth_endpoint: str,
                 token_endpoint: str,
                 ssl_verify: bool = True) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.auth_endpoint = auth_endpoint
        self.token_endpoint = token_endpoint
        self.ssl_verify = ssl_verify

        # Create cache file name to store the refresh token. Use server &
        # client ID combination.
        self.cache_file: str = 'token_{0}_{1}.cache'.format(server, client_id)

        # Make oauthlib library accept non-HTTPS redirection.
        # This should not be applied if the redirect is hosted by actual
        # server (not localhost).
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    def credentials(self) -> OAuth2Credentials:
        delta = datetime.timedelta(days=15)
        expires_in = delta + datetime.datetime.utcnow()

        return OAuth2Credentials(
            scopes=self.scopes,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri=self.token_endpoint,
            access_token=self.__get_refreshed_access_token(),
            token_expiry=expires_in,
            user_agent='Python Client Library', refresh_token=self.__get_known_refresh_token()
        )

    def get_access_token_authorization_code_grant(self) -> str:
        '''
        Get OAuth2 access token by Authorization Code Grant (Server-side Web
        Application).

        This method initially tries to get a new access token from refresh
        token.

        If refresh token is not available or does not work, proceed to new
        authorization flow:
         1. To launch the browser to navigate authorization URL.
         2. To start temporary HTTP server at localhost:REDIRECT_PORT and block.
         3. When the redirect is received, HTTP server exits.
         4. To get access token and refresh token with given authentication
            code by redirection.
         5. Save the token object, which includes refresh_token, for later refresh operation.
        '''
        # First, try getting a new access token from refresh token.
        access_token: str = self.__get_refreshed_access_token()
        if access_token:
            return access_token

        # Then, fallback to the full authorization path. Offline access scope
        # is needed to get refresh token.
        if 'panopto' in self.token_endpoint:
            scope = self.scopes + ['offline_access']
        else:
            scope = self.scopes

        session = OAuth2Session(
            self.client_id, scope=scope, redirect_uri=REDIRECT_URL)

        # Open the authorization page by the browser.
        authorization_url, state = session.authorization_url(
            self.auth_endpoint)
        logging.debug(
            'Opening the browser for authorization: {0}'.format(authorization_url))
        webbrowser.open_new_tab(authorization_url)

        # Launch HTTP server to receive the redirect after authorization.
        redirected_path = ''
        with RedirectTCPServer() as httpd:
            logging.debug(
                'HTTP server started at port {0}. Waiting for redirect.'.format(REDIRECT_PORT))
            # Serve one request.
            httpd.handle_request()
            # The property may not be readable immediately. Wait until it becomes valid.
            while httpd.last_get_path is None:
                time.sleep(1)
            redirected_path = httpd.last_get_path

        logging.debug('Get a new access token with authorization code, which is ' +
                      'provided as return path: {0}'.format(redirected_path))
        session.fetch_token(self.token_endpoint, client_secret=self.client_secret,
                            authorization_response=redirected_path, verify=self.ssl_verify)
        self.__save_token_to_cache(session.token)

        return str(session.token['access_token'])

    def __get_refreshed_access_token(self) -> str:
        '''
        Private method of the class.
        Get a new access token from refresh token.
        Save the updated token object, which includes refresh_token, for later refresh operation.
        Returning None if failing to get the new access token with any reason.
        '''
        try:
            logging.debug('Read cached token from {0}'.format(self.cache_file))
            with open(self.cache_file, 'rb') as fr:
                token = pickle.load(fr)

            session = OAuth2Session(self.client_id, token=token)

            logging.debug('Get a new access token by using saved refresh token.')
            extra = {'client_id': self.client_id,
                     'client_secret': self.client_secret}
            session.refresh_token(self.token_endpoint,
                                  verify=self.ssl_verify, **extra)
            self.__save_token_to_cache(session.token)

            return str(session.token['access_token'])

        # Catch any failures (exceptions) and return with None.
        except Exception as e:
            logging.fatal('Failed to refresh access token: ' + str(e))
            return ''

    def __get_known_refresh_token(self) -> str:
        logging.debug('Read cached token from {0}'.format(self.cache_file))
        with open(self.cache_file, 'rb') as fr:
            token = pickle.load(fr)
        return str(token['refresh_token'])

    def __save_token_to_cache(self, token: str) -> None:
        '''
        Private method of the class.
        Save entire token object from oauthlib (not just refresh token).
        '''
        with open(self.cache_file, 'wb') as fw:
            pickle.dump(token, fw)
        logging.debug('OAuth2 flow provided the token below. Cache it to {0}'.format(
            self.cache_file))
        logging.debug(pprint.pformat(token, indent=4))


class RedirectTCPServer(ThreadingTCPServer):
    '''
    A helper class for Authorization Code Grant.
    Custom class of ThreadingTCPServer with RedirectHandler class as handler.
    last_get_path property is set whenever GET method is called by the handler.
    '''

    def __init__(self) -> None:
        # Class property, representing the path of the most recent GET call.
        self.last_get_path = None
        # Create an instance at REDIRECT_PORT with RedirectHandler class.
        super().__init__(('', REDIRECT_PORT), RedirectHandler)
        # Override the attribute of the server.
        self.allow_reuse_address = True


class RedirectHandler(BaseHTTPRequestHandler):
    '''
    A helper class for Authorization Code Grant.
    '''

    def do_GET(self) -> None:
        '''
        Handle a GET request. Set the path to the server's property.
        '''
        self.server.last_get_path = self.path  # type: ignore
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(('<html><body><p>Authorization redirect was received. ' +
                         'You may close this page.</p></body></html>').encode('utf-8'))
        self.wfile.flush()
