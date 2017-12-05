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


class DefaultConfig(collections.abc.MutableMapping):
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
        self._init_from_defaults()
        self._init_from_pepperrc(filename)

    def _init_from_pepperrc(self, filename=...):
        if filename is ...:
            filename = os.path.expanduser('~/.pepperrc')

        config = ConfigParser(interpolation=None)
        config.read(filename)
        if 'main' in config:
            for k, v in config['main']:
                if k in self.CONFIG_MAP:
                    self[self.CONFIG_MAP[k]] = v


class EnvironConfig(DefaultConfig):
    """
    Loads configurations from process environmnet (default os.environ)
    """

    CONFIG_MAP = {
        'SALTAPI_USER': 'user',
        'SALTAPI_PASS': 'password',
        'SALTAPI_EAUTH': 'eauth',
        'SALTAPI_URL': 'url',
    }

    def __init__(self, env=...):
        self._init_from_defaults()
        self._init_from_environ(env)

    def _init_from_environ(self, env=...):
        if env is ...:
            env = os.environ

        for k, v in env:
            if k in self.CONFIG_MAP:
                self[self.CONFIG_MAP[k]] = v


class TuiConfig(DefaultConfig):
    """
    Prompts the user for information.
    """

    PROMPTERS = {
        'user': lambda self: input('Username: '),
        'password': (
            lambda self:
            None if self['eauth'] == 'kerberos' else getpass.getpass(prompt='Password: ')
        ),
    }

    def __init__(self):
        """
        Loads config information from file, and then prompts the user to fill in
        missing bits
        """
        self._init_from_defaults()
        self._init_from_tui()

    def _init_from_tui(self):
        for field, prompter in self.PROMPTERS:
            if not self[field]:
                self[field] = prompter()


class TuiPepperrcConfig(TuiConfig, PepperrcConfig, DefaultConfig):
    """
    Composes TUI and Pepperrc configurations.
    """

    def __init__(self, filename=...):
        self._init_from_defaults()
        self._init_from_pepperrc(filename)
        self._init_from_tui()
