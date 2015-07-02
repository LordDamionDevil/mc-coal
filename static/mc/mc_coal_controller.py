#!/usr/bin/env python

import base64
import datetime
import errno
import fnmatch
import json
import logging
import os
import random
import shutil
import signal
import stat
import string
import subprocess
import sys
import time
import urllib
import zipfile

from apiclient.discovery import build
from apiclient.errors import HttpError
from apiclient.http import MediaFileUpload, MediaIoBaseDownload
from oauth2client import gce
import httplib2

import requests

TQ_API_SCOPE = 'https://www.googleapis.com/auth/taskqueue'
TQ_API_VERSION = 'v1beta2'
STORAGE_API_SCOPE = 'https://www.googleapis.com/auth/devstorage.full_control'
STORAGE_API_VERSION = 'v1'
COAL_DIR = '/coal/'
SERVERS_DIR = os.path.join(COAL_DIR, 'servers')
ARCHIVES_DIR = os.path.join(COAL_DIR, 'archives')
MINECRAFT_DIR = os.path.join(COAL_DIR, 'minecraft')
NUM_RETRIES = 10
CHUNKSIZE = 2 * 1024 * 1024
COMMAND_FIFO_FILENAME = 'command-fifo'
MINECRAFT_SERVER_JAR_FILENAME = 'minecraft_server.jar'
LOG4J_CONFIG_FILENAME = 'log4j2.xml'
EULA_FILENAME = 'eula.txt'
SERVER_KEY_FILENAME = 'server_key'
AGENT_PID_FILENAME = 'agent.pid'
SERVER_PID_FILENAME = 'server.pid'
RUN_SERVER_FILENAME = 'run_server.sh'
AGENT_FILENAME = 'mc_coal_agent.py'
MC_COAL_DIRNAME = 'mc_coal'
START_EVENT = 'START_SERVER'
STOP_EVENT = 'STOP_SERVER'

# Globals
client = None
logger = None
project = None
app_bucket = None
external_ip = None


class ControllerClient(object):
    def __init__(self, host, client_id, secret, access_token=None, refresh_token=None, *args, **kwargs):
        self.host = host
        self.scheme = 'https'
        if self.host == 'localhost:8080':
            self.scheme = 'http'
        self.client_id = client_id
        self.secret = secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        super(ControllerClient, self).__init__(*args, **kwargs)

    @property
    def headers(self):
        if self.access_token:
            return {
                'Authorization': 'Bearer {0}'.format(self.access_token)
            }
        return None

    def request_tokens(self):
        url = "{0}://{1}/oauth/v1/token".format(self.scheme, self.host)
        data = {
            'client_id': self.client_id,
            'client_secret': self.secret,
            'scope': 'controller'
        }
        if self.refresh_token is None:
            data['grant_type'] = 'authorization_code'
            data['code'] = self.secret
            data['redirect_uri'] = '/'
        else:
            data['grant_type'] = 'refresh_token'
            data['refresh_token'] = self.refresh_token
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            token_response = response.json()
            self.access_token = token_response['access_token']
            self.refresh_token = token_response['refresh_token']
        except requests.exceptions.RequestException:
            self.access_token = None
            self.refresh_token = None
            raise

    def get(self, url, params=None):
        url = "{0}://{1}{2}".format(self.scheme, self.host, url)
        response = requests.get(url, data=params, headers=self.headers)
        if response.status_code == 401:
            self.request_tokens()
            response = requests.get(url, data=params, headers=self.headers)
        response.raise_for_status()
        return response

    def post(self, url, params):
        url = "{0}://{1}{2}".format(self.scheme, self.host, url)
        response = requests.post(url, data=params, headers=self.headers)
        if response.status_code == 401:
            self.request_tokens()
            response = requests.post(url, data=params, headers=self.headers)
        response.raise_for_status()
        return response

    def post_event(self, server_key, event, completed):
        try:
            params = {
                'server_key': server_key,
                'event': event,
                'completed': completed
            }
            self.post("/api/v1/controllers/event", params=params)
        except Exception as e:
            logger.error("Error ({0}) calling event API: {1}".format(str(e), e.response.text))


