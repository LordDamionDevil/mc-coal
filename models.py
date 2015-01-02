import fix_path  # noqa

from cStringIO import StringIO
import datetime
import logging
import re
import random
import string

from google.appengine.ext import blobstore, ndb
from google.appengine.api import users, mail, app_identity, taskqueue, urlfetch, memcache

import webapp2_extras.appengine.auth.models as auth_models

import pytz

from PIL import Image, ImageFilter

from restler.decorators import ae_ndb_serializer

from slugify import slugify

from channel import ServerChannels

from filters import datetime_filter
from image import NdbImage
from patterns import (
    UNKNOWN_TAG, TIMESTAMP_TAG, LOGIN_TAG, LOGOUT_TAG, CHAT_TAG, STOPPING_TAG, STARTING_TAG, DEATH_TAG,
    ACHIEVEMENT_TAG, CHANNEL_TAGS_SET, REGEX_TAGS
)
from server_queue import start_server, backup_server, restart_server, stop_server
import search


UNICODE_ASCII_DIGITS = string.digits.decode('ascii')
SECTION_SIGN = u'\xa7'
AGENT_CLIENT_ID = 'mc-coal-agent'
TICKS_PER_PLAY_SECOND = 20
SERVER_UNKNOWN = 'UNKNOWN'
SERVER_QUEUED_START = 'QUEUED_START'
SERVER_QUEUED_RESTART = 'QUEUED_RESTART'
SERVER_QUEUED_STOP = 'QUEUED_STOP'
SERVER_HAS_STARTED = 'HAS_STARTED'
SERVER_HAS_STOPPED = 'HAS_STOPPED'
SERVER_LOADING = 'LOADING'
SERVER_LOADED = 'LOADED'
SERVER_SAVING = 'SAVING'
SERVER_SAVED = 'SAVED'
SERVER_RUNNING = 'RUNNING'
SERVER_STOPPED = 'STOPPED'
INSTANCE_UNKNOWN = 'UNKNOWN'


class MojangException(Exception):
    pass


def seconds_since_epoch(dt):
    if not dt:
        return None
    return (dt - datetime.datetime(1970, 1, 1)).total_seconds()


def safe_float_from_string(float_string):
    try:
        return float(float_string)
    except:
        return None


def dts_to_naive_utc(dts, tz):
    dt = datetime.datetime.strptime(dts, "%Y-%m-%d %H:%M:%S")
    dt = tz.localize(dt)
    return dt.astimezone(pytz.utc).replace(tzinfo=None)


def name_to_timezone(name):
    try:
        timezone = pytz.timezone(name)
    except:
        timezone = pytz.utc
    return timezone


def strip_control_codes(s):
    ns = s
    i = ns.find(SECTION_SIGN)
    while i > -1:
        ns = ns[0:i] + ns[i+2:]
        i = ns.find(SECTION_SIGN)
    return ns


