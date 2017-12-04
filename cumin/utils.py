import os
from contextlib import contextmanager


@contextmanager
def umask(new_mask):
    cur_mask = os.umask(new_mask)
    try:
        yield
    finally:
        os.umask(cur_mask)
