#!/usr/bin/env python
'''
A CLI interface to a remote salt-api instance
'''
from __future__ import print_function

import sys
import logging

from cumin.cli import PepperCli
from cumin import PepperException

from logging import NullHandler


def main():
    logging.basicConfig(format='%(levelname)s %(asctime)s %(module)s: %(message)s')
    logger = logging.getLogger('pepper')
    logger.addHandler(NullHandler())

    try:
        cli = PepperCli()
        for exit_code, result in cli.run():
            print(result)
            if exit_code is not None:
                sys.exit(exit_code)
    # except PepperException as exc:
    #     sys.exit('Pepper error: {0}'.format(exc))
    # except Exception as e:
    #     logger.debug('Uncaught traceback:', exc_info=True)
    #     raise
    except (KeyboardInterrupt, SystemExit):
        sys.exit()


if __name__ == '__main__':
    main()