@ae_ndb_serializer
class User(auth_models.User):
    active = ndb.BooleanProperty(default=False)
    admin = ndb.BooleanProperty(default=False)
    authorized_client_ids = ndb.StringProperty(repeated=True)
    email = ndb.StringProperty()
    nickname = ndb.StringProperty()
    usernames = ndb.StringProperty(repeated=True)
    timezone_name = ndb.StringProperty(default='UTC')
    last_login = ndb.DateTimeProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @property
    def name(self):
        return self.nickname or self.email

    @property
    def timezone(self):
        return name_to_timezone(self.timezone_name)

    @property
    def is_gae_user(self):
        for auth_id in self.auth_ids:
            if auth_id.startswith('gaeuser:'):
                return True
        return False

    def get_server_username(self, server_key):
        for username in self.usernames:
            if Player.lookup(server_key, username) is not None:
                return username
        return None

    def get_server_play_name(self, server_key):
        username = self.get_server_username(server_key)
        if username is not None:
            return username
        if self.nickname:
            return '*{0}'.format(self.nickname)
        return self.email

    def add_username(self, username):
        if username not in self.usernames:
            self.usernames.append(username)

    def set_usernames(self, usernames):
        for username in usernames:
            u = User.lookup(username=username)
            if u is not None and u.key != self.key:
                raise Exception("Username already taken: {0}".format(username))
        self.usernames = usernames

    def add_auth_id(self, auth_id):
        if auth_id not in self.auth_ids:
            self.auth_ids.append(auth_id)

    def get_player(self, server_key):
        if self.username:
            return Player.get_or_create(server_key, self.username)
        return None

    def is_client_id_authorized(self, client_id):
        return client_id in self.authorized_client_ids

    def authorize_client_id(self, client_id):
        if client_id and client_id not in self.authorized_client_ids:
            self.authorized_client_ids.append(client_id)
            self.put()

    def unauthorize_client_id(self, client_id):
        from oauth import authorization_provider
        if client_id and client_id in self.authorized_client_ids:
            self.authorized_client_ids.remove(client_id)
            self.put()
        authorization_provider.discard_client_user_tokens(client_id, self.key)

    def is_username(self, username):
        return username in self.usernames if username is not None else False

    def is_player(self, player):
        if player is not None:
            return self.is_username(player.username)
        return False

    def merge(self, user):
        if self.key == user.key:
            return
        for auth_id in user.auth_ids:
            self.add_auth_id(auth_id)
        for username in user.usernames:
            if username not in self.usernames:
                self.usernames.append(username)
        self.put_async()
        screenshots = []
        for screenshot in ScreenShot.query_by_user_key(user.key):
            screenshot.user_key = self.key
            screenshots.append(screenshot)
        ndb.put_multi(screenshots)
        user.key.delete()

    @classmethod
    def _pre_delete_hook(cls, key):
        user = key.get()
        values = []
        for auth_id in user.auth_ids:
            unique = '%s.auth_id:%s' % (user.__class__.__name__, auth_id)
            values.append(unique)
        user.unique_model.delete_multi(values)

    @classmethod
    def get_gae_user_auth_id(cls, gae_user_id=None, gae_user=None):
        if not gae_user_id:
            gae_user_id = gae_user.user_id() if gae_user else None
        return 'gaeuser:{0}'.format(gae_user_id) if gae_user_id else None

    @classmethod
    def create_by_gae_user(cls, gae_user=None):
        if not gae_user:
            gae_user = users.get_current_user()
        if gae_user:
            return cls.create_user(
                cls.get_gae_user_auth_id(gae_user=gae_user),
                email=gae_user.email(),
                nickname=gae_user.nickname()
            )
        return False, None

    @classmethod
    def get_indie_auth_id(cls, me=None):
        return 'indieuser:{0}'.format(me) if me else None

    @classmethod
    def get_mojang_auth_id(cls, uuid):
        return 'mojang:{0}'.format(uuid) if uuid else None

    @classmethod
    def lookup(cls, email=None, username=None, short_name=None):
        if email is not None or username is not None:
            query = cls.query()
            if email is not None:
                query = query.filter(ndb.StringProperty('email') == email)
            if username is not None:
                query = query.filter(ndb.StringProperty('usernames') == username)
            return query.get()
        return None

    @classmethod
    def is_single_admin(cls):
        return cls.query().filter(cls.admin == True).count(keys_only=True, limit=2) < 2  # noqa

    @classmethod
    def send_admin_email(cls, subject, body, admin=None):
        admins = [admin] if admin else cls.query_admin()
        for admin in admins:
            if admin.email:
                mail.send_mail(
                    sender='noreply@{0}.appspotmail.com'.format(app_identity.get_application_id()),
                    to=admin.email,
                    subject=subject,
                    body=body
                )

    @classmethod
    def query_all(cls):
        return cls.query().order(cls.created)

    @classmethod
    def query_all_reverse(cls):
        return cls.query().order(-cls.created)

    @classmethod
    def query_admin(cls):
        return cls.query().filter(User.admin == True)  # noqa


@ae_ndb_serializer
class MinecraftDownload(ndb.Model):
    version = ndb.StringProperty(required=True)
    url = ndb.StringProperty(required=True)

    def verify(self):
        result = urlfetch.fetch(url=self.url, method=urlfetch.HEAD)
        if result.status_code >= 400:
            return False
        return True

    @classmethod
    def create(cls, version, url, verify=True):
        key = ndb.Key(cls, version)
        exists = key.get()
        if exists:
            raise Exception("Minecraft version ({0}) already exists".format(version))
        mc = cls(key=key, version=version, url=url)
        if verify and not mc.verify():
            raise Exception("Minecraft URL ({0}) is invalid".format(url))
        mc.put()
        return mc

    @classmethod
    def lookup(cls, version):
        key = ndb.Key(cls, version)
        return key.get()


