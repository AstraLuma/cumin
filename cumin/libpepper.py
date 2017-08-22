'''
A Python library for working with Salt's REST API

(Specifically the rest_cherrypy netapi module.)

'''
import json
import logging
from six.moves.urllib import parse as urlparse
import requests
from functools import partial
from .sse import stream_sse

logger = logging.getLogger('pepper')


class SaltTokenAuth(requests.auth.AuthBase):
    def __init__(self, token):
        super().__init__()
        self.token = token

    def __call__(self, request):
        if self.token:
            request.headers.setdefault('X-Auth-Token', self.token)
        return request


class PepperException(Exception):
    pass


class MissingLogin(PepperException):
    """
    Authentication required
    """


class AuthenticationDenied(PepperException):
    """
    401:Authentication denied
    """


class ServerError(PepperException):
    """
    500:Server error.
    """


class SaltApi(object):
    '''
    A thin wrapper for making HTTP calls to the salt-api rest_cherrpy REST
    interface

    >>> api = Pepper('https://localhost:8000')
    >>> api.login('saltdev', 'saltdev', 'pam')
    {"return": [
            {
                "eauth": "pam",
                "expire": 1370434219.714091,
                "perms": [
                    "test.*"
                ],
                "start": 1370391019.71409,
                "token": "c02a6f4397b5496ba06b70ae5fd1f2ab75de9237",
                "user": "saltdev"
            }
        ]
    }
    >>> api.low([{'client': 'local', 'tgt': '*', 'fun': 'test.ping'}])
    {u'return': [{u'ms-0': True,
              u'ms-1': True,
              u'ms-2': True,
              u'ms-3': True,
              u'ms-4': True}]}

    '''

    def __init__(self, api_url, ignore_ssl_errors=False):
        '''
        Initialize the class with the URL of the API

        :param api_url: Host or IP address of the salt-api URL;
            include the port number

        :param ignore_ssl_errors: Add a flag to urllib2 to ignore invalid SSL certificates

        :raises PepperException: if the api_url is misformed

        '''
        split = urlparse.urlsplit(api_url)
        if split.scheme not in ['http', 'https']:
            raise PepperException("salt-api URL missing HTTP(s) protocol: {0}"
                                  .format(api_url))

        self.api_url = api_url
        self._ssl_verify = not ignore_ssl_errors
        self.auth = {}
        self.session = requests.Session()

    def _construct_url(self, path):
        '''
        Construct the url to salt-api for the given path

        Args:
            path: the path to the salt-api resource

        >>> api = Pepper('https://localhost:8000/salt-api/')
        >>> api._construct_url('/login')
        'https://localhost:8000/salt-api/login'
        '''

        relative_path = path.lstrip('/')
        return urlparse.urljoin(self.api_url, relative_path)

    def _find_auth(self, data):
        eauth = data['eauth'] if data is not None and 'eauth' in data else self.auth.get('eauth')
        if eauth == 'kerberos':
            from requests_kerberos import HTTPKerberosAuth, OPTIONAL
            return HTTPKerberosAuth(mutual_authentication=OPTIONAL)
        elif self.auth and self.auth.get('token'):
            return SaltTokenAuth(self.auth['token'])
        # Don't do this because of the use of sessionless salt-api
        # else:
        #     raise MissingLogin

    def _mkrequest(self, method, path, data=None, headers={}):
        '''
        A thin wrapper around request and request_kerberos to send
        requests and return the response

        If the current instance contains an authentication token it will be
        attached to the request as a custom header.

        :rtype: response

        '''
        auth = self._find_auth(data)
        head = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        }
        head.update(headers)

        resp = getattr(self.session, method)(
            url=self._construct_url(path),
            headers=head,
            verify=self._ssl_verify,
            auth=auth,
            data=json.dumps(data),
        )
        if resp.status_code == 401:
            raise AuthenticationDenied
        elif resp.status_code == 500:
            raise ServerError
        else:
            print(resp, resp.headers)
            return resp

    def run(self, cmds):
        '''
        Execute a command through salt-api and return the response

        :param list cmds: a list of command dictionaries
        '''
        body = self._mkrequest('post', '/', cmds).json()
        return body

    def login(self, username, password, eauth):
        body = self._mkrequest('post', '/login', {
            'username': username,
            'password': password,
            'eauth': eauth,
        })
        self.auth = body['return']
        return self.auth

    def logout(self):
        self._mkrequest('post', '/logout')
        self.auth = {}

    def unsessioned_run(self, cmds, **kwargs):
        '''
        Execute a command through salt-api and return the response

        Additional keyword arguments should be what's necessary for eauth. It's
        probably either:
        * username, password, eauth
        * token

        :param list cmds: a list of command dictionaries
        '''
        body = self._mkrequest('post', '/run', cmds).json()
        return body

    # TODO: minions, jobs, keys collections

    def hook(self, path, body):
        hookpath = urlparse.urljoin('/hook', path)
        self._mkrequest('post', hookpath, body)

    def stats(self):
        return self._mkrequest('get', '/stats').json()

    def events(self):
        """
        Generator tied to the Salt event bus. Produces data roughly in the form of:

            {
                'data': {
                    '_stamp': '2017-07-31T20:32:29.691100',
                    'fun': 'runner.manage.status',
                    'fun_args': [],
                    'jid': '20170731163229231910',
                    'user': 'astro73'
                },
                'tag': 'salt/run/20170731163229231910/new'
            }

        """
        # This is ripped from pepper, and doesn't support kerb to boot
        for msg in stream_sse(partial(self._mkrequest, 'get')):
            data = json.loads(msg['data'])
            yield data
