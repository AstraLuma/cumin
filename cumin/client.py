"""
A mid-level client to make executing commands easier.
"""
from collections import ChainMap
from .api import SaltApi
from .config import standard_configuration, NullCache


def _dict_filter_none(**kwarg):
    return {k: v for k, v in kwarg.items() if v is not None}


class Client:
    def __init__(self, api_url=None, *, config=None, cache=None, auto_login=True):
        """
        * api_url: URL to use, defaulting to one loaded from configuration
        * config: A configuration, defaulting to standard_configuration
        * cache: Authentication Cache to use, defaulting to NullCache
        * auto_login: Attempt to login automatically, if credentials are available
          and nothing is cached (Default: True)
        """
        self.config = config or standard_configuration()
        self.cache = cache or NullCache(self.config)
        self.api = SaltApi(api_url or self.config['url'], cache=self.cache, ssl_verify=self.config['verify'])

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
        Run a single execution function on one or more minions and a generator
        producing (mid, result) pairs as they are available. (Or (None, None) if
        no new minions have responded.)

        NOTE: Every loop through the generator is an API call.
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

        def asynciter():
            waiting_for = set(minions)
            while waiting_for:
                # Note: runner:jobs.lookup_jid gives this to us directly, but
                # requires runner permissions
                status = self.api.jobs(jid)['info'][0]
                results = status['Result']
                finished = set(waiting_for).intersection(set(results.keys()))
                if finished:
                    for m in finished:
                        yield m, results[m]
                    waiting_for -= finished
                else:
                    yield None, None

        return minions, asynciter()

    def local_batch(self, tgt, fun, arg=None, kwarg=None, tgt_type='glob',
                    batch='50%', ret=None):
        """
        Run a single execution function on one or more minions in staged batches,
        waiting for the results.
        """
        # We don't have the option to get results as they finish, so just merge
        # everything
        batches = self.api.run([_dict_filter_none(
            client='local_batch',
            tgt=tgt,
            fun=fun,
            arg=arg,
            kwarg=kwarg,
            tgt_type=tgt_type,
            batch=batch,
            ret=ret,
        )])['return']
        return ChainMap(*batches)

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