@ae_ndb_serializer
class Server(ndb.Model):
    name = ndb.StringProperty()
    short_name = ndb.StringProperty()
    is_gce = ndb.BooleanProperty(default=False)
    version = ndb.StringProperty()
    running_version = ndb.StringProperty()
    memory = ndb.StringProperty(default='256M')
    operator = ndb.StringProperty()
    address = ndb.StringProperty()
    idle_timeout = ndb.IntegerProperty(default=5)
    active = ndb.BooleanProperty(default=True)
    status = ndb.StringProperty(default=SERVER_UNKNOWN)
    completed = ndb.IntegerProperty(default=None)
    is_running = ndb.ComputedProperty(lambda self: self.status == SERVER_RUNNING)
    is_stopped = ndb.ComputedProperty(lambda self: self.status == SERVER_STOPPED)
    is_queued_start = ndb.ComputedProperty(lambda self: self.status in [SERVER_QUEUED_START, SERVER_LOADING, SERVER_LOADED])  # noqa
    is_queued_restart = ndb.ComputedProperty(lambda self: self.status == SERVER_QUEUED_RESTART)
    is_queued_stop = ndb.ComputedProperty(lambda self: self.status in [SERVER_QUEUED_STOP, SERVER_SAVING, SERVER_SAVED])
    is_queued = ndb.ComputedProperty(
        lambda self: self.status in [
            SERVER_QUEUED_START, SERVER_QUEUED_RESTART, SERVER_QUEUED_STOP, SERVER_LOADING, SERVER_LOADED, SERVER_SAVING
        ]
    )
    is_loading = ndb.ComputedProperty(lambda self: self.status == SERVER_LOADING)
    is_saving = ndb.ComputedProperty(lambda self: self.status == SERVER_SAVING)
    is_unknown = ndb.ComputedProperty(lambda self: self.status == SERVER_UNKNOWN)
    last_ping = ndb.DateTimeProperty()
    last_server_day = ndb.IntegerProperty()
    last_server_time = ndb.IntegerProperty()
    is_raining = ndb.BooleanProperty()
    is_thundering = ndb.BooleanProperty()
    num_overloads = ndb.IntegerProperty()
    ms_behind = ndb.IntegerProperty()
    skipped_ticks = ndb.IntegerProperty()
    timestamp = ndb.DateTimeProperty()
    queued = ndb.DateTimeProperty()
    idle = ndb.DateTimeProperty()
    last_played = ndb.DateTimeProperty(default=None)
    agent_key = ndb.KeyProperty()
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @property
    def server_day(self):
        return self.last_server_day

    @property
    def server_time(self):
        st = self.last_server_time
        if self.is_running and self.timestamp is not None and st is not None:
            d = datetime.datetime.utcnow() - self.timestamp
            st += d.seconds * TICKS_PER_PLAY_SECOND
            if st >= 24000:
                st %= 24000
        return st

    @property
    def agent(self):
        return self.agent_key.get() if self.agent_key is not None else None

    @property
    def mc_properties(self):
        return MinecraftProperties.get_or_create(self.key)

    @property
    def has_open_play_session(self):
        return PlaySession.query_open(self.key).get() is not None

    @property
    def minecraft_url(self):
        if self.version:
            download = ndb.Key(MinecraftDownload, self.version).get()
            if download and download.verify():
                return download.url
        else:
            return None

    @property
    def open_sessions(self):
        playing_usernames = []
        open_sessions = []
        open_sessions_query = PlaySession.query_latest_open(self.key)
        for open_session in open_sessions_query:
            if open_session.username and open_session.username not in playing_usernames:
                playing_usernames.append(open_session.username)
                open_sessions.append(open_session)
        return open_sessions

    @property
    def url_key(self):
        if self.short_name:
            return self.short_name
        return self.key.urlsafe()

    @property
    def idle_shutdown(self):
        shutdown = None
        if self.is_gce and self.is_running and self.idle and self.idle_timeout:
            shutdown = self.idle + datetime.timedelta(seconds=self.idle_timeout*60)
        return shutdown

    @property
    def idle_shutdown_in(self):
        shutdown_in = None
        shutdown = self.idle_shutdown
        if shutdown:
            shutdown_in = 0
            now = datetime.datetime.utcnow()
            if now < shutdown:
                shutdown_in = shutdown - now
        return shutdown_in

    def set_short_name(self, short_name):
        try:
            ndb.Key(urlsafe=short_name)
            return False  # Can't set the short_name to a valid key
        except:
            pass
        short_name = slugify(short_name) if short_name else None
        if short_name == self.short_name:
            return True
        if not short_name or auth_models.Unique.create("Server.short_name.{0}".format(short_name)):
            old_short_name = self.short_name
            self.short_name = short_name
            self.put()
            if old_short_name:
                auth_models.Unique.delete_multi(["Server.short_name.{0}".format(old_short_name)])
            return True
        else:
            return False

    def start(self):
        if self.is_gce and not (self.is_running or self.is_queued_start):
            if self.minecraft_url is None:
                raise Exception("No valid minecraft version specified for server")
            if not self.mc_properties.eula_agree:
                raise Exception("You must agree to the Mojang Minecraft EULA to Play")
            start_server(self, reserved_ports=Server.reserved_ports(ignore_server=self))
            self.last_played = datetime.datetime.utcnow()
            self.update_status(status=SERVER_QUEUED_START)

    def backup(self):
        if self.is_gce and self.is_running:
            backup_server(self)

    def restart(self):
        if self.is_gce and not self.is_queued_restart:
            restart_server(self)
            self.update_status(status=SERVER_QUEUED_RESTART)

    def stop(self):
        if self.is_gce and not (self.is_stopped or self.is_queued_stop):
            stop_server(self)
            self.update_status(status=SERVER_QUEUED_STOP)

    def stop_if_idle(self):
        shutdown = self.idle_shutdown
        if shutdown and datetime.datetime.utcnow() > shutdown:
            self.stop()

    def update_version(self, server_version):
        if server_version is not None:
            if self.running_version != server_version:
                self.running_version = server_version
                self.put()

    def update_status(
        self, status=None, last_ping=None, server_day=None, server_time=None, is_raining=None, is_thundering=None,
        num_overloads=None, ms_behind=None, skipped_ticks=None, address=None, timestamp=None, completed=None
    ):
        logging.info(
            "Updating Status (current: {0}, queued: {1}, new: {2}, completed: {3})".format(
                self.status, self.queued, status, completed
            )
        )
        changed = False
        now = datetime.datetime.utcnow()
        address = address or self.address
        timeout = now - datetime.timedelta(minutes=5)
        previous_status = self.status
        # Set queued datetime
        if status in [SERVER_QUEUED_START, SERVER_QUEUED_RESTART, SERVER_QUEUED_STOP]:
            self.queued = datetime.datetime.utcnow()
            self.idle = None
            changed = True
        elif status in [SERVER_LOADING, SERVER_LOADED, SERVER_SAVING]:
            if completed is not None:
                self.completed = completed
                self.queued = datetime.datetime.utcnow()
                self.idle = None
                changed = True
        elif status is not None and self.queued is not None:
            # Don't update status if status is not desired outcome of queued status, will go UNKNOWN eventually if something goes wrong  # noqa
            if (
                (previous_status in [SERVER_QUEUED_START, SERVER_LOADING, SERVER_LOADED] and status not in [SERVER_HAS_STARTED, SERVER_RUNNING]) or  # noqa
                (previous_status == SERVER_QUEUED_RESTART and status not in [SERVER_HAS_STARTED, SERVER_RUNNING]) or  # noqa
                (previous_status in [SERVER_QUEUED_STOP, SERVER_SAVING] and status is not SERVER_SAVED)
            ):
                status = previous_status
            else:
                self.completed = None
                self.queued = None
                self.idle = None
                changed = True
        # No status provided, check for timeout on running servers
        if status is None:
            status = previous_status
            if previous_status != SERVER_STOPPED:
                if self.queued is None:
                    if self.last_ping is None or self.last_ping < timeout:
                        self.idle = None
                        status = SERVER_UNKNOWN
                elif self.queued < timeout:
                    self.queued = None
                    self.completed = None
                    self.idle = None
                    status = SERVER_UNKNOWN
        if status != previous_status:
            changed = True
        # Update address
        if status in [SERVER_HAS_STOPPED, SERVER_SAVED, SERVER_STOPPED]:
            address = None
        if address != self.address:
            self.address = address
            changed = True
        # Update server day/time
        if (
            (server_day is not None and server_day != self.last_server_day) or
            (server_time is not None and server_time != self.last_server_time)
        ):
            self.timestamp = timestamp or datetime.datetime.utcnow()
            if server_day is not None:
                self.last_server_day = server_day
            if server_time is not None:
                self.last_server_time = server_time
            changed = True
        # Update server weather
        if is_raining is not None and is_raining != self.is_raining:
            self.is_raining = is_raining
            changed = True
        if is_thundering is not None and is_thundering != self.is_thundering:
            self.is_thundering = is_thundering
            changed = True
        # Update overloads
        if num_overloads is not None and num_overloads != self.num_overloads:
            self.num_overloads = num_overloads
            changed = True
        if ms_behind is not None and ms_behind != self.ms_behind:
            self.ms_behind = ms_behind
            changed = True
        if skipped_ticks is not None and skipped_ticks != self.skipped_ticks:
            self.skipped_ticks = skipped_ticks
            changed = True
        # Record pings every minute, even if nothing changed
        if last_ping is not None:
            if self.last_ping is None or self.last_ping < last_ping - datetime.timedelta(minutes=1):
                changed = True
        # Close all open play sessions if stopped
        if status in [SERVER_HAS_STOPPED, SERVER_SAVED]:
            PlaySession.close_all_current(self.key, now)
        # Put server changes
        if changed:
            logging.info(
                "Changed Status (previous: {0}, new: {1}, queued: {2})".format(
                    self.status, status, self.queued
                )
            )
            if status == SERVER_HAS_STARTED:
                status = SERVER_RUNNING
            elif status in [SERVER_HAS_STOPPED, SERVER_SAVED]:
                status = SERVER_STOPPED
            logging.info(
                "Actual Changed Status (previous: {0}, new: {1}, queued: {2})".format(
                    self.status, status, self.queued
                )
            )
            self.status = status
            if last_ping is not None:
                self.last_ping = last_ping
            self.put()
            # Email admins
            send_email = previous_status != status
            if status in [
                SERVER_QUEUED_START, SERVER_QUEUED_RESTART, SERVER_QUEUED_STOP,
                SERVER_LOADING, SERVER_LOADED, SERVER_SAVING, SERVER_SAVED
            ]:
                send_email = False
            if send_email:
                for admin in User.query_admin():
                    subject = "{0} server status is {1}".format(self.name, status)
                    body = 'The {0} server status is {1} as of {2}.\n\nThe last agent ping was on {3}'.format(
                        self.name,
                        status,
                        datetime_filter(datetime.datetime.utcnow(), timezone=admin.timezone),
                        datetime_filter(self.last_ping, timezone=admin.timezone) if self.last_ping else 'NEVER'
                    )
                    User.send_admin_email(subject, body, admin=admin)
        ServerChannels.send_status(self)

    def deactivate(self):
        if self.is_running:
            self.stop()
        self.active = False
        self.status = SERVER_UNKNOWN
        self.idle = None
        self.set_short_name(None)
        self.put()

    @classmethod
    def _pre_delete_hook(cls, key):
        instance = key.get()
        if instance.agent_key is not None:
            instance.agent_key.delete()
        instance.set_short_name(None)

    @classmethod
    def create(cls, **kwargs):
        instance = cls(**kwargs)
        instance.put()
        if instance.agent_key is None:
            from oauth import Client, authorization_provider
            existing_agent_client = True
            while existing_agent_client:
                random_int = ''.join([random.choice(UNICODE_ASCII_DIGITS) for x in xrange(5)])
                client_id = Client.get_key_name("{0}-{1}".format(AGENT_CLIENT_ID, random_int))
                agent_client_key = Client.get_key(client_id)
                existing_agent_client = agent_client_key.get()
            agent_client = Client(
                key=agent_client_key,
                client_id=client_id,
                server_key=instance.key,
                redirect_uris=['/'],
                scope=['agent'],
                secret=authorization_provider.generate_client_secret()
            )
            agent_client.put()
            instance.agent_key = agent_client.key
            instance.put()
        return instance

    @classmethod
    def query_all(cls):
        return cls.query().filter(cls.active == True).order(-cls.last_played).order(-cls.created)  # noqa

    @classmethod
    def query_all_reverse(cls):
        return cls.query().filter(cls.active == True).order(cls.last_played).order(cls.created)  # noqa

    @classmethod
    def query_running(cls):
        return cls.query_all().filter(cls.is_running == True)  # noqa

    @classmethod
    def get_by_short_name(cls, short_name):
        return cls.query_all().filter(cls.short_name == short_name).get()

    @classmethod
    def reserved_ports(cls, ignore_server=None):
        ports = []
        for server in cls.query_all():
            if not ignore_server or server.key != ignore_server.key:
                port = server.mc_properties.server_port
                if port is not None:
                    ports.append(port)
        return ports