def init_external_ip():
    global external_ip
    try:
        results = json.loads(
            subprocess.Popen(
                ['gcloud', 'compute', 'instances', 'list', '--quiet', '--format=json', '--regex=coal-instance-singleton'],  # noqa
                stdout=subprocess.PIPE
            ).stdout.read()
        )
        external_ip = results[0]['networkInterfaces'][0]['accessConfigs'][0]['natIP']
    except Exception as e:
        logger.exception("Couldn't read external ip address: {0}".format(e))


def pid_exists(pid):
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH:
            return False
    return True


def get_ports_in_use():
    _, port_dirs, _ = os.walk(SERVERS_DIR).next()
    ports = [int(port) for port in port_dirs if fnmatch.fnmatch(port, '[0-9]*')]
    ports.sort()
    return ports


def get_free_port(reserved_ports=None):
    ports_in_use = get_ports_in_use()
    unavailable_ports = ports_in_use
    if reserved_ports is not None:
        unavailable_ports.extend(reserved_ports)
    port = 25565
    while port in unavailable_ports:
        port += 1
    return port


def get_server_dir(port):
    return os.path.join(SERVERS_DIR, str(port))


def get_server_pid(server_dir):
    pid = None
    try:
        with open(os.path.join(server_dir, SERVER_PID_FILENAME), 'r') as f:
            pid = f.read()
    except:
        pass
    return int(pid) if pid else None


def remove_server_pid(server_dir):
    os.remove(os.path.join(server_dir, SERVER_PID_FILENAME))


def get_archive_file_path(server_key):
    return os.path.join(ARCHIVES_DIR, '{0}.zip'.format(server_key))


def get_gcs_archive_name(server_key):
    return 'worlds/{0}.zip'.format(server_key)


def get_archives():
    _, _, archive_files = os.walk(SERVERS_DIR).next()
    archives = [
        (os.path.splitext(archive_file)[0], os.path.join(ARCHIVES_DIR, archive_file)) for archive_file in archive_files if fnmatch.fnmatch(archive_file, '*.zip')  # noqa
    ]
    return archives


def read_server_key(port):
    server_key = None
    server_key_filename = os.path.join(SERVERS_DIR, str(port), SERVER_KEY_FILENAME)
    try:
        with open(server_key_filename, 'r') as f:
            server_key = f.read()
    except:
        pass
    return server_key


def write_server_key(port, server_key):
    server_dir = get_server_dir(port)
    server_key_filename = os.path.join(server_dir, SERVER_KEY_FILENAME)
    with open(server_key_filename, 'w') as server_key_file:
        server_key_file.write(server_key)


def get_servers():
    servers = dict()
    ports = get_ports_in_use()
    for port in ports:
        server_key = read_server_key(port)
        servers[server_key] = {'port': port}
    return servers


def get_minecraft_version(minecraft_url):
    new_mc_dir = None
    try:
        _, mc_dirs, _ = os.walk(MINECRAFT_DIR).next()
        mc = None
        for mc_dir in mc_dirs:
            url_filename = os.path.join(MINECRAFT_DIR, mc_dir, 'url')
            if os.path.exists(url_filename):
                with open(url_filename, 'r') as f:
                    mc_url = f.read().strip()
                    if mc_url == minecraft_url:
                        mc = os.path.join(MINECRAFT_DIR, mc_dir, MINECRAFT_SERVER_JAR_FILENAME)
        if mc is None:
            exists = True
            while exists:
                mc_dir_name = ''.join(random.choice(string.ascii_uppercase) for x in range(10))
                new_mc_dir = os.path.join(MINECRAFT_DIR, mc_dir_name)
                exists = os.path.exists(new_mc_dir)
            os.makedirs(new_mc_dir)
            url_filename = os.path.join(new_mc_dir, 'url')
            with open(url_filename, 'w') as f:
                f.write(minecraft_url)
            mc = os.path.join(new_mc_dir, MINECRAFT_SERVER_JAR_FILENAME)
            urllib.urlretrieve(minecraft_url, mc)
        return mc
    except Exception, e:
        logger.error("Error ({0}) fetching minecraft jar".format(e))
        if new_mc_dir and os.path.exists(new_mc_dir):
            shutil.rmtree(new_mc_dir)
        raise


