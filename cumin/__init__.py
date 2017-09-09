'''
Pepper is a CLI front-end to salt-api

'''
import json
import os

from .api import SaltApi, PepperException, AuthenticationDenied, ServerError
from .client import Client

__all__ = (
    '__version__', '__gitrev__', 'SaltApi', 'PepperException',
    'AuthenticationDenied', 'ServerError', 'Client',
)

try:
    # First try to grab the version from the version.json build file.
    vfile = os.path.join(os.path.dirname(__file__), 'version.json')

    with open(vfile, 'rb') as f:
        data = f.read().decode("utf-8")
        ret = json.loads(data)
        version = ret.get('version')
        sha = ret.get('sha')
except IOError:
    # Build version file doesn't exist; we may be running from a clone.
    setup_file = os.path.join(os.path.dirname(__file__), os.pardir, 'setup.py')

    if os.path.exists(setup_file):
        import imp

        setup = imp.load_source('pepper_setup', setup_file)
        version, sha = setup.get_version()
    else:
        version, sha = None, None

__version__ = version or 'Unknown'
__gitrev__ = sha
del version, sha
