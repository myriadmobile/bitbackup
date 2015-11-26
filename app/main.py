#!/usr/bin/env python
import argparse
import signal
import subprocess
import sys
import threading
from datetime import datetime

import boto3
import colorama
import requests
import tarfile
import tempfile
import workerpool
from boto3.s3.transfer import S3Transfer
from colorama import Fore, Style

is_debug = False


def debug(message):
    if is_debug:
        print(Fore.MAGENTA + threading.current_thread().name + ': ' + Style.DIM + Fore.CYAN + message + Style.RESET_ALL)


def info(message):
    print(Fore.MAGENTA + threading.current_thread().name + ': ' + Fore.CYAN + message + Style.RESET_ALL)


def success(message):
    print(Fore.MAGENTA + threading.current_thread().name + ': ' + Fore.GREEN + message + Style.RESET_ALL)


def error(message):
    print(Fore.MAGENTA + threading.current_thread().name + ': ' + Style.BRIGHT + Fore.RED + message + Style.RESET_ALL)


def divider():
    print(Style.BRIGHT + Fore.MAGENTA + ('=' * 109) + Fore.RESET + Style.RESET_ALL)


class Bitbackup:
    def __init__(self, bb_username='', bb_password='', s3_key='', s3_secret='', s3_bucket='', s3_base_path='',
                 s3_endpoint='https://s3.amazonaws.com', worker_count=8):
        self._bb_username = bb_username
        self._bb_password = bb_password
        self._s3_key = s3_key
        self._s3_secret = s3_secret
        self._s3_bucket = s3_bucket
        self._s3_base_path = s3_base_path
        self._s3_endpoint = s3_endpoint
        self._worker_count = worker_count

    def run(self):
        self._print_header()

        signaler = Signaler()
        bitbucket = Bitbucket(self._bb_username, self._bb_password)
        git = Git()

        def toolbox_factory():
            s3 = S3(self._s3_key, self._s3_secret, self._s3_bucket, self._s3_base_path, self._s3_endpoint)
            return BitbackupWorkerToolbox(bitbucket, git, s3)

        def worker_factory(job_queue):
            worker = workerpool.EquippedWorker(job_queue, toolbox_factory)
            worker.setName(worker.getName().replace("Thread", "Worker"))
            return worker

        info('Loading repository list...')
        repos = bitbucket.get_all_repositories()

        info('Starting {} workers...'.format(self._worker_count))
        pool = workerpool.WorkerPool(size=self._worker_count, worker_factory=worker_factory, maxjobs=1)

        for repo in repos:
            if signaler.should_term():
                break
            pool.put(BitbackupJob(repo))

        pool.shutdown()
        pool.wait()
        self._print_footer()

    def _print_header(self):
        print('')
        divider()
        divider()
        print('')
        print(Style.BRIGHT + Fore.GREEN + '  Starting Bitbackup!' + Style.RESET_ALL)
        print('')
        print(Style.BRIGHT + '    User/Team:   ' + Style.RESET_ALL + self._bb_username)
        print(
            Style.BRIGHT + '    Destination: ' + Style.RESET_ALL + 's3://' + self._s3_bucket + '/' + self._s3_base_path)
        print('')
        divider()
        divider()
        print('')

    def _print_footer(self):
        print('')
        divider()
        divider()
        print('')
        print(Style.BRIGHT + Fore.GREEN + 'Bitbackup finished!' + Style.RESET_ALL)
        print('')
        divider()
        divider()
        print('')


class BitbackupWorkerToolbox:
    def __init__(self, bitbucket, git, s3):
        self.bitbucket = bitbucket
        self.git = git
        self.s3 = s3


class BitbackupJob(workerpool.Job):
    def __init__(self, repo):
        super().__init__()
        self._repo = repo

    def run(self, toolbox=None):
        repo_name = self._repo.get('full_name')
        try:
            clone_url = toolbox.bitbucket.get_clone_url(self._repo)
            archive = toolbox.git.archive(clone_url)
            key = repo_name + '.tar.gz'
            toolbox.s3.upload(key, archive.name)
            success('Backed up ' + repo_name + '!')
        except Exception:
            error('Failed to backup {}'.format(repo_name))