class ServerModel(ndb.Model):
    @property
    def server_key(self):
        return self.key.parent()

    @classmethod
    def server_query(cls, server_key):
        return cls.query(ancestor=server_key)


@ae_ndb_serializer
class MinecraftProperties(ServerModel):
    server_port = ndb.IntegerProperty()
    motd = ndb.StringProperty(default='An MC-COAL Minecraft Server')
    white_list = ndb.BooleanProperty(default=False)
    gamemode = ndb.IntegerProperty(default=0)
    force_gamemode = ndb.BooleanProperty(default=False)
    level_type = ndb.StringProperty(default='DEFAULT')
    level_seed = ndb.StringProperty()
    generator_settings = ndb.StringProperty()
    difficulty = ndb.IntegerProperty(default=1)
    pvp = ndb.BooleanProperty(default=False)
    hardcore = ndb.BooleanProperty(default=False)
    allow_flight = ndb.BooleanProperty(default=False)
    allow_nether = ndb.BooleanProperty(default=True)
    max_build_height = ndb.IntegerProperty(default=256)
    generate_structures = ndb.BooleanProperty(default=True)
    spawn_npcs = ndb.BooleanProperty(default=True)
    spawn_animals = ndb.BooleanProperty(default=True)
    spawn_monsters = ndb.BooleanProperty(default=True)
    view_distance = ndb.IntegerProperty(default=10)
    player_idle_timeout = ndb.IntegerProperty(default=0)
    max_players = ndb.IntegerProperty(default=20)
    max_world_size = ndb.IntegerProperty(default=29999984)
    spawn_protection = ndb.IntegerProperty(default=16)
    enable_command_block = ndb.BooleanProperty(default=False)
    snooper_enabled = ndb.BooleanProperty(default=True)
    resource_pack = ndb.StringProperty()
    op_permission_level = ndb.IntegerProperty(default=3)
    eula_agree = ndb.BooleanProperty(default=False)

    @property
    def server(self):
        return self.key.parent().get()

    @property
    def server_properties(self):
        mc_props = {}
        for prop in self._properties:
            mc_prop_name = prop.replace('_', '-')
            value = getattr(self, prop)
            if mc_prop_name != 'server-port' or value:
                mc_props[mc_prop_name] = str(value) if value is not None else ''
                if mc_props[mc_prop_name] in ['False', 'True']:
                    mc_props[mc_prop_name] = mc_props[mc_prop_name].lower()
        return mc_props

    @classmethod
    def get_or_create(cls, server_key, **kwargs):
        return cls.get_or_insert('mc-properties-{0}'.format(server_key.urlsafe()), parent=server_key, **kwargs)


