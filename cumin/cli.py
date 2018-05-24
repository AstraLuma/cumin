'''
A CLI interface to a remote salt-api instance

'''
import json
import logging
import argparse
import time
import sys

from .client import Client
from .config import FileCache, Config, load_config_environ, load_config_pepperrc, load_config_tui
from . import __version__

logger = logging.getLogger('pepper')


def _guess_client():
    cmd = sys.argv[0]
    if cmd.endswith('-run'):
        return 'runner'
    else:
        return 'local'


class PepperCli(object):
    def __init__(self, seconds_to_wait=3):
        self.seconds_to_wait = seconds_to_wait
        self.parser = self.get_parser()
        self.add_globalopts()
        self.add_tgtopts()
        self.add_authopts()

    def get_parser(self):
        parser = argparse.ArgumentParser(
            description=__doc__)
        parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
        return parser

    def parse(self):
        '''
        Parse all args
        '''
        self.parser.add_argument(
            '-c', dest='config', default=None,
            help='Configuration file location. Default is a file path in the '
                 '"PEPPERRC" environment variable or ~/.pepperrc.',
        )

        self.parser.add_argument(
            '-v', dest='verbose', default=0, action='count',
            help='Increment output verbosity; may be specified multiple times',
        )

        self.options = self.parser.parse_args()

    def add_globalopts(self):
        '''
        Misc global options
        '''
        optgroup = self.parser.add_argument_group(
            "Pepper ``salt`` Options", "Mimic the ``salt`` CLI")

        optgroup.add_argument('cmd', nargs='*', help='Command to run')

        optgroup.add_argument(
            '-t', '--timeout', dest='timeout', type=int, default=60,
            help='Specify wait time (in seconds) before returning control to the shell',
        )

        optgroup.add_argument(
            '--client', dest='client', default=_guess_client(),
            choices=['local', 'local_async', 'local_batch', 'runner', 'wheel'],
            help='specify the salt-api client to use (local, local_async, runner, etc)')

        optgroup.add_argument(
            '--json', dest='json_input',
            help='Enter JSON at the CLI instead of positional (text) arguments. This '
            'is useful for arguments that need complex data structures. '
            'Specifying this argument will cause positional arguments to be '
            'ignored.',
        )

        optgroup.add_argument(
            '--events', dest='events', action='store_true',
            help='Show an event stream. No commands will be executed.',
        )
        # optgroup.add_argument('--out', '--output', dest='output',
        #        help="Specify the output format for the command output")

        # optgroup.add_argument('--return', default='', metavar='RETURNER',
        #    help="Redirect the output from a command to a persistent data store")

        optgroup.add_argument(
            '--fail-if-incomplete', action='store_true', dest='fail_if_minions_dont_respond',
            default=False,
            help='Return a failure exit code if not all minions respond. This option '
            'requires the authenticated user have access to run the '
            '`jobs.list_jobs` runner function.',
        )

        return optgroup

    def add_tgtopts(self):
        '''
        Targeting
        '''
        optgroup = self.parser.add_argument_group(
            "Targeting Options",
            "Target which minions to run commands on"
        )

        optgroup.set_defaults(tgt_type='glob')

        optgroup.add_argument(
            '-E', '--pcre', dest='tgt_type', action='store_const', const='pcre',
            help="Instead of using shell globs to evaluate the target servers, "
            "use pcre regular expressions."
        )

        optgroup.add_argument(
            '-L', '--list', dest='tgt_type', action='store_const', const='list',
            help="Instead of using shell globs to evaluate the target servers, "
            "take a comma or space delimited list of servers."
        )

        optgroup.add_argument(
            '-G', '--grain', dest='tgt_type', action='store_const', const='grain',
            help='Instead of using shell globs to evaluate the target use a '
            'grain value to identify targets, the syntax for the target is the '
            'grain key followed by a globexpression: "os:Arch*".'
        )

        optgroup.add_argument(
            '-P', '--grain-pcre', dest='tgt_type', action='store_const', const='grain_pcre',
            help='Instead of using shell globs to evaluate the target use a '
            'grain value to identify targets, the syntax for the target is the '
            'grain key followed by a pcre regular expression: "os:Arch.*".'
        )

        optgroup.add_argument(
            '-N', '--nodegroup', dest='tgt_type', action='store_const', const='nodegroup',
            help="Instead of using shell globs to evaluate the target use one of "
            "the predefined nodegroups to identify a list of targets."
        )

        optgroup.add_argument(
            '-R', '--range', dest='tgt_type', action='store_const', const='range',
            help="Instead of using shell globs to evaluate the target use a range "
            "expression to identify targets. Range expressions look like %%cluster."
        )

        optgroup.add_argument(
            '-C', '--compound', dest='tgt_type', action='store_const', const='compound',
            help="The compound target option allows for multiple target types to "
            "be evaluated, allowing for greater granularity in target matching. "
            "The compound target is space delimited, targets other than globs are "
            "preceded with an identifier matching the specific targets argument "
            "type: salt 'G@os:RedHat and webser* or E@database.*'."
        )

        optgroup.add_argument(
            '-I', '--pillar', dest='tgt_type', action='store_const', const='pillar',
            help='Instead of using shell globs to evaluate the target use a pillar '
            'value to identify targets, the syntax for the target is the pillar '
            'key followed by a glob expression: "role:production*".'
        )

        optgroup.add_argument(
            '-J', '--pillar-pcre', dest='tgt_type', action='store_const', const='pillar_pcre',
            help='Instead of using shell globs to evaluate the target use a pillar '
            'value to identify targets, the syntax for the target is the pillar '
            'key followed by a pcre regular expression: "role:prod.*".'

        )

        optgroup.add_argument(
            '-S', '--ipcidr', dest='tgt_type', action='store_const', const='ipcidr',
            help="Match based on Subnet (CIDR notation) or IP address."
        )

        optgroup.add_argument('--batch', dest='batch', default=None)

        return optgroup

    def add_authopts(self):
        '''
        Authentication options
        '''
        optgroup = self.parser.add_argument_group(
            "Authentication Options",
            'Authentication credentials can optionally be supplied via the environment '
            'variables: SALTAPI_URL, SALTAPI_USER, SALTAPI_PASS, SALTAPI_EAUTH.'
        )

        optgroup.add_argument(
            '-u', '--saltapi-url', dest='saltapiurl',
            help="Specify the host url.  Defaults to https://localhost:8080"
        )

        optgroup.add_argument(
            '-a', '--auth', '--eauth', '--extended-auth', dest='eauth',
            help='Specify the external_auth backend to authenticate against and interactively '
            'prompt for credentials'
        )

        optgroup.add_argument(
            '--username', dest='username',
            help="Optional, defaults to user name. will be prompt if empty unless "
            "--non-interactive"
        )

        optgroup.add_argument(
            '--password', dest='password',
            help="Optional, but will be prompted unless --non-interactive"
        )

        optgroup.add_argument(
            '--non-interactive', action='store_false', dest='interactive', default=True,
            help="Optional, fail rather than waiting for input"
        )

        optgroup.add_argument(
            '-T', '--make-token', default=False, dest='mktoken', action='store_true',
            help="Generate and save an authentication token for re-use. The token is "
            "generated and made available for the period defined in the Salt Master."
        )

        optgroup.add_argument(
            '-x', dest='cache', default=None,
            help='Cache file location. Default is a file path in the "PEPPERCACHE" '
            'environment variable or ~/.peppercache.'
        )

        return optgroup

    CONFIG_MAP = {
        # argparse : config
        'saltapiurl': 'url',
        'eauth': 'eauth',
        'username': 'user',
        'password': 'password',
        'cache': 'cache',
    }

    def load_config_cache(self):
        config = Config()
        load_config_pepperrc(config, self.options.config)
        load_config_environ(config)

        for arg, conf in self.CONFIG_MAP.items():
            if getattr(self.options, arg, None):
                config[conf] = getattr(self.options, arg, None)

        load_config_tui(config)

        if self.options.mktoken:
            cache = FileCache(config)
        else:
            cache = None

        return config, cache

    def parse_target(self):
        opts = {}

        if self.options.events:
            return opts

        # Soooo... it turns out salt-api parses out kwargs for us, sometimes
        if self.options.client in ('local', 'local_async', 'local_batch'):
            opts.update({
                'tgt': self.options.cmd[0],
                'fun': self.options.cmd[1],
                'arg': self.options.cmd[2:],
                'tgt_type': self.options.tgt_type,
            })
        else:
            opts.update({
                'fun': self.options.cmd[0],
                'arg': self.options.cmd[1:],
            })
        if self.options.client == 'local_batch':
            opts.update({
                'batch': self.options.batch,
            })
        if self.options.client in ('local', 'local_async'):
            opts.update({
                'timeout': self.options.timeout,
            })
        return opts

    def format_response(self, data):
        return json.dumps(data, indent=4)

    def run(self):
        '''
        Parse all arguments and call salt-api
        '''
        self.parse()

        # move logger instantiation to method?
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(max(logging.ERROR - (self.options.verbose * 10), 1))

        config, cache = self.load_config_cache()

        args = self.parse_target()

        self.client = Client(
            config=config,
            cache=cache,
            auto_login=True,
        )

        if self.options.json_input:
            data = json.loads(self.options.json_input)
            res = self.client.api.run(data)
            yield None, self.format_response(res)
        elif self.options.events:
            for ev in self.client.events():
                yield None, self.format_response(ev)
        elif self.options.client == 'local_async':
            minions, results = self.client.local_async(**args)
            start = time.time()
            end = start + self.options.timeout
            for mid, res in results:
                if mid is not None:
                    minions.remove(mid)
                    yield None, self.format_response({mid: res})
                    if not minions:
                        break
                if time.time() > end:
                    break
            if minions:
                ret = 1 if self.options.fail_if_minions_dont_respond else 0
                yield ret, "No response from {}".format(', '.join(minions))
        else:
            res = getattr(self.client, self.options.client)(**args)
            yield None, self.format_response(res)
