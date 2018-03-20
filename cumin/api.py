"""
A low-level API exposing the salt-api HTTP calls fairly directly.
"""
import json
import logging
from six.moves.urllib import parse as urlparse
import posixpath as urlpath
import requests
import tarfile
import io
from .config import NullCache
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


class AuthenticationDenied(PepperException):
    """
    401:Authentication denied
    """


class ServerError(PepperException):
    """
    500:Server error
    """


class SaltApi(object):
    '''
    A thin wrapper for making HTTP calls to the salt-api rest_cherrpy REST
    interface

    >>> api = SaltApi('https://localhost:8000')
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
    >>> api.run([{'client': 'local', 'tgt': '*', 'fun': 'test.ping'}])
    {u'return': [{u'ms-0': True,
              u'ms-1': True,
              u'ms-2': True,
              u'ms-3': True,
              u'ms-4': True}]}

    '''

    def __init__(self, api_url, *, cache=None, ssl_verify=False):
        '''
        Initialize the class with the URL of the API

        :param api_url: Host or IP address of the salt-api URL;
            include the port number

        :param ssl_verify: A bool or string pointing to something that looks like a CA or trust store

        :raises ValueError: if the api_url is misformed

        '''
        split = urlparse.urlsplit(api_url)
        if split.scheme not in ['http', 'https']:
            raise ValueError("salt-api URL missing HTTP(s) protocol: {0}".format(api_url))

        if cache is None:
            self.authcache = NullCache(None)
        else:
            self.authcache = cache

        self.api_url = api_url
        self._ssl_verify = ssl_verify
        self.auth = self.authcache.get_auth() or {}
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

    def _mkrequest(self, method, path, data=None, headers={}, **kwargs):
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
            **kwargs
        )
        if resp.status_code == 401:
            raise AuthenticationDenied(resp.text)
        elif resp.status_code == 500:
            raise ServerError(resp.text)
        else:
            resp.raise_for_status()
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
        }).json()
        self.auth = body['return'][0]
        self.authcache.set_auth(self.auth)
        return self.auth

    def logout(self):
        self._mkrequest('post', '/logout').json()
        self.auth = {}

    def run_unsessioned(self, cmds):
        '''
        Execute a command through salt-api and return the response, bypassing
        the usual session mechanisms.

        Additional keyword arguments should be what's necessary for eauth. It's
        probably either:
        * username, password, eauth
        * token

        :param list cmds: a list of command dictionaries
        '''
        return self._mkrequest('post', '/run', cmds).json()

    def minions(self, mid):
        if mid is ...:
            path = '/minions'
        else:
            path = urlpath.join('/minions', mid)
        return self._mkrequest('get', path).json()

    def run_async(self, cmds):
        '''
        Start an execution command and immediately return the job id.

        lowstate data describing Salt commands must be sent in the request body.
        The client option will be set to local_async.

        :param list cmds: a list of command dictionaries
        '''
        return self._mkrequest('post', '/minions', cmds).json()

    def jobs(self, jid):
        if jid is ...:
            path = '/jobs'
        else:
            path = urlpath.join('/jobs', jid)
        return self._mkrequest('get', path).json()

    def keys(self, mid):
        if mid is ...:
            path = '/keys'
        else:
            path = urlpath.join('/keys', mid)
        return self._mkrequest('get', path).json()

    def key_gen(self, mid, **kwargs):
        """
        * mid: The name of the minion for which to generate a key pair.
        * keysize: The size of the key pair to generate. The size must be 2048,
          which is the default, or greater. If set to a value less than 2048,
          the key size will be rounded up to 2048.
        * force: If a public key has already been accepted for the given minion
          on the master, then the gen_accept function will return an empty
          dictionary and not create a new key. This is the default behavior. If
          force is set to True, then the minion's previously accepted key will
          be overwritten.
        * username
        * password
        * eauth
        """
        form = {
            'mid': mid,
        }
        form.update(kwargs)
        resp = self._mkrequest('post', '/keys', form)
        buf = io.BytesIO(resp.binary)
        return tarfile.open(fileobj=buf, mode='r')

    def hook(self, path, body):
        hookpath = urlpath.join('/hook', path)
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
        for msg in stream_sse(self._mkrequest, 'get', '/events'):
            data = json.loads(msg['data'])
            yield data