@ae_ndb_serializer
class Player(ServerModel):
    username = ndb.StringProperty(required=True)
    last_login_timestamp = ndb.DateTimeProperty()

    @property
    def user(self):
        return User.lookup(username=self.username)

    @property
    def is_playing(self):
        return PlaySession.current(self.server_key, self.username) is not None

    @property
    def last_session_duration(self):
        last_session = PlaySession.last(self.server_key, self.username)
        return last_session.duration if last_session is not None else None

    @property
    def last_login_timestamp_sse(self):
        return seconds_since_epoch(self.last_login_timestamp)

    def is_user(self, user):
        return user.is_username(self.username) if user is not None else False

    def _post_put_hook(self, future):
        search.add_player(self)

    @classmethod
    def is_valid_username(cls, username):
        if username and '@' not in username and '*' not in username:
            return True
        return False

    @classmethod
    def _post_delete_hook(cls, key, future):
        search.remove_player(key)

    @classmethod
    def get_or_create(cls, server_key, username):
        return cls.get_or_insert(username, parent=server_key, username=username)

    @classmethod
    def query_all(cls, server_key):
        return cls.server_query(server_key).order(cls.last_login_timestamp)

    @classmethod
    def query_all_reverse(cls, server_key):
        return cls.server_query(server_key).order(-cls.last_login_timestamp)

    @classmethod
    def query_by_username(cls, server_key):
        return cls.server_query(server_key).order(cls.username)

    @classmethod
    def lookup(cls, server_key, username):
        key = None
        if username is not None:
            key = ndb.Key(cls, username, parent=server_key)
        return key.get() if key is not None else None


@ae_ndb_serializer
class Location(ndb.Model):
    x = ndb.FloatProperty()
    y = ndb.FloatProperty()
    z = ndb.FloatProperty()