def copy_server_properties(port, server_properties):
    default_properties = os.path.join(COAL_DIR, 'server.properties')
    server_dir = get_server_dir(port)
    new_properties = os.path.join(server_dir, 'server.properties')
    server_properties['server-port'] = str(port)
    with open(new_properties, "w") as fout:
        with open(default_properties, "r") as fin:
            for line in fin:
                for prop in server_properties:
                    if line.startswith(prop):
                        line = "{0}={1}\n".format(prop, server_properties[prop])
                fout.write(line)


def copy_eula(port):
    dt = datetime.datetime.utcnow()
    default_eula = os.path.join(COAL_DIR, EULA_FILENAME)
    server_dir = get_server_dir(port)
    new_eula = os.path.join(server_dir, EULA_FILENAME)
    if not os.path.exists(new_eula):
        with open(new_eula, "w") as fout:
            with open(default_eula, "r") as fin:
                for line in fin:
                    if line.startswith('TIMESTAMP'):
                        # Fri Jun 27 04:04:26 UTC 2014
                        line = "#{:%a %b %d %H:%M:%S UTC %Y}\n".format(dt)
                    fout.write(line)


def copy_server_files(port, minecraft_url, server_properties):
    server_dir = get_server_dir(port)
    mc = get_minecraft_version(minecraft_url)
    shutil.copy2(mc, server_dir)
    shutil.copy2(os.path.join(COAL_DIR, LOG4J_CONFIG_FILENAME), server_dir)
    copy_eula(port)
    copy_server_properties(port, server_properties)
    filenames = [
        'timezones.py',
        AGENT_FILENAME
    ]
    mc_coal_dir = os.path.join(server_dir, MC_COAL_DIRNAME)
    if not os.path.exists(mc_coal_dir):
        os.makedirs(mc_coal_dir)
    for fn in filenames:
        shutil.copy2(os.path.join(COAL_DIR, fn), mc_coal_dir)


def make_fifo(server_dir):
    fifo = os.path.join(server_dir, COMMAND_FIFO_FILENAME)
    try:
        os.remove(fifo)
    except OSError:
        pass
    os.mkfifo(fifo, 0666)
    return fifo


def write_server_command(server_dir, command):
    fifo = os.path.join(server_dir, COMMAND_FIFO_FILENAME)
    with open(fifo, 'a+') as fifo_file:
        if command:
            if command[-1] != u'\n':
                command += u'\n'
            fifo_file.write(command.encode('ISO-8859-2', errors='ignore'))


