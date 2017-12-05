"""
A mid-level client to make executing commands easier.
"""
from functools import partial
from .api import SaltApi
from .config import standard_configuration, NullCache


def _dict_filter_none(**kwarg):
    return {k: v for k, v in kwarg.items() if v is not None}


class Client:
    def __init__(self, api_url=None, *, config=None, cache=None, ignore_ssl_errors=False, auto_login=True):
        """
        * api_url: URL to use, defaulting to one loaded from configuration
        * config: A configuration, defaulting to standard_configuration
        * cache: Authentication Cache to use, defaulting to NullCache
        * ignore_ssl_errors: Don't validate certificates
        * auto_login: Attempt to login automatically, if credentials are available
          and nothing is cached (Default: True)
        """
        self.config = config or standard_configuration()
        self.cache = cache or NullCache(self.config)
        self.api = SaltApi(api_url or self.config['url'], cache=self.cache, ignore_ssl_errors=ignore_ssl_errors)

        if auto_login and self.config['user'] and not self.api.auth:
            self.login(self.config['user'], self.config['password'], self.config['eauth'])

    def login(self, username, password, eauth):
        return self.api.login(username, password, eauth)

    def logout(self):
        return self.api.logout()

    def events(self):
        yield from self.api.events()

    def local(self, tgt, fun, arg=None, kwarg=None, tgt_type='glob',
              timeout=None, ret=None):
        """
        Run a single execution function on one or more minions and wait for the
        results.
        """
        return self.api.run([_dict_filter_none(
            client='local',
            tgt=tgt,
            fun=fun,
            arg=arg,
            kwarg=kwarg,
            tgt_type=tgt_type,
            timeout=timeout,
            ret=ret,
        )])['return'][0]

    def local_async(self, tgt, fun, arg=None, kwarg=None, tgt_type='glob',
                    timeout=None, ret=None):
        """
        Run a single execution function on one or more minions and get a
        callable to get the job status.
        """
        body = self.api.run([_dict_filter_none(
            client='local_async',
            tgt=tgt,
            fun=fun,
            arg=arg,
            kwarg=kwarg,
            tgt_type=tgt_type,
            timeout=timeout,
            ret=ret,
        )])
        jid = body['return'][0]['jid']
        minions = body['return'][0]['minions']
        return minions, (lambda: self.api.jobs(jid)['info'][0])

    def local_batch(self, tgt, fun, arg=None, kwarg=None, tgt_type='glob',
                    batch='50%', ret=None):
        """
        Run a single execution function on one or more minions in staged batches,
        waiting for the results.
        """
        for result in self.api.run([_dict_filter_none(
            client='local_batch',
            tgt=tgt,
            fun=fun,
            arg=arg,
            kwarg=kwarg,
            tgt_type=tgt_type,
            batch=batch,
            ret=ret,
        )])['return']:
            yield result

    def runner(self, fun, arg=None, kwarg=None):
        """
        Run a single runner function on the master.
        """
        return self.api.run([_dict_filter_none(
            client='runner',
            fun=fun,
            arg=arg,
            kwarg=kwarg,
        )])['return'][0]

    def wheel(self, fun, arg=None, kwarg=None):
        """
        Run a single wheel function on the master.
        """
        return self.api.run([_dict_filter_none(
            client='wheel',
            fun=fun,
            arg=arg,
            kwarg=kwarg,
        )])['return'][0]