class UsernameModel(ServerModel):
    username = ndb.StringProperty()

    @property
    def user(self):
        return User.lookup(username=self.username)

    @property
    def player(self):
        return Player.lookup(self.server_key, self.username)

    def is_user(self, user):
        return user.is_username(self.username) if user is not None else False


@ae_ndb_serializer
class LogLine(UsernameModel):
    line = ndb.StringProperty(required=True)
    zone = ndb.StringProperty(required=True)
    timestamp = ndb.DateTimeProperty()
    has_timestamp = ndb.ComputedProperty(lambda self: self.timestamp is not None)
    log_level = ndb.StringProperty()
    ip = ndb.StringProperty()
    port = ndb.StringProperty()
    location = ndb.StructuredProperty(Location)
    chat = ndb.StringProperty()
    death_message = ndb.StringProperty()
    username_mob = ndb.StringProperty()
    weapon = ndb.StringProperty()
    code = ndb.StringProperty()
    achievement = ndb.StringProperty()
    achievement_message = ndb.StringProperty()
    tags = ndb.StringProperty(repeated=True)
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    def _pre_put_hook(self):
        if not self.tags:
            self.tags = [UNKNOWN_TAG]
        if TIMESTAMP_TAG not in self.tags and self.timestamp is not None:
            self.tags.insert(0, TIMESTAMP_TAG)

    def _post_put_hook(self, future):
        if Player.is_valid_username(self.username):
            Player.get_or_create(self.server_key, self.username)
        search.add_log_lines([self])
        self.send_message()

    def send_message(self):
        tags_set = set(self.tags)
        tags = list(tags_set.intersection(CHANNEL_TAGS_SET))
        if tags:
            ServerChannels.send_message(self, tags[0])

    @property
    def timezone(self):
        return name_to_timezone(self.zone)

    @property
    def timestamp_sse(self):
        return seconds_since_epoch(self.timestamp)

    @classmethod
    def _post_delete_hook(cls, key, future):
        search.remove_log_line(key)

    @classmethod
    def create(cls, server, line, zone, **kwargs):
        stripped_line = strip_control_codes(line)
        tz = name_to_timezone(zone)
        zone = tz.zone
        kwargs['tags'] = [UNKNOWN_TAG]
        for regexes, tags in REGEX_TAGS:
            match = None
            for regex in regexes:
                match = re.match(regex, line)
                if match:
                    gd = match.groupdict()
                    d = gd.pop('date', None)
                    t = gd.pop('time', None)
                    if d and t:
                        dts = "{0} {1}".format(d, t)
                        kwargs['timestamp'] = dts_to_naive_utc(dts, tz)
                    location_x = gd.pop('location_x', None)
                    location_y = gd.pop('location_y', None)
                    location_z = gd.pop('location_z', None)
                    if location_x and location_y and location_z:
                        kwargs['location'] = Location(
                            x=safe_float_from_string(location_x),
                            y=safe_float_from_string(location_y),
                            z=safe_float_from_string(location_z)
                        )
                    username = gd.pop('username', None)
                    if username:
                        username = strip_control_codes(username)
                        kwargs['username'] = username
                    username_mob = gd.pop('username_mob', None)
                    if username_mob:
                        username_mob = strip_control_codes(username_mob)
                        kwargs['username_mob'] = username_mob
                    kwargs.update(gd)
                    kwargs['tags'] = tags
                    if DEATH_TAG in tags:
                        username = kwargs['username']
                        i = stripped_line.find(username) + len(username) + 1
                        kwargs['death_message'] = stripped_line[i:]
                    if ACHIEVEMENT_TAG in tags:
                        username = kwargs['username']
                        i = stripped_line.find(username) + len(username) + 1
                        kwargs['achievement_message'] = stripped_line[i:]
                    break
            if match:
                break
        server.update_version(kwargs.pop('server_version', None))
        log_line = cls(parent=server.key, line=line, zone=zone, **kwargs)
        log_line.put()
        if LOGIN_TAG in log_line.tags:
            PlaySession.create(log_line.server_key, log_line.username, log_line.timestamp, zone, log_line.key)
        if LOGOUT_TAG in log_line.tags:
            PlaySession.close_current(log_line.server_key, log_line.username, log_line.timestamp, log_line.key)
        if STARTING_TAG in log_line.tags or STOPPING_TAG in log_line.tags:
            PlaySession.close_all_current(server.key, log_line.timestamp, log_line.key)
            if STARTING_TAG in log_line.tags:
                server.update_status(SERVER_HAS_STARTED)
            if STOPPING_TAG in log_line.tags:
                server.update_status(SERVER_HAS_STOPPED)
        return log_line

    @classmethod
    def lookup_line(cls, server_key, line):
        return cls.server_query(server_key).filter(cls.line == line).get()

    @classmethod
    def query_latest(cls, server_key):
        return cls.server_query(server_key).order(-cls.created)

    @classmethod
    def get_last_line(cls, server_key):
        return cls.query_latest(server_key).get()

    @classmethod
    def query_latest_with_timestamp(cls, server_key):
        return cls.server_query(server_key).filter(cls.has_timestamp == True).order(-cls.timestamp)  # noqa

    @classmethod
    def get_last_line_with_timestamp(cls, server_key):
        return cls.query_latest_with_timestamp(server_key).get()

    @classmethod
    def query_latest_username(cls, server_key, username):
        return cls.query_latest_with_timestamp(server_key).filter(cls.username == username)

    @classmethod
    def query_by_tags(cls, server_key, tags):
        return cls.server_query(server_key).filter(cls.tags == tags)

    @classmethod
    def query_latest_chats(cls, server_key):
        return cls.query_by_tags(server_key, CHAT_TAG).order(-cls.timestamp)

    @classmethod
    def query_oldest_chats(cls, server_key):
        return cls.query_by_tags(server_key, CHAT_TAG).order(cls.timestamp)

    @classmethod
    def query_latest_logins(cls, server_key):
        return cls.query_by_tags(server_key, LOGIN_TAG).order(-cls.timestamp)

    @classmethod
    def query_oldest_logins(cls, server_key):
        return cls.query_by_tags(server_key, LOGIN_TAG).order(cls.timestamp)

    @classmethod
    def query_latest_logouts(cls, server_key):
        return cls.query_by_tags(server_key, LOGOUT_TAG).order(-cls.timestamp)

    @classmethod
    def query_oldest_logouts(cls, server_key):
        return cls.query_by_tags(server_key, LOGOUT_TAG).order(cls.timestamp)

    @classmethod
    def query_latest_events(cls, server_key):
        return cls.server_query(server_key).filter(
            cls.tags.IN([CHAT_TAG, LOGIN_TAG, LOGOUT_TAG, DEATH_TAG, ACHIEVEMENT_TAG])
        ).order(-cls.timestamp, cls.key)

    @classmethod
    def query_oldest_events(cls, server_key):
        return cls.server_query(server_key).filter(
            cls.tags.IN([CHAT_TAG, LOGIN_TAG, LOGOUT_TAG, DEATH_TAG, ACHIEVEMENT_TAG])
        ).order(cls.timestamp, cls.key)

    @classmethod
    def query_api(cls, server_key, username=None, tag=None, since=None, before=None):
        query = cls.query_latest_with_timestamp(server_key)
        if username:
            query = query.filter(cls.username == username)
        if tag:
            query = query.filter(cls.tags == tag)
        if since:
            query = query.filter(cls.timestamp >= since)
        if before:
            query = query.filter(cls.timestamp < before)
        return query

    @classmethod
    def search_api(cls, server_key, q, size=None, username=None, tag=None, since=None, before=None, cursor=None):
        query_string = u"{0}".format(q)
        if username is not None:
            query_string = u"{0} username:{1}".format(query_string, username)
        if tag is not None:
            query_string = u"{0} tags:{1}".format(query_string, tag)
        if since is not None:
            query_string = u"{0} timestamp_sse >= {1}".format(query_string, seconds_since_epoch(since))
        if before is not None:
            query_string = u"{0} timestamp_sse < {1}".format(query_string, seconds_since_epoch(before))
        results, _, next_cursor = search.search_log_lines(
            query_string, server_key=server_key, limit=size or 50, cursor=cursor
        )
        return results, next_cursor if next_cursor else None


