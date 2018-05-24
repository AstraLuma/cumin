#!/usr/bin/env python
'''
A CLI front-end to a running salt-api system

'''
import json
import os
import re

from setuptools import setup
from setuptools.command import sdist

setup_kwargs = {
    'name': 'salt-cumin',
    'description': __doc__.strip(),
    'author': 'Seth House',
    'author_email': 'shouse@saltstack.com',
    'maintainer': 'Jamie Bliss',
    'maintainer_email': 'jamie.bliss@astro73.com',
    'url': 'https://github.com/astronouth7303/cumin',
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Topic :: System :: Clustering',
        'Topic :: System :: Distributed Computing',
    ],
    'packages': [
        'cumin',
    ],
    'package_data': {
        'cumin': ['version.json'],
    },
    'entry_points': {
        'console_scripts': [
            'cumin = cumin.__main__:main',
            'cumin-run = cumin.__main__:main'
        ]
    },
    'install_requires': [
        'requests',
    ],
    'extras_require': {
        'kerberos': ['requests_kerberos'],
    },
}


def versionfile(base_dir):
    return os.path.join(base_dir, 'cumin', 'version.json')


def readmefile(base_dir):
    return os.path.join(base_dir, 'README.rst')


def read_version_tag():
    git_dir = os.path.join(os.path.dirname(__file__), '.git')

    if os.path.isdir(git_dir):
        import subprocess

        try:
            p = subprocess.Popen(['git', 'describe'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = p.communicate()
        except Exception:
            pass
        else:
            return out.strip() or None

    else:
        return read_version_from_json_file()

    return None


def read_version_from_json_file():
    with open(versionfile(os.path.dirname(__file__))) as f:
        return json.load(f)['version']


def read_readme():
    with open(readmefile(os.path.dirname(__file__))) as f:
        return f.read()


def parse_version_tag(tag):
    '''
    Parse the output from Git describe

    Returns a tuple of the version number, number of commits (if any), and the
    Git SHA (if available).
    '''
    if isinstance(tag, bytes):
        tag = tag.decode()
    if not tag or '-g' not in tag:
        return tag, None, None

    match = re.search('(?P<version>.*)-(?P<num_commits>[0-9]+)-g(?P<sha>[0-9a-fA-F]+)', tag)

    if not match:
        return tag, None, None

    match_dict = match.groupdict()
    return (
        match_dict.get('version'),
        match_dict.get('num_commits'),
        match_dict.get('sha'))


def get_version():
    '''
    Return a tuple of the version and Git SHA
    '''
    version, num_commits, sha = parse_version_tag(read_version_tag())
    if sha:
        version = '{0}.dev{1}'.format(version, num_commits)
    return version, sha


def write_version_file(base_dir):
    ver_path = versionfile(base_dir)
    version, sha = get_version()

    with open(ver_path, 'wt') as f:
        json.dump({'version': version, 'sha': sha}, f)


class PepperSdist(sdist.sdist):
    '''
    Write the version.json file to the sdist tarball build directory
    '''

    def make_release_tree(self, base_dir, files):
        sdist.sdist.make_release_tree(self, base_dir, files)
        write_version_file(base_dir)


if __name__ == '__main__':
    version, sha = get_version()
    readme = read_readme()

    setup(cmdclass={
        'sdist': PepperSdist,
    }, version=version, long_description=readme, **setup_kwargs)  # git_sha=sha
