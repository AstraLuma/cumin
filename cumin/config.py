"""
Handles configuration, credentials, caching, etc.
"""
import os
import abc
import json
import time
import getpass
import collections.abc
from configparser import ConfigParser
from .utils import umask

DEFAULT_SETTINGS = {
    'cache': os.path.expanduser('~/.peppercache'),
    'url': 'https://localhost:8000/',
    'user': None,
    'password': None,
    'eauth': 'auto',
    'verify': True
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
        if self.token_file and os.path.exists(self.token_file):
            with open(self.token_file, 'rt') as f:
                try:
                    auth = json.load(f)
                except json.decoder.JSONDecodeError:
                    # Assuming the file is corrupt. Eating the exception
                    return
            if auth['expire'] < time.time() + 30:  # XXX: Why +30?
                return
            return auth

    def set_auth(self, auth):
        # A bunch of extra work to set file permissions without having a window of leak
        with umask(0):
            fdsc = os.open(self.token_file, os.O_WRONLY | os.O_CREAT, 0o600)
            with os.fdopen(fdsc, 'wt') as f:
                json.dump(auth, f)


class Config(collections.abc.MutableMapping):
    """
    Configuration that just initializes itself from default values.
    """

    def __init__(self):
        self._init_from_defaults()

    def _init_from_defaults(self):
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


def load_config_pepperrc(config, filename=None):
    """
    Loads configurations from a pepperrc file (default is ~/.pepperrc),
    overridable by environment variables.
    """

    CONFIG_MAP = {
        'saltapi_user': 'user',
        'saltapi_pass': 'password',
        'saltapi_eauth': 'eauth',
        'saltapi_url': 'url',
        'saltapi_ssl_verify': 'verify',
    }

    if not filename:
        filename = os.path.expanduser('~/.pepperrc')

    cp = ConfigParser(interpolation=None)
    cp.read(filename)
    if 'main' in cp:
        for k, v in cp['main'].items():
            if k in CONFIG_MAP:
                config[CONFIG_MAP[k]] = v


def load_config_environ(config, environ=None):
    """
    Loads configurations from process environmnet (default os.environ)
    """

    CONFIG_MAP = {
        'SALTAPI_USER': 'user',
        'SALTAPI_PASS': 'password',
        'SALTAPI_EAUTH': 'eauth',
        'SALTAPI_URL': 'url',
        'SALTAPI_SSL_VERIFY': 'verify',
        'PEPPERCACHE': 'cache',
    }

    if environ is None:  # Don't overwrite {}
        environ = os.environ

    for k, v in environ.items():
        if k in CONFIG_MAP:
            config[CONFIG_MAP[k]] = v


def load_config_tui(config):
    """
    Prompts the user for information.
    """

    PROMPTERS = {
        'user': lambda: input('Username: '),
        'password': (
            lambda:
            None if config['eauth'] == 'kerberos' else getpass.getpass(prompt='Password: ')
        ),
    }

    for field, prompter in PROMPTERS.items():
        if not config[field]:
            config[field] = prompter()


def standard_configuration(*, pepperrc=None, environ=None):
    """
    Builds a standard configuration, suitable for most API clients.

    Standard uses this order:
    1. Process environment
    2. .pepperrc file
    3. Hard-coded defaults
    """
    config = Config()
    load_config_pepperrc(config, pepperrc)
    load_config_environ(config, environ)
    return config