@ae_ndb_serializer
class Command(UsernameModel):
    command = ndb.StringProperty(required=True)
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @property
    def to_dict(self):
        return {'username': self.username, 'command': self.command}

    @classmethod
    def push(cls, server_key, username, command, **kwargs):
        instance = cls(
            parent=server_key,
            username=username,
            command=command,
            **kwargs
        )
        instance.put()
        return instance

    @classmethod
    @ndb.transactional
    def pop_all(cls, server_key):
        commands = []
        query = cls.server_query(server_key).order(cls.created)
        for command in query:
            commands.append(command.to_dict)
            command.key.delete()
        return commands


@ae_ndb_serializer
class PlaySession(UsernameModel):
    login_timestamp = ndb.DateTimeProperty(required=True)
    logout_timestamp = ndb.DateTimeProperty()
    zone = ndb.StringProperty(required=True)
    login_log_line_key = ndb.KeyProperty(kind=LogLine)
    logout_log_line_key = ndb.KeyProperty(kind=LogLine)
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @property
    def duration(self):
        login_timestamp = self.login_timestamp or datetime.datetime.utcnow()
        logout_timestamp = self.logout_timestamp or datetime.datetime.utcnow()
        return logout_timestamp - login_timestamp

    def close(self, timestamp, logout_log_line_key=None):
        self.logout_timestamp = timestamp
        self.logout_log_line_key = logout_log_line_key
        self.put()

    @classmethod
    @ndb.transactional
    def create(cls, server_key, username, timestamp, zone, login_log_line_key, **kwargs):
        current = cls.current(server_key, username)
        if current:
            current.close(timestamp, login_log_line_key)
        session = cls(
            parent=server_key,
            username=username,
            login_timestamp=timestamp,
            zone=zone,
            login_log_line_key=login_log_line_key,
            **kwargs
        )
        session.put()
        server = server_key.get()
        if server.idle:
            server.idle = None
            server.put()
        player = Player.get_or_create(session.server_key, username)
        player.last_login_timestamp = timestamp
        player.put()
        return session

    @classmethod
    def close_current(cls, server_key, username, timestamp, logout_log_line_key):
        current = cls.current(server_key, username)
        if current:
            current.close(timestamp, logout_log_line_key)
        return current

    @classmethod
    def close_all_current(cls, server_key, timestamp, logout_log_line_key=None):
        open_sessions_query = cls.query_open(server_key)
        for session in open_sessions_query:
            session.close(timestamp, logout_log_line_key=logout_log_line_key)

    @classmethod
    def query_open(cls, server_key):
        return cls.server_query(server_key).filter(cls.logout_timestamp == None)  # noqa

    @classmethod
    def query_latest_open(cls, server_key):
        return cls.query_open(server_key).order(-cls.login_timestamp)

    @classmethod
    def query_current(cls, server_key, username):
        return cls.query_open(server_key).filter(cls.username == username)

    @classmethod
    def current(cls, server_key, username):
        return cls.query_current(server_key, username).get()

    @classmethod
    def last(cls, server_key, username):
        return cls.query_latest(server_key, username=username).get()

    @classmethod
    def query_latest(cls, server_key, username=None, since=None, before=None):
        query = cls.server_query(server_key).order(-cls.login_timestamp)
        if username:
            query = query.filter(cls.username == username)
        if since:
            query = query.filter(cls.login_timestamp >= since)
        if before:
            query = query.filter(cls.login_timestamp < before)
        return query

    @classmethod
    def query_oldest(cls, server_key, username=None):
        query = cls.server_query(server_key).order(cls.login_timestamp)
        if username:
            query = query.filter(cls.username == username)
        return query