class Bitbucket:
    def __init__(self, username, password, endpoint='https://api.bitbucket.org/2.0/'):
        self._username = username
        self._password = password
        self._endpoint = endpoint

    def _create_url(self, path):
        return self._endpoint + path

    def _request(self, url='', **kwargs):
        kwargs['auth'] = (self._username, self._password)
        response = requests.request('get', url, **kwargs)
        return response.json()

    def get_all_repositories(self):
        repositories = []

        next = self._create_url('repositories/' + self._username + '?pagelen=100&page=1')
        while next is not None:
            debug('Fetching repo list' + next)
            response = self._request(next)
            repositories += response.get('values')
            next = response.get('next')

        return repositories

    def get_clone_url(self, repository):
        clone = repository.get('links').get('clone')
        for link in clone:
            if link.get('name') == 'https':
                href = str(link.get('href'))
                return href.replace('@', ':' + self._password + '@')
        return None


class Git:
    def archive(self, url):
        basename = url[str(url).rindex('/') + 1:]
        tempdir = tempfile.TemporaryDirectory(suffix='.git')
        debug('Cloning ' + basename + ' in to ' + tempdir.name + '...')
        subprocess.check_output("git clone --bare --quiet {} {}".format(url, tempdir.name), shell=True)
        archive = self._make_tarfile(tempdir.name, basename)
        return archive

    def _make_tarfile(self, source_dir, basename):
        output = tempfile.NamedTemporaryFile(suffix='.tar.gz')
        debug('Tar and GZ ' + source_dir + ' to ' + output.name + ' as ' + basename + '...')
        with tarfile.open(output.name, "w:gz") as tar:
            tar.add(source_dir, arcname=basename)
        return output


class S3:
    def __init__(self, access_key, secret_key, bucket, s3_base_path, s3_endpoint='https://s3.amazonaws.com'):
        self._bucket = bucket
        self._base_path = s3_base_path
        client = boto3.client(aws_access_key_id=access_key, aws_secret_access_key=secret_key, service_name='s3',
                              endpoint_url=s3_endpoint)
        self._transfer = S3Transfer(client)

    def upload(self, key, file):
        key = self._base_path + '/' + key
        debug('Uploading ' + file + ' to s3://' + self._bucket + ':' + key + '...')
        self._transfer.upload_file(file, self._bucket, key)
        return


class Signaler:
    sigterm = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.term)
        signal.signal(signal.SIGTERM, self.term)
        signal.signal(signal.SIGQUIT, self.term)

    def term(self, signum, frame):
        self.sigterm = True

    def should_term(self):
        return self.sigterm


if __name__ == '__main__':
    colorama.init()

    parser = argparse.ArgumentParser(description='Backup Bitbucket repositories to a S3 compatible store.')
    parser.add_argument('--bb-username', required=True, dest='bb_username', help='Bitbucket username or team name')
    parser.add_argument('--bb-password', required=True, dest='bb_password', help='Bitbucket password or team API key')
    parser.add_argument('--s3-key', required=True, dest='s3_key', help='S3 Access Key')
    parser.add_argument('--s3-secret', required=True, dest='s3_secret', help='S3 Secret Key')
    parser.add_argument('--s3-bucket', required=True, dest='s3_bucket', help='S3 Bucket')
    parser.add_argument('--s3-base-path', dest='s3_base_path', default=datetime.now().strftime("%Y-%m-%d-%H:%M"),
                        help='S3 base path')
    parser.add_argument('--s3-endpoint', dest='s3_endpoint', default='https://s3.amazonaws.com', help='S3 host')
    parser.add_argument('--workers', dest='worker_count', type=int, default=8, help='The number of worker threads')
    parser.add_argument('--debug', dest='is_debug', action='store_true', help='Print debug messages')

    args = vars(parser.parse_args())
    is_debug = args.pop('is_debug')

    bitbackup = Bitbackup(**args)
    bitbackup.run()

    try:
        bitbackup = Bitbackup(**args)
        bitbackup.run()
    except Exception as e:
        error('Backup failed: {}'.format(e))
        sys.exit(1)
