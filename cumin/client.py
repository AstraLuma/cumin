"""
A mid-level client to make executing commands easier.
"""
from functools import partial
from .api import SaltApi


def _dict_filter_none(**kwarg):
    return {k: v for k, v in kwarg.items() if v is not None}


class Client:
    def __init__(self, api_url, ignore_ssl_errors=False):
        self.api = SaltApi(api_url, ignore_ssl_errors)

    def login(self, username, password, eauth):
        return self.api.login(username, password, eauth)

    def logout(self):
        return self.api.logout()

    def events(self):
        yield from self.api.events()

    def local(self, tgt, fun, arg=None, kwarg=None, expr_form='glob',
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
            expr_form=expr_form,
            timeout=timeout,
            ret=ret,
        )])['return'][0]

    def local_async(self, tgt, fun, arg=None, kwarg=None, expr_form='glob',
                    timeout=None, ret=None):
        """
        Run a single execution function on one or more minions and a callable to
        get the job status.
        """
        body = self.api.run([_dict_filter_none(
            client='local_async',
            tgt=tgt,
            fun=fun,
            arg=arg,
            kwarg=kwarg,
            expr_form=expr_form,
            timeout=timeout,
            ret=ret,
        )])
        jid = body['return'][0]['jid']
        # TODO: Do anything with the minions?
        return partial(self.api.jobs, jid)

    def local_batch(self, tgt, fun, arg=None, kwarg=None, expr_form='glob',
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
            expr_form=expr_form,
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