def make_run_server_script(server_dir, server_memory, fifo):
    mc_jar = os.path.join(server_dir, MINECRAFT_SERVER_JAR_FILENAME)
    log4j_config = os.path.join(server_dir, LOG4J_CONFIG_FILENAME)
    pid_filename = os.path.join(server_dir, SERVER_PID_FILENAME)
    run_filename = os.path.join(server_dir, RUN_SERVER_FILENAME)
    run_script = '#!/bin/bash\n'
    run_script += '/usr/bin/java -Xmx{0} -Dlog4j.configurationFile={1} -jar {2} nogui <> {3} &\n'.format(
        server_memory, log4j_config, mc_jar, fifo
    )
    run_script += 'echo $! >| {0}\n'.format(pid_filename)
    with open(run_filename, 'w') as run_file:
        run_file.write(run_script)
    st = os.stat(run_filename)
    os.chmod(run_filename, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return run_filename


def load_zip_from_gcs(server_key):
    name = get_gcs_archive_name(server_key)
    credentials = gce.AppAssertionCredentials(scope=STORAGE_API_SCOPE)
    http = credentials.authorize(httplib2.Http())
    service = build('storage', STORAGE_API_VERSION, http=http)
    try:
        request = service.objects().list(bucket=app_bucket, prefix=name)
        result = request.execute()
        items = result.get('items', [])
        if not items:
            return False
    except HttpError as e:
        logging.error("Error ({0}) calling {1}".format(e.resp, getattr(e, 'operationType', None)))
        raise
    archive = get_archive_file_path(server_key)
    retry = True
    while retry:
        with file(archive, 'w') as f:
            request = service.objects().get_media(bucket=app_bucket, object=name)
            media = MediaIoBaseDownload(f, request, chunksize=CHUNKSIZE)
            tries = 0
            done = False
            progress = previous_progress = None
            while not done:
                try:
                    status, done = media.next_chunk()
                    tries = 0
                    progress = int(status.progress() * 100) if status is not None else 0
                    if done:  # Done
                        retry = False
                        progress = 100
                    if progress != previous_progress:
                        if progress % 10 == 0:
                            logger.info("Server {0} archive is {1}% downloaded".format(server_key, progress))
                        try:
                            client.post_event(server_key, START_EVENT, progress)
                        except Exception as e:
                            logger.exception(
                                "Error sending controller load event for server [{0}]: {1}".format(
                                    server_key, e
                                )
                            )
                    previous_progress = progress
                except HttpError as e:
                    if e.resp.status in [404]:  # Start download all over again
                        os.remove(archive)
                        done = True
                        logging.error(
                            "Error ({0}) downloading archive for server {1}. Retrying....".format(
                                str(e), server_key
                            )
                        )
                    elif e.resp.status in [500, 502, 503, 504]:  # Retry with backoff
                        tries += 1
                        if tries > NUM_RETRIES:
                            os.remove(archive)
                            return False
                        sleeptime = 2**min(tries, 4)
                        logger.error(
                            "Error ({0}) downloading archive for server {1}. Sleeping {2} seconds.".format(
                                str(e), server_key, sleeptime
                            )
                        )
                        time.sleep(sleeptime)
                    else:
                        os.remove(archive)
                        return False
    return True


def load_zip(server_key):
    archive = get_archive_file_path(server_key)
    if not os.path.exists(archive):
        return load_zip_from_gcs(server_key)
    return True


def unzip_server_dir(server_key, server_dir):
    archive = get_archive_file_path(server_key)
    if os.path.exists(archive):
        with zipfile.ZipFile(archive, allowZip64=True) as zf:
            for member in zf.infolist():
                zf.extract(member, server_dir)
        os.remove(archive)


def start_minecraft(server_key, server_dir, run_server_script):
    try:
        args = ['sudo', '-u', '_minecraft', run_server_script]
        subprocess.check_call(args, cwd=server_dir)
    except Exception, e:
        logger.error("Error ({0}) starting MC process for server {1}".format(e, server_key))
        raise


def start_server(server_key, **kwargs):
    minecraft_url = kwargs['minecraft_url']
    server_memory = kwargs.get('memory', '256M')
    operator = kwargs.get('operator', None)
    reserved_ports = kwargs.get('reserved_ports', list())
    server_properties = kwargs.get('server_properties', {})
    servers = get_servers()
    if server_key in servers.keys():
        return  # TODO: Handle partial startups/shutdowns
    port = server_properties.get('server-port', None)
    if port:
        port = int(port)
    else:
        port = get_free_port(reserved_ports=reserved_ports)
    if port in get_ports_in_use():
        raise Exception("Requested port {0} already in use".format(port))
    address = external_ip
    if port != 25565:
        address += ':{0}'.format(port)
    server_dir = get_server_dir(port)
    try:
        os.makedirs(server_dir)
        write_server_key(port, server_key)
        found = load_zip(server_key)
        if found:
            unzip_server_dir(server_key, server_dir)
    except Exception as e:
        logger.error("Error ({0}) loading files for server {1}".format(e, server_key))
        raise
    try:
        copy_server_files(port, minecraft_url, server_properties)
    except Exception as e:
        logger.error("Error ({0}) copying files for server {1}".format(e, server_key))
        raise
    try:
        fifo = make_fifo(server_dir)
    except Exception as e:
        logger.error("Error ({0}) making fifo for server {1}".format(e, server_key))
        raise
    try:
        args = ['chown', '-R', '_minecraft', server_dir]
        subprocess.check_call(args, cwd=server_dir)
    except Exception as e:
        logger.error("Error ({0}) chowning files for server {1}".format(e, server_key))
        raise
    # Start Agent
    try:
        mc_coal_dir = os.path.join(server_dir, MC_COAL_DIRNAME)
        agent = os.path.join(mc_coal_dir, AGENT_FILENAME)
        args = [agent]
        args.append('--coal_host={0}.appspot.com'.format(project))
        args.append('--agent_client_id={0}'.format(kwargs['agent_client_id']))
        args.append('--agent_secret={0}'.format(kwargs['agent_secret']))
        args.append('--address={0}'.format(address))
        pid = subprocess.Popen(args, cwd=mc_coal_dir).pid
        pid_filename = os.path.join(server_dir, AGENT_PID_FILENAME)
        with open(pid_filename, 'w') as pid_file:
            pid_file.write(str(pid))
    except Exception as e:
        logger.error("Error ({0}) starting agent process for server {1}".format(e, server_key))
        raise
    # Create run script
    try:
        run_server_script = make_run_server_script(server_dir, server_memory, fifo)
    except Exception, e:
        logger.error("Error ({0}) creating run_server_script for server {1}".format(e, server_key))
        raise
    # Start minecraft
    start_minecraft(server_key, server_dir, run_server_script)
    # Add operator to ops and whitelist if provided
    if operator:
        write_server_command(server_dir, 'op {0}'.format(operator))
        write_server_command(server_dir, 'whitelist add {0}'.format(operator))


def stop_minecraft(server_key, server_dir):
    try:
        write_server_command(server_dir, 'stop')
        pid = get_server_pid(server_dir)
        if pid:
            while pid_exists(pid):
                time.sleep(0.5)
            remove_server_pid(server_dir)
    except Exception as e:
        logger.error("Error ({0}) stopping MC process for server {1}".format(e, server_key))


def minecraft_save_off(server_key, server_dir):
    try:
        write_server_command(server_dir, 'save-all')
        write_server_command(server_dir, 'save-off')
    except Exception as e:
        logger.error("Error ({0}) turning off save for server {1}".format(e, server_key))


def minecraft_save_on(server_key, server_dir):
    try:
        write_server_command(server_dir, 'save-on')
    except Exception as e:
        logger.error("Error ({0}) turning on save for server {1}".format(e, server_key))


def zip_server_dir(server_dir, archive_file):
    skip_dirs = [
        os.path.join(server_dir, MC_COAL_DIRNAME),
        os.path.join(server_dir, 'logs'),
    ]
    skip_files = [
        COMMAND_FIFO_FILENAME,
        MINECRAFT_SERVER_JAR_FILENAME,
        LOG4J_CONFIG_FILENAME,
        SERVER_KEY_FILENAME,
        AGENT_PID_FILENAME,
        SERVER_PID_FILENAME,
        RUN_SERVER_FILENAME
    ]
    abs_src = os.path.abspath(server_dir)
    with zipfile.ZipFile(archive_file, mode="w", allowZip64=True) as zf:
        for dirname, subdirs, files in os.walk(server_dir):
            if dirname not in skip_dirs:
                arcname = os.path.relpath(dirname, abs_src)
                zf.write(dirname, arcname)
                for filename in files:
                    if filename not in skip_files:
                        absname = os.path.abspath(os.path.join(dirname, filename))
                        arcname = os.path.relpath(absname, abs_src)
                        zf.write(absname, arcname)


def upload_zip_to_gcs(server_key, archive_file, backup=False):
    name = get_gcs_archive_name(server_key)
    credentials = gce.AppAssertionCredentials(scope=STORAGE_API_SCOPE)
    http = credentials.authorize(httplib2.Http())
    service = build('storage', STORAGE_API_VERSION, http=http)
    retry = True
    while retry:
        media = MediaFileUpload(archive_file, chunksize=CHUNKSIZE, resumable=True)
        if not media.mimetype():
            media = MediaFileUpload(archive_file, 'application/zip', resumable=True)
        request = service.objects().insert(bucket=app_bucket, name=name, media_body=media)
        progress = previous_progress = None
        tries = 0
        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                tries = 0
                progress = int(status.progress() * 100) if status is not None else 0
                if response is not None:  # Done
                    retry = False
                    progress = 100
                if progress != previous_progress:
                    if progress % 10 == 0:
                        logger.info("Server {0} archive is {1}% uploaded".format(server_key, progress))
                    if not backup:
                        try:
                            client.post_event(server_key, STOP_EVENT, progress)
                        except Exception as e:
                            logger.exception(
                                "Error sending controller save event for server [{0}]: {1}".format(
                                    server_key, e
                                )
                            )
                previous_progress = progress
            except HttpError as e:
                if e.resp.status in [404]:  # Start upload all over again
                    response = None
                    logging.error(
                        "Error ({0}) uploading archive for server {1}. Retrying....".format(
                            str(e), server_key
                        )
                    )
                elif e.resp.status in [500, 502, 503, 504]:  # Retry with backoff
                    tries += 1
                    if tries > NUM_RETRIES:
                        raise
                    sleeptime = 2**min(tries, 4)
                    logger.error(
                        "Error ({0}) uploading archive for server {1}. Sleeping {2} seconds.".format(
                            str(e), server_key, sleeptime
                        )
                    )
                    time.sleep(sleeptime)
                else:
                    raise
    os.remove(archive_file)


def backup_server(server_key, **kwargs):
    servers = get_servers()
    server = servers.get(server_key, None)
    if server is None:
        return  # TODO: Handle partial startups/shutdowns
    port = server['port']
    server_dir = get_server_dir(port)
    # Archive server_dir
    archive_successful = False
    archive = get_archive_file_path(server_key)
    write_server_command(server_dir, '/say Saving game...')
    try:
        # Pause saving
        minecraft_save_off(server_key, server_dir)
    except Exception as e:
        logger.error("Error ({0}) pausing saves for server {1}".format(e, server_key))
    try:
        zip_server_dir(server_dir, archive)
        archive_successful = True
    except Exception as e:
        logger.error("Error ({0}) archiving server {1}".format(e, server_key))
    try:
        # Unpause saving
        minecraft_save_on(server_key, server_dir)
    except Exception as e:
        logger.error("Error ({0}) unpausing saves for server {1}".format(e, server_key))
    try:
        if archive_successful:
            upload_zip_to_gcs(server_key, archive, backup=True)
            write_server_command(server_dir, '/say Game saved.')
    except Exception as e:
        write_server_command(server_dir, '/say Game save failed.')
        logger.error("Error ({0}) uploading archived server {1}".format(e, server_key))


def stop_server(server_key, **kwargs):
    servers = get_servers()
    server = servers.get(server_key, None)
    if server is None:
        return  # TODO: Handle partial startups/shutdowns
    port = server['port']
    server_dir = get_server_dir(port)
    # Stop minecraft
    stop_minecraft(server_key, server_dir)
    # Archive server_dir
    archive_successful = False
    archive = get_archive_file_path(server_key)
    try:
        zip_server_dir(server_dir, archive)
        archive_successful = True
    except Exception as e:
        logger.error("Error ({0}) archiving server {1}".format(e, server_key))
    try:
        upload_zip_to_gcs(server_key, archive)
    except Exception as e:
        logger.error("Error ({0}) uploading archived server {1}".format(e, server_key))
    try:
        # Stop Agent
        with open(os.path.join(server_dir, AGENT_PID_FILENAME), 'r') as f:
            pid = f.read()
        os.kill(int(pid), signal.SIGTERM)
        os.waitpid(int(pid), 0)
    except OSError as e:
        logger.error("Error ({0}) terminating agent process for server {1}".format(e, server_key))
    # Delete server_dir
    if archive_successful:
        shutil.rmtree(server_dir)


def restart_server(server_key, **kwargs):
    servers = get_servers()
    server = servers.get(server_key, None)
    if server is None:
        return  # TODO: Handle partial startups/shutdowns
    port = server['port']
    server_dir = get_server_dir(port)
    run_server_script = os.path.join(server_dir, RUN_SERVER_FILENAME)
    # Stop minecraft
    stop_minecraft(server_key, server_dir)
    # Start minecraft
    start_minecraft(server_key, server_dir, run_server_script)


def complete_tasks(tasks):
    completed_tasks = list()
    for task in tasks:
        try:
            task_id = task['id']
            payload = task['payload']
            event = payload.pop('event')
            logger.info("Working task {0}: {1}".format(task_id, event))
            server_key = payload.pop('server_key')
            if event == 'START_SERVER':
                start_server(server_key, **payload)
            if event == 'BACKUP_SERVER':
                backup_server(server_key, **payload)
            if event == 'RESTART_SERVER':
                restart_server(server_key, **payload)
            if event == 'STOP_SERVER':
                stop_server(server_key, **payload)
            completed_tasks.append(task)
            logger.info(u"Completed task {0}: {1}".format(task_id, event))
        except Exception, e:
            logger.error(u"Error ({0}: {1}) completing task {2}".format(type(e).__name__, e, task['id']))
    return completed_tasks


def lease_tasks(service):
    tasks = []
    try:
        request = service.tasks().lease(
            project=project, taskqueue='controller', leaseSecs=300, numTasks=1
        )
        response = request.execute()
        tasks += response.get('items', [])
        for task in tasks:
            try:
                task['payload'] = json.loads(base64.b64decode(task['payloadBase64']))
            except Exception, e:
                logger.error(u"Error ({0}: {1}) parsing task {2}".format(type(e).__name__, e, task['id']))
    except Exception, e:
        logger.error(u"Error ({0}: {1}) leasing tasks".format(type(e).__name__, e))
    return tasks


def delete_tasks(service, tasks):
    for task in tasks:
        try:
            request = service.tasks().delete(
                project='s~{0}'.format(project),
                taskqueue='controller',
                task=task['id']
            )
            request.execute()
        except Exception, e:
            logger.error(u"Error ({0}: {1}) deleting task {2}".format(type(e).__name__, e, task['id']))


def init_logger(debug=False, logfile='controller.log'):
    main_logger = logging.getLogger('main')
    main_logger.setLevel(logging.DEBUG)
    main_logger.propagate = False
    formatter = logging.Formatter(
        u'%(asctime)s : %(name)-8s %(levelname)-6s %(message)s'
    )
    if logfile:
        fh = logging.FileHandler(logfile)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        main_logger.addHandler(fh)
    ch = logging.StreamHandler()
    if debug:
        ch.setLevel(logging.DEBUG)
    else:
        ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    main_logger.addHandler(ch)


def main(argv):
    global client
    global project
    global app_bucket
    global logger
    init_logger()
    logger = logging.getLogger('main')
    if not os.path.exists(SERVERS_DIR):
        os.makedirs(SERVERS_DIR)
    if not os.path.exists(ARCHIVES_DIR):
        os.makedirs(ARCHIVES_DIR)
    if not os.path.exists(MINECRAFT_DIR):
        os.makedirs(MINECRAFT_DIR)
    try:
        with open('/coal/project_id', 'r') as f:
            project = f.read().strip()
        with open('/coal/client_id', 'r') as f:
            client_id = f.read().strip()
        with open('/coal/secret', 'r') as f:
            secret = f.read().strip()
        init_external_ip()
        client = ControllerClient('{0}.appspot.com'.format(project), client_id, secret)
        app_bucket = '{0}.appspot.com'.format(project)
        credentials = gce.AppAssertionCredentials(scope=TQ_API_SCOPE)
        http = credentials.authorize(httplib2.Http())
        service = build('taskqueue', TQ_API_VERSION, http=http)
        while True:
            tasks = lease_tasks(service)
            if tasks:
                completed_tasks = []
                try:
                    completed_tasks = complete_tasks(tasks)
                finally:
                    delete_tasks(service, completed_tasks)
            else:
                # Restart crashed servers
                servers = get_servers()
                if servers:
                    for server_key, server in servers.iteritems():
                        server_dir = get_server_dir(server['port'])
                        pid = get_server_pid(server_dir)
                        if pid and not pid_exists(pid):
                            logger.error("Server '{0}' has crashed. Restarting minecraft.".format(server_key))
                            run_server_script = os.path.join(server_dir, RUN_SERVER_FILENAME)
                            start_minecraft(server_key, server_dir, run_server_script)
                # Save non-uploaded archives
                archives = get_archives()
                if archives:
                    server_key, archive_file = archives[0]
                    upload_zip_to_gcs(server_key, archive_file, backup=True)
                else:
                    time.sleep(10.0)
    except KeyboardInterrupt:
        logger.info(u"Canceled")
    except SystemExit:
        logger.info(u"System Exit")
    except Exception, e:
        logger.error(u"Unexpected {0}: {1}".format(type(e).__name__, e))
    logger.info(u"Shutting down... Goodbye.")


if __name__ == "__main__":
    main(sys.argv[1:])
