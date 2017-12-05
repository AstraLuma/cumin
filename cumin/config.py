"""
Handles configuration, credentials, caching, etc.
"""
import os
import abc
import json
import time
import getpass
import collections.abc
from configparser import ConfigParser, RawConfigParser
from .utils import umask

DEFAULT_SETTINGS = {
    'config': os.path.expanduser('~/.peppercache'),
    'url': 'https://localhost:8000/',
    'user': None,
    'password': None,
    'eauth': 'auto',
}


class AbstractCache(abc.ABC):
    def __init__(self, config):
        self.config = config

    @abc.abstractmethod
    def get_auth(self):
        """
        Loads the auth dictionary from cache, or None.

        The data is in the form of:
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

        This may potentially block on IO, depending on the backend used, but
        should never ask the user for information.
        """

    @abc.abstractmethod
    def set_auth(self, data):
        """
        Saves data from an auth dictionary to the cache, or None to clear it.
        Format should be the same as get_auth().
        """


class DefaultConfig(collections.abc.MutableMapping):
    """
    Configuration that just initializes itself from default values.
    """

    def __init__(self):
        self._data = DEFAULT_SETTINGS.copy()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, data):
        self._data[key] = data

    def __delitem__(self, key):
        if key in DEFAULT_SETTINGS:
            self._data[key] = DEFAULT_SETTINGS[key]
        else:
            del self._data[key]

    def __iter__(self):
        yield from self._data

    def __len__(self):
        return len(self._data)


class NullCache(AbstractCache):
    """
    Implements the cache interface, but does nothing.
    """

    def get_auth(self):
        return None

    def set_auth(self, data):
        pass


class FileCache(AbstractCache):
    """
    Handles caching the credentials in a file (default is ~/.peppercache)
    """

    def __init__(self, config):
        super().__init__(config)
        self.token_file = config['cache']

    def get_auth(self):
        with open(self.token_file, 'rt') as f:
            auth = json.load(f)
        if auth['expire'] < time.time() + 30:  # XXX: Why +30?
            auth = None
        return auth

    def set_auth(self, auth):
        with umask(0):
            fdsc = os.open(self.token_file, os.O_WRONLY | os.O_CREAT, 0o600)
            with os.fdopen(fdsc, 'wt') as f:
                json.dump(auth, f)


class PepperrcConfig(DefaultConfig):
    """
    Loads configurations from a pepperrc file (default is ~/.pepperrc),
    overridable by environment variables.
    """

    CONFIG_MAP = {
        'SALTAPI_USER': 'user',
        'SALTAPI_PASS': 'password',
        'SALTAPI_EAUTH': 'eauth',
        'SALTAPI_URL': 'url',
    }

    def __init__(self, filename=...):
        super().__init__(self)
        if filename is ...:
            filename = os.path.expanduser('~/.pepperrc')


class CliPepperrcConfig(PepperrcConfig):
    """
    Same as PepperrcConfig, but may also prompt the user for information.
    """

    PROMPTERS = {
        'user': lambda self: input('Username: '),
        'password': (
            lambda self:
            None if self['eauth'] == 'kerberos' else getpass.getpass(prompt='Password: ')
        ),
    }

    def __init__(self, filename=...):
        """
        Loads config information from file, and then prompts the user to fill in
        missing bits
        """
        super().__init__(filename)
        for field, prompter in self.PROMPTERS:
            if not self[field]:
                self[field] = prompter()


def get_login_details(self):
    '''
    This parses the config file, environment variables and command line options
    and returns the config values
    Order of parsing:
        command line options, ~/.pepperrc, environment, defaults
    '''

    # setting default values
    results = {
        'SALTAPI_USER': None,
        'SALTAPI_PASS': None,
        'SALTAPI_EAUTH': 'auto',
    }

    try:
        config = ConfigParser(interpolation=None)
    except TypeError:
        config = RawConfigParser()
    config.read(self.options.config)

    # read file
    profile = 'main'
    if config.has_section(profile):
        for key, value in list(results.items()):
            if config.has_option(profile, key):
                results[key] = config.get(profile, key)

    # get environment values
    for key, value in list(results.items()):
        results[key] = os.environ.get(key, results[key])

    if results['SALTAPI_EAUTH'] == 'kerberos':
        results['SALTAPI_PASS'] = None

    if self.options.eauth:
        results['SALTAPI_EAUTH'] = self.options.eauth
    if self.options.username is None and results['SALTAPI_USER'] is None:
        if self.options.interactive:
            results['SALTAPI_USER'] = input('Username: ')
        else:
            logger.error("SALTAPI_USER required")
            sys.exit(1)
    else:
        if self.options.username is not None:
            results['SALTAPI_USER'] = self.options.username
    if self.options.password is None and results['SALTAPI_PASS'] is None:
        if self.options.interactive:
            results['SALTAPI_PASS'] = getpass.getpass(prompt='Password: ')
        else:
            logger.error("SALTAPI_PASS required")
            sys.exit(1)
    else:
        if self.options.password is not None:
            results['SALTAPI_PASS'] = self.options.password

    return results

def parse_url(self):
    '''
    Determine api url
    '''
    url = 'https://localhost:8000/'

    try:
        config = ConfigParser(interpolation=None)
    except TypeError:
        config = RawConfigParser()
    config.read(self.options.config)

    # read file
    profile = 'main'
    if config.has_section(profile):
        if config.has_option(profile, "SALTAPI_URL"):
            url = config.get(profile, "SALTAPI_URL")

    # get environment values
    url = os.environ.get("SALTAPI_URL", url)

    # get eauth prompt options
    if self.options.saltapiurl:
        url = self.options.saltapiurl

    return url

def parse_login(self):
    '''
    Extract the authentication credentials
    '''
    login_details = self.get_login_details()

    # Auth values placeholder; grab interactively at CLI or from config
    user = login_details['SALTAPI_USER']
    passwd = login_details['SALTAPI_PASS']
    eauth = login_details['SALTAPI_EAUTH']

    return user, passwd, eauth