class GaussianBlurFilter(ImageFilter.Filter):
    name = "GaussianBlur"

    def __init__(self, radius=10):
        self.radius = radius

    def filter(self, image):
        return image.gaussian_blur(self.radius)


@ae_ndb_serializer
class ScreenShot(NdbImage, ServerModel):
    user_key = ndb.KeyProperty()
    random_id = ndb.FloatProperty()
    blurred_image_key = ndb.KeyProperty(kind=NdbImage)
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def _pre_delete_hook(cls, key):
        super(ScreenShot, cls)._pre_delete_hook(key)
        instance = key.get()
        blurred_image = instance.blurred_image
        if blurred_image is not None:
            blurred_image.key.delete()

    @property
    def user(self):
        return self.user_key.get() if self.user_key is not None else None

    @property
    def blurred_image(self):
        return self.blurred_image_key.get() if self.blurred_image_key else None

    @property
    def blurred_image_serving_url(self):
        blurred_image = self.blurred_image
        if blurred_image is not None:
            return blurred_image.get_serving_url()
        return None

    def generate_blurred_image_data(self):
        blob_reader = blobstore.BlobReader(self.blob_key)
        pil_image = Image.open(blob_reader)
        screenshot_filter = GaussianBlurFilter()
        pil_image = pil_image.filter(screenshot_filter)
        output = StringIO()
        pil_image.save(output, format="png")
        pil_image_data = output.getvalue()
        output.close()
        return pil_image_data

    def create_blurred(self):
        f = self.filename
        filename = "{0}_blur.png".format(f[:f.rfind('.') if f.rfind('.') != -1 else len(f)])
        blurred_image = NdbImage.create(
            parent=self.key, data=self.generate_blurred_image_data(), filename=filename, mime_type='image/png'
        )
        if self.blurred_image_key:
            self.blurred_image_key.delete()
        self.blurred_image_key = blurred_image.key
        self.put()

    @classmethod
    def create(cls, server_key, user, **kwargs):
        instance = super(ScreenShot, cls).create(parent=server_key, **kwargs)
        instance.user_key = user.key if user else None
        instance.username = user.get_server_username(server_key) if user else None
        instance.random_id = random.random()
        instance.put()
        taskqueue.add(url='/screenshots/{0}/create_blur'.format(instance.key.urlsafe()))
        return instance

    @classmethod
    def background(cls, server_key):
        namespace = "server-background"
        key = server_key.urlsafe()
        bg_key_str = memcache.get(key, namespace=namespace)
        if bg_key_str is not None:
            bg_key = ndb.Key(urlsafe=bg_key_str)
            return bg_key.get()
        else:
            bg = cls.random(server_key)
            if bg is not None:
                memcache.add(key, bg.key.urlsafe(), time=60, namespace=namespace)
            return bg

    @classmethod
    def random(cls, server_key):
        count = ScreenShot.server_query(server_key).count(keys_only=True, limit=101)
        if not count:
            return None
        # Small enough for offset?
        if count <= 100:
            offset = random.randrange(count)
            screenshot = ScreenShot.server_query(server_key).order(cls.random_id).get(offset=offset)
        else:  # Use statistics
            screenshot = ScreenShot.server_query(server_key).filter(
                cls.random_id > random.random()
            ).order(cls.random_id).get()
            if screenshot is None:
                screenshot = ScreenShot.server_query(server_key).order(cls.random_id).get()
        return screenshot

    @classmethod
    def query_latest(cls, server_key, user_key=None, since=None, before=None):
        query = cls.server_query(server_key).order(-cls.created)
        if user_key:
            query = query.filter(cls.user_key == user_key)
        if since:
            query = query.filter(cls.created >= since)
        if before:
            query = query.filter(cls.created < before)
        return query

    @classmethod
    def query_oldest(cls, server_key):
        return cls.server_query(server_key).order(cls.created)

    @classmethod
    def query_by_user_key(cls, user_key):
        return cls.query().order(cls.created)
