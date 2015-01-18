import fix_path  # noqa

import datetime
from functools import wraps
import json
import logging

from google.appengine.ext import ndb

import pytz

import webapp2

from wtforms import form, fields, validators, ValidationError

from restler.serializers import json_response as restler_json_response
from restler.serializers import ModelStrategy

from forms import RestfulStringField, RestfulBooleanField, RestfulSelectField, UniquePort
from models import Server, MinecraftProperties, MinecraftDownload, User, Player, PlaySession
from models import LogLine, Command, ScreenShot
from models import CHAT_TAG, DEATH_TAG, ACHIEVEMENT_TAG
from models import SERVER_UNKNOWN, SERVER_RUNNING, SERVER_STOPPED, SERVER_QUEUED_START, SERVER_QUEUED_STOP
from models import SERVER_LOADING, SERVER_LOADED, SERVER_SAVING, SERVER_SAVED
from server_queue import START_EVENT, STOP_EVENT
from oauth import Client, authenticate_agent_oauth_required, authenticate_controller_oauth_required
from oauth import authenticate_user_required, authenticate_admin_required
from user_auth import authentication_required


def validate_params(form_class):
    def decorator(request_method):
        @wraps(request_method)
        def wrapped(handler, *args, **kwargs):
            valid = False
            form = None
            request = handler.request
            while True:
                try:
                    if request.headers.get('Content-Type', '').startswith('application/json'):
                        json_params = json.loads(request.body)
                        form = form_class(data=json_params)
                    else:
                        form = form_class(formdata=request.params)
                    valid = form.validate()
                except Exception, e:
                    errors = u"Unhandled form parsing exception: {0}".format(e)
                    handler.json_response({}, status_code=400, errors=errors)
                    logging.error(errors)
                    try:
                        logging.error(handler.request)
                    except Exception, e:
                        logging.error(u"Can't log the request: {0}".format(e))
                if valid:
                    handler.request.form = form
                    request_method(handler, *args, **kwargs)
                    return
                else:
                    try:
                        message = form.errors
                    except:
                        message = u"Exception creating Form"
                    handler.json_response({}, status_code=400, errors=message)
                    logging.error(message)
                    return
        return wrapped
    return decorator


def boolean_input_required(form, field):
    if field.data is None and field.object_data is None:
        raise ValidationError(field.gettext('This field is required.'))


class JsonHandler(webapp2.RequestHandler):
    def _setup_context(self, context):
        if not context:
            context = {}
        context['request'] = self.request
        return context

    def _setup_data(self, model_or_query, errors=None):
        data = dict()
        if errors is not None:
            data['errors'] = errors
        else:
            data = model_or_query
        return data

    def json_response(self, model_or_query, strategy=None, status_code=200, errors=None, context=None):
        context = self._setup_context(context)
        data = self._setup_data(model_or_query, errors=errors)
        return restler_json_response(self.response, data, strategy=strategy, status_code=status_code, context=context)

    def handle_exception(self, exception, debug_mode):
        errors = exception.message or str(exception)
        if isinstance(exception, webapp2.HTTPException):
            code = exception.code
            if code == 404:
                super(JsonHandler, self).handle_exception(exception, debug_mode)
        else:
            code = 500
            logging.error(errors)
        self.json_response({}, status_code=code, errors=errors)


class PingForm(form.Form):
    server_name = fields.StringField(validators=[validators.DataRequired(), validators.Length(max=500)])
    is_server_running = RestfulBooleanField(validators=[validators.Optional()])
    server_day = fields.IntegerField(validators=[validators.Optional()])
    server_time = fields.IntegerField(validators=[validators.Optional()])
    is_raining = RestfulBooleanField(validators=[validators.Optional()])
    is_thundering = RestfulBooleanField(validators=[validators.Optional()])
    num_overloads = fields.IntegerField(validators=[validators.Optional()])
    ms_behind = fields.IntegerField(validators=[validators.Optional()])
    skipped_ticks = fields.IntegerField(validators=[validators.Optional()])
    address = RestfulStringField(validators=[validators.Optional()])
    timestamp = fields.DateTimeField(validators=[validators.Optional()])


class PingHandler(JsonHandler):
    @authentication_required(authenticate=authenticate_agent_oauth_required, request_property_name='authentication')
    @validate_params(form_class=PingForm)
    def post(self):
        form = self.request.form
        is_server_running = form.is_server_running.data
        server_day = form.server_day.data
        server_time = form.server_time.data
        is_raining = form.is_raining.data
        is_thundering = form.is_thundering.data
        num_overloads = form.num_overloads.data
        ms_behind = form.ms_behind.data
        skipped_ticks = form.skipped_ticks.data
        address = form.address.data
        timestamp = form.timestamp.data
        client = Client.get_by_client_id(self.request.authentication.client_id)
        server = client.server
        if not server.active:
            self.abort(404)
        status = SERVER_UNKNOWN
        if is_server_running:
            status = SERVER_RUNNING
        elif is_server_running is False:
            status = SERVER_STOPPED
        server.update_status(
            status=status,
            last_ping=datetime.datetime.utcnow(),
            server_day=server_day,
            server_time=server_time,
            is_raining=is_raining,
            is_thundering=is_thundering,
            num_overloads=num_overloads,
            ms_behind=ms_behind,
            skipped_ticks=skipped_ticks,
            address=address,
            timestamp=timestamp
        )
        commands = []
        if is_server_running:
            commands = Command.pop_all(server.key)
        response = {
            'commands': commands
        }
        self.json_response(response, status_code=200)


class LogLineForm(form.Form):
    line = fields.StringField(validators=[validators.DataRequired()])
    zone = fields.StringField(validators=[validators.DataRequired()])


class LogLineHandler(JsonHandler):
    @authentication_required(authenticate=authenticate_agent_oauth_required, request_property_name='authentication')
    @validate_params(form_class=LogLineForm)
    def post(self):
        client = Client.get_by_client_id(self.request.authentication.client_id)
        server = client.server
        if not server.active:
            self.abort(404)
        status_code = 200
        line = self.request.form.line.data
        zone = self.request.form.zone.data
        existing_line = LogLine.lookup_line(server.key, line)
        if existing_line is None:
            log_line = LogLine.create(server, line, zone)
            if log_line is not None:
                status_code = 201
        self.json_response({}, status_code=status_code)


class LastLineHandler(JsonHandler):
    @authentication_required(authenticate=authenticate_agent_oauth_required, request_property_name='authentication')
    def get(self):
        client = Client.get_by_client_id(self.request.authentication.client_id)
        server = client.server
        if not server.active:
            self.abort(404)
        last_log_line = LogLine.get_last_line_with_timestamp(server.key)
        response = {
            'lastline': last_log_line.line if last_log_line is not None else None,
        }
        self.json_response(response, status_code=200)


class EventForm(form.Form):
    server_key = fields.StringField(validators=[validators.DataRequired()])
    event = fields.StringField(validators=[validators.DataRequired()])
    completed = fields.IntegerField(validators=[validators.Optional()])


class EventHandler(JsonHandler):
    @authentication_required(authenticate=authenticate_controller_oauth_required, request_property_name='authentication')  # noqa
    @validate_params(form_class=EventForm)
    def post(self):
        client = Client.get_by_client_id(self.request.authentication.client_id)
        instance = client.instance
        if instance is not None:
            form = self.request.form
            try:
                server_key = ndb.Key(urlsafe=form.server_key.data)
                server = server_key.get()
            except Exception:
                server = None
            if server:
                event = form.event.data
                completed = form.completed.data
                status = None
                if event == START_EVENT:
                    if completed < 100:
                        status = SERVER_LOADING
                    else:
                        status = SERVER_LOADED
                if event == STOP_EVENT:
                    if completed < 100:
                        status = SERVER_SAVING
                    else:
                        status = SERVER_SAVED
                if status:
                    server.update_status(status=status, completed=completed)
        response = {}
        self.json_response(response, status_code=200)


def api_datetime(dt, zone=None, dt_format=u"%Y-%m-%d %H:%M:%S", tz_format=u"%Z%z"):
    if dt:
        utc_dt = pytz.UTC.localize(dt)
        if zone:
            try:
                tz = pytz.timezone(zone)
            except:
                tz = pytz.utc
        else:
            tz = pytz.utc
        tz_dt = utc_dt.astimezone(tz) if utc_dt else None
        dt_tz_format = "{0} {1}".format(dt_format, tz_format) if tz_format else dt_format
        return tz_dt.strftime(dt_tz_format) if tz_dt else utc_dt.strftime(dt_format)
    return None


class MultiPageForm(form.Form):
    size = fields.IntegerField(default=10, validators=[validators.NumberRange(min=1, max=50)])
    cursor = fields.StringField(validators=[validators.Optional()])


class MultiPage():
    @property
    def size(self):
        return self.request.form.size.data or self.request.form.size.default

    @property
    def cursor(self):
        cursor = self.request.form.cursor.data
        if cursor:
            try:
                cursor = ndb.Cursor.from_websafe_string(cursor)
            except Exception, e:
                self.abort(400, {'cursor': e.message})
        return cursor or None

    def fetch_page(self, query, results_name='results'):
        results, cursor, more = query.fetch_page(self.size, start_cursor=self.cursor)
        response = {results_name: results}
        if more:
            response['cursor'] = cursor.to_websafe_string()
        return response


class MultiPageJsonHandler(JsonHandler, MultiPage):
    pass


USER_FIELDS = ['active', 'admin', 'email', 'nickname', 'usernames']
USER_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'last_coal_login': lambda o: api_datetime(o.last_login),
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
USER_STRATEGY = ModelStrategy(User).include(*USER_FIELDS).include(**USER_FIELD_FUNCTIONS)


class UsersHandler(MultiPageJsonHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=MultiPageForm)
    def get(self):
        self.json_response(self.fetch_page(User.query_all(), results_name='users'), USER_STRATEGY)


class UserKeyHandler(JsonHandler):
    def get_user_by_key(self, key, abort=True):
        fail_code = 404
        if key == 'self':
            fail_code = 403
            user = self.request.user
        else:
            try:
                user_key = ndb.Key(urlsafe=key)
                user = user_key.get()
            except Exception:
                user = None
        if abort and not user:
            self.abort(fail_code)
        return user

    @authentication_required(authenticate=authenticate_user_required)
    def get(self, key):
        user = self.get_user_by_key(key)
        self.json_response(user, USER_STRATEGY)


SERVER_FIELDS = [
    'name', 'short_name', 'address', 'running_version', 'status',
    'server_day', 'server_time', 'is_raining', 'is_thundering'
]
SERVER_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'gce': lambda o: o.is_gce,
    'last_ping': lambda o: api_datetime(o.last_ping),
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
SERVER_STRATEGY = ModelStrategy(Server).include(*SERVER_FIELDS).include(**SERVER_FIELD_FUNCTIONS)


class ServerForm(form.Form):
    name = fields.StringField(validators=[validators.DataRequired()])


class CreateServerForm(ServerForm):
    gce = RestfulBooleanField(validators=[boolean_input_required])


class ServersHandler(MultiPageJsonHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=MultiPageForm)
    def get(self):
        self.json_response(self.fetch_page(Server.query_all(), results_name='servers'), SERVER_STRATEGY)

    @authentication_required(authenticate=authenticate_admin_required)
    @validate_params(form_class=CreateServerForm)
    def post(self):
        server = Server.create(name=self.request.form.name.data, is_gce=self.request.form.gce.data)
        self.json_response(server, SERVER_STRATEGY, status_code=201)


class ServerBaseHandler(JsonHandler):
    def get_server_by_key(self, key, abort=True):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is not None and not server.active:
                server = None
        except Exception:
            server = None
        if abort and not server:
            self.abort(404)
        return server


class ServerKeyHandler(ServerBaseHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, key):
        self.json_response(self.get_server_by_key(key), SERVER_STRATEGY)

    @authentication_required(authenticate=authenticate_admin_required)
    @validate_params(form_class=ServerForm)
    def post(self, key):
        server = self.get_server_by_key(key)
        server.name = self.request.form.name.data
        server.put()
        self.json_response(server, SERVER_STRATEGY, status_code=200)


SERVER_PROPERTIES_FIELDS = [
    'server_port', 'motd', 'white_list', 'gamemode', 'force_gamemode', 'level_type', 'level_seed', 'generator_settings',
    'difficulty', 'pvp', 'hardcore', 'allow_flight', 'allow_nether', 'max_build_height', 'generate_structures',
    'spawn_npcs', 'spawn_animals', 'spawn_monsters', 'view_distance', 'player_idle_timeout', 'max_players',
    'max_world_size', 'spawn_protection', 'enable_command_block', 'snooper_enabled', 'resource_pack',
    'op_permission_level'
]
SERVER_PROPERTIES_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.parent().urlsafe(),
    'version': lambda o: o.server.version,
    'memory': lambda o: o.server.memory,
    'operator': lambda o: o.server.operator,
    'idle_timeout': lambda o: o.server.idle_timeout
}
SERVER_PROPERTIES_STRATEGY = ModelStrategy(MinecraftProperties).include(*SERVER_PROPERTIES_FIELDS).include(**SERVER_PROPERTIES_FIELD_FUNCTIONS)  # noqa


class ServerPropertiesForm(form.Form):
    server_port = fields.IntegerField(
        validators=[validators.Optional(), validators.NumberRange(min=25565, max=25575), UniquePort()]
    )
    version = RestfulSelectField(validators=[validators.Optional()])
    memory = RestfulSelectField(
        validators=[validators.Optional()],
        choices=[
            ('256M', '256 Megabytes'),
            ('512M', '512 Megabytes'),
            ('1G', '1 Gigabyte'),
            ('2G', '2 Gigabytes'),
            ('3G', '3 Gigabytes'),
            ('4G', '4 Gigabytes')

        ]
    )
    operator = RestfulStringField(validators=[validators.Optional()])
    idle_timeout = fields.IntegerField(validators=[validators.Optional(), validators.NumberRange(min=0, max=60)])
    motd = RestfulStringField(validators=[validators.Optional()])
    white_list = RestfulBooleanField(validators=[validators.Optional()])
    gamemode = RestfulSelectField(
        validators=[validators.Optional()],
        choices=[
            ('0', 'Survival'),
            ('1', 'Creative'),
            ('2', 'Adventure')
        ]
    )
    force_gamemode = RestfulBooleanField(validators=[validators.Optional()])
    level_type = RestfulSelectField(
        validators=[validators.Optional()],
        choices=[
            ('DEFAULT', 'Default: Standard world with hills, valleys, water, etc.'),
            ('FLAT', 'Flat: A flat world with no features, meant for building.'),
            ('LARGEBIOMES', 'Large Biomes: Same as default but all biomes are larger.'),
            ('AMPLIFIED', 'Amplified: Same as default but world-generation height limit is increased.')
        ]
    )
    level_seed = RestfulStringField(validators=[validators.Optional()])
    generator_settings = RestfulStringField(validators=[validators.Optional()])
    difficulty = RestfulSelectField(
        validators=[validators.Optional()],
        choices=[
            ('0', 'Peaceful'),
            ('1', 'Easy'),
            ('2', 'Normal'),
            ('3', 'Hard')
        ]
    )
    pvp = RestfulBooleanField(validators=[validators.Optional()])
    hardcore = RestfulBooleanField(validators=[validators.Optional()])
    allow_flight = RestfulBooleanField(validators=[validators.Optional()])
    allow_nether = RestfulBooleanField(validators=[validators.Optional()])
    max_build_height = fields.IntegerField(validators=[validators.Optional(), validators.NumberRange(min=0, max=1024)])
    generate_structures = RestfulBooleanField(validators=[validators.Optional()])
    spawn_npcs = RestfulBooleanField(validators=[validators.Optional()])
    spawn_animals = RestfulBooleanField(validators=[validators.Optional()])
    spawn_monsters = RestfulBooleanField(validators=[validators.Optional()])
    view_distance = fields.IntegerField(validators=[validators.Optional(), validators.NumberRange(min=3, max=15)])
    player_idle_timeout = fields.IntegerField(validators=[validators.Optional(), validators.NumberRange(min=0, max=60)])
    max_players = fields.IntegerField(validators=[validators.Optional(), validators.NumberRange(min=0, max=10000)])
    max_world_size = fields.IntegerField(validators=[validators.Optional(), validators.NumberRange(min=1, max=29999984)])  # noqa
    spawn_protection = fields.IntegerField(validators=[validators.Optional(), validators.NumberRange(min=0, max=64)])
    enable_command_block = RestfulBooleanField(validators=[validators.Optional()])
    snooper_enabled = RestfulBooleanField(validators=[validators.Optional()])
    resource_pack = RestfulStringField(validators=[validators.Optional()])
    op_permission_level = RestfulSelectField(
        validators=[validators.Optional()],
        choices=[
            ('1', 'Can bypass spawn protection'),
            ('2', 'Can use /clear, /difficulty, /effect, /gamemode, /gamerule, /give, and /tp, and can edit command blocks'),  # noqa
            ('3', 'Can use /ban, /deop, /kick, and /op')
        ]
    )

    def __init__(self, server=None, *args, **kwargs):
        super(ServerPropertiesForm, self).__init__(*args, **kwargs)
        self.server = server
        self.version.choices = [
            (d.version, d.version) for d in MinecraftDownload.query_all()
        ]


class ServerPropertiesHander(ServerBaseHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, key):
        server = self.get_server_by_key(key)
        if not server.is_gce:
            self.abort(404)
        self.json_response(server.mc_properties, SERVER_PROPERTIES_STRATEGY)

    @authentication_required(authenticate=authenticate_admin_required)
    def post(self, key):
        server = self.get_server_by_key(key)
        if not server.is_gce:
            self.abort(404)
        valid = False
        try:
            self.request.form = ServerPropertiesForm(formdata=self.request.params, server=server)
            valid = self.request.form.validate()
        except Exception, e:
            errors = u"Unhandled form parsing exception: {0}".format(e)
            self.json_response({}, status_code=400, errors=errors)
            logging.error(errors)
            try:
                logging.error(self.request)
            except Exception, e:
                logging.error(u"Can't log the request: {0}".format(e))
        if valid:
            server_put = properties_put = False
            server = self.get_server_by_key(key)
            if not server.is_gce:
                self.abort(404)
            server_properties = server.mc_properties
            for prop in self.request.form:
                if prop.name == 'server_port':
                    if prop.data is not None:
                        setattr(server_properties, prop.name, int(prop.data))
                    else:
                        setattr(server_properties, prop.name, None)
                elif prop.data is not None:
                    if prop.name in ['version', 'memory', 'operator', 'idle_timeout']:
                        setattr(server, prop.name, prop.data)
                        server_put = True
                    elif prop.name in ['gamemode', 'difficulty', 'op_permission_level']:
                        setattr(server_properties, prop.name, int(prop.data))
                        properties_put = True
                    else:
                        setattr(server_properties, prop.name, prop.data)
                        properties_put = True
            if server_put:
                server.put()
            if properties_put:
                server_properties.put()
            self.json_response(server_properties, SERVER_PROPERTIES_STRATEGY, status_code=200)
            return
        else:
            try:
                message = form.errors
            except:
                message = u"Exception creating Form"
            self.json_response({}, status_code=400, errors=message)
            logging.error(message)
            return


class ServerPlayHandler(ServerBaseHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def post(self, key):
        server = self.get_server_by_key(key)
        if not server.is_gce:
            self.abort(404)
        status_code = 200
        if server.status not in [SERVER_RUNNING, SERVER_QUEUED_START]:
            server.start()
            status_code = 202
        self.response.set_status(status_code)


class ServerPauseHandler(ServerBaseHandler):
    @authentication_required(authenticate=authenticate_admin_required)
    def post(self, key):
        server = self.get_server_by_key(key)
        if not server.is_gce:
            self.abort(404)
        status_code = 200
        if server.status not in [SERVER_STOPPED, SERVER_QUEUED_STOP]:
            server.stop()
            status_code = 202
        self.response.set_status(status_code)


PLAYER_FIELDS = ['username', 'is_playing']
PLAYER_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'server_key': lambda o: o.server_key.urlsafe(),
    'user_key': lambda o: o.user.key.urlsafe() if o.user is not None else None,
    'last_login': lambda o: api_datetime(o.last_login_timestamp),
    'last_session_duration': lambda o: o.last_session_duration.total_seconds() if o.last_session_duration is not None else None  # noqa
}
PLAYER_STRATEGY = ModelStrategy(Player).include(*PLAYER_FIELDS).include(**PLAYER_FIELD_FUNCTIONS)


class ServerModelHandler(JsonHandler):
    def get_server(self, server_key, abort_404=True):
        try:
            server = ndb.Key(urlsafe=server_key).get()
            if server is not None and not server.active:
                server = None
        except Exception:
            server = None
        if abort_404 and server is None:
            self.abort(404)
        return server

    def get_player_by_key_or_username(self, server_key, key_username, abort_404=True):
        player = None
        try:
            player_key = ndb.Key(urlsafe=key_username)
            if server_key == player_key.parent():
                player = player_key.get()
        except Exception:
            player = Player.lookup(server_key, key_username)
        if abort_404 and not player:
            self.abort(404)
        return player

    def get_server_model_by_key(self, server_key, key, abort_404=True):
        instance = None
        try:
            instance_key = ndb.Key(urlsafe=key)
            if server_key == instance_key.parent():
                instance = instance_key.get()
        except Exception:
            instance = None
        if abort_404 and not instance:
            self.abort(404)
        return instance


class MultiPageServerModelHandler(ServerModelHandler, MultiPage):
    pass


class PlayersHandler(MultiPageServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=MultiPageForm)
    def get(self, server_key):
        server_key = self.get_server(server_key).key
        self.json_response(
            self.fetch_page(Player.query_by_username(server_key), results_name='players'),
            PLAYER_STRATEGY
        )


class PlayerKeyUsernameHandler(ServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, server_key, key_username):
        server_key = self.get_server(server_key).key
        player = self.get_player_by_key_or_username(server_key, key_username)
        self.json_response(player, PLAYER_STRATEGY)


PLAY_SESSION_FIELDS = ['username']
PLAY_SESSION_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'server_key': lambda o: o.server_key.urlsafe(),
    'player_key': lambda o: o.player.key.urlsafe() if o.player is not None else None,
    'user_key': lambda o: o.user.key.urlsafe() if o.user is not None else None,
    'login_timestamp': lambda o: api_datetime(o.login_timestamp),
    'logout_timestamp': lambda o: api_datetime(o.logout_timestamp),
    'duration': lambda o: o.duration.total_seconds(),
    'login_logline_key': lambda o: o.login_log_line_key.urlsafe() if o.login_log_line_key is not None else None,
    'logout_logline_key': lambda o: o.logout_log_line_key.urlsafe() if o.logout_log_line_key is not None else None,
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
PLAY_SESSION_STRATEGY = ModelStrategy(PlaySession).include(*PLAY_SESSION_FIELDS).include(**PLAY_SESSION_FIELD_FUNCTIONS)


class PlaySessionsForm(MultiPageForm):
    since = fields.DateTimeField(validators=[validators.Optional()])
    before = fields.DateTimeField(validators=[validators.Optional()])


class PlaySessionsHandler(MultiPageServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=PlaySessionsForm)
    def get(self, server_key, key_username=None):
        server_key = self.get_server(server_key).key
        username = None
        if key_username:
            player = self.get_player_by_key_or_username(server_key, key_username)
            username = player.username
        since = self.request.form.since.data or None
        before = self.request.form.before.data or None
        query = PlaySession.query_latest(server_key, username=username, since=since, before=before)
        self.json_response(self.fetch_page(query, results_name='sessions'), PLAY_SESSION_STRATEGY)


class PlaySessionKeyHandler(ServerModelHandler):
    def get_play_session_by_key(self, server_key, key, abort_404=True):
        play_session = None
        try:
            play_session_key = ndb.Key(urlsafe=key)
            if server_key == play_session_key.parent():
                play_session = play_session_key.get()
        except Exception:
            play_session = None
        if abort_404 and not play_session:
            self.abort(404)
        return play_session

    @authentication_required(authenticate=authenticate_user_required)
    def get(self, server_key, key):
        server_key = self.get_server(server_key).key
        play_session = self.get_play_session_by_key(server_key, key)
        self.json_response(play_session, PLAY_SESSION_STRATEGY)


CHAT_FIELDS = ['username', 'line', 'chat']
CHAT_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'server_key': lambda o: o.server_key.urlsafe(),
    'player_key': lambda o: o.player.key.urlsafe() if o.player is not None else None,
    'user_key': lambda o: o.user.key.urlsafe() if o.user is not None else None,
    'timestamp': lambda o: api_datetime(o.timestamp),
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
CHAT_STRATEGY = ModelStrategy(LogLine).include(*CHAT_FIELDS).include(**CHAT_FIELD_FUNCTIONS)


class ChatForm(MultiPageForm):
    q = fields.StringField(validators=[validators.Optional()])
    since = fields.DateTimeField(validators=[validators.Optional()])
    before = fields.DateTimeField(validators=[validators.Optional()])


class ChatPostForm(form.Form):
    chat = fields.StringField(validators=[validators.DataRequired()])


class ChatHandler(MultiPageServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=ChatForm)
    def get(self, server_key, key_username=None):
        server_key = self.get_server(server_key).key
        username = None
        if key_username:
            player = self.get_player_by_key_or_username(server_key, key_username)
            username = player.username
        since = self.request.form.since.data or None
        before = self.request.form.before.data or None
        q = self.request.form.q.data or None
        if q:
            query_string = u"chat:{0}".format(q)
            cursor = self.request.form.cursor.data or None
            results, next_cursor = LogLine.search_api(
                server_key,
                query_string,
                size=self.size,
                username=username,
                tag=CHAT_TAG,
                since=since,
                before=before,
                cursor=cursor
            )
            response = {'chats': results}
            if next_cursor is not None:
                results, _ = LogLine.search_api(
                    server_key,
                    query_string,
                    size=self.size,
                    username=username,
                    tag=CHAT_TAG,
                    since=since,
                    before=before,
                    cursor=next_cursor
                )
                if results:
                    response['cursor'] = next_cursor
            self.json_response(response, CHAT_STRATEGY)
        else:
            query = LogLine.query_api(server_key, username=username, tag=CHAT_TAG, since=since, before=before)
            self.json_response(self.fetch_page(query, results_name='chats'), CHAT_STRATEGY)

    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=ChatPostForm)
    def post(self, server_key, key_username=None):
        server_key = self.get_server(server_key).key
        username = self.request.user.get_server_play_name(server_key)
        if key_username:
            player = self.get_player_by_key_or_username(server_key, key_username)
            username = player.username
            if username not in self.request.user.usernames:
                self.abort(403)
        if username:
            chat = u"/say <{0}> {1}".format(username, self.request.form.chat.data)
        else:
            chat = u"/say {0}".format(self.request.form.chat.data)
        Command.push(server_key, username, chat)
        self.response.set_status(202)


class ChatKeyHandler(ServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, server_key, key):
        server_key = self.get_server(server_key).key
        log_line = self.get_server_model_by_key(server_key, key)
        if CHAT_TAG not in log_line.tags:
            self.abort(404)
        self.json_response(log_line, CHAT_STRATEGY)


DEATH_FIELDS = ['username', 'line']
DEATH_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'server_key': lambda o: o.server_key.urlsafe(),
    'message': lambda o: o.death_message,
    'player_key': lambda o: o.player.key.urlsafe() if o.player is not None else None,
    'user_key': lambda o: o.user.key.urlsafe() if o.user is not None else None,
    'timestamp': lambda o: api_datetime(o.timestamp),
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
DEATH_STRATEGY = ModelStrategy(LogLine).include(*DEATH_FIELDS).include(**DEATH_FIELD_FUNCTIONS)


class DeathForm(MultiPageForm):
    q = fields.StringField(validators=[validators.Optional()])
    since = fields.DateTimeField(validators=[validators.Optional()])
    before = fields.DateTimeField(validators=[validators.Optional()])


class DeathHandler(MultiPageServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=DeathForm)
    def get(self, server_key, key_username=None):
        server_key = self.get_server(server_key).key
        username = None
        if key_username:
            player = self.get_player_by_key_or_username(server_key, key_username)
            username = player.username
        since = self.request.form.since.data or None
        before = self.request.form.before.data or None
        q = self.request.form.q.data or None
        if q:
            query_string = u"death_message:{0}".format(q)
            cursor = self.request.form.cursor.data or None
            results, next_cursor = LogLine.search_api(
                server_key,
                query_string,
                size=self.size,
                username=username,
                tag=DEATH_TAG,
                since=since,
                before=before,
                cursor=cursor
            )
            response = {'deaths': results}
            if next_cursor is not None:
                results, _ = LogLine.search_api(
                    server_key,
                    query_string,
                    size=self.size,
                    username=username,
                    tag=DEATH_TAG,
                    since=since,
                    before=before,
                    cursor=next_cursor
                )
                if results:
                    response['cursor'] = next_cursor
            self.json_response(response, DEATH_STRATEGY)
        else:
            query = LogLine.query_api(server_key, username=username, tag=DEATH_TAG, since=since, before=before)
            self.json_response(self.fetch_page(query, results_name='deaths'), DEATH_STRATEGY)


class DeathKeyHandler(ServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, server_key, key):
        server_key = self.get_server(server_key).key
        log_line = self.get_server_model_by_key(server_key, key)
        if DEATH_TAG not in log_line.tags:
            self.abort(404)
        self.json_response(log_line, DEATH_STRATEGY)


ACHIEVEMENT_FIELDS = ['username', 'line']
ACHIEVEMENT_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'server_key': lambda o: o.server_key.urlsafe(),
    'name': lambda o: o.achievement,
    'message': lambda o: o.achievement_message,
    'player_key': lambda o: o.player.key.urlsafe() if o.player is not None else None,
    'user_key': lambda o: o.user.key.urlsafe() if o.user is not None else None,
    'timestamp': lambda o: api_datetime(o.timestamp),
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
ACHIEVEMENT_STRATEGY = ModelStrategy(LogLine).include(*ACHIEVEMENT_FIELDS).include(**ACHIEVEMENT_FIELD_FUNCTIONS)


class AchievementForm(MultiPageForm):
    q = fields.StringField(validators=[validators.Optional()])
    since = fields.DateTimeField(validators=[validators.Optional()])
    before = fields.DateTimeField(validators=[validators.Optional()])


class AchievementHandler(MultiPageServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=AchievementForm)
    def get(self, server_key, key_username=None):
        server_key = self.get_server(server_key).key
        username = None
        if key_username:
            player = self.get_player_by_key_or_username(server_key, key_username)
            username = player.username
        since = self.request.form.since.data or None
        before = self.request.form.before.data or None
        q = self.request.form.q.data or None
        if q:
            query_string = u"achievement:{0}".format(q)
            cursor = self.request.form.cursor.data or None
            results, next_cursor = LogLine.search_api(
                server_key,
                query_string,
                size=self.size,
                username=username,
                tag=ACHIEVEMENT_TAG,
                since=since,
                before=before,
                cursor=cursor
            )
            response = {'achievements': results}
            if next_cursor is not None:
                results, _ = LogLine.search_api(
                    server_key,
                    query_string,
                    size=self.size,
                    username=username,
                    tag=ACHIEVEMENT_TAG,
                    since=since,
                    before=before,
                    cursor=next_cursor
                )
                if results:
                    response['cursor'] = next_cursor
            self.json_response(response, ACHIEVEMENT_STRATEGY)
        else:
            query = LogLine.query_api(server_key, username=username, tag=ACHIEVEMENT_TAG, since=since, before=before)
            self.json_response(self.fetch_page(query, results_name='achievements'), ACHIEVEMENT_STRATEGY)


class AchievementKeyHandler(ServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, server_key, key):
        server_key = self.get_server(server_key).key
        log_line = self.get_server_model_by_key(server_key, key)
        if ACHIEVEMENT_TAG not in log_line.tags:
            self.abort(404)
        self.json_response(log_line, ACHIEVEMENT_STRATEGY)


LOG_LINE_FIELDS = ['username', 'line', 'log_level', 'ip', 'port', 'location', 'chat', 'tags']
LOG_LINE_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'server_key': lambda o: o.server_key.urlsafe(),
    'player_key': lambda o: o.player.key.urlsafe() if o.player is not None else None,
    'user_key': lambda o: o.user.key.urlsafe() if o.user is not None else None,
    'timestamp': lambda o: api_datetime(o.timestamp),
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
LOG_LINE_STRATEGY = ModelStrategy(LogLine).include(*LOG_LINE_FIELDS).include(**LOG_LINE_FIELD_FUNCTIONS)


class LogLineForm(MultiPageForm):
    q = fields.StringField(validators=[validators.Optional()])
    tag = fields.StringField(validators=[validators.Optional()])
    since = fields.DateTimeField(validators=[validators.Optional()])
    before = fields.DateTimeField(validators=[validators.Optional()])


class LogLinesHandler(MultiPageServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=LogLineForm)
    def get(self, server_key, key_username=None):
        server_key = self.get_server(server_key).key
        username = None
        if key_username:
            player = self.get_player_by_key_or_username(server_key, key_username)
            username = player.username
        since = self.request.form.since.data or None
        before = self.request.form.before.data or None
        q = self.request.form.q.data or None
        tag = self.request.form.tag.data or None
        if q:
            query_string = u"line:{0}".format(q)
            cursor = self.request.form.cursor.data or None
            results, next_cursor = LogLine.search_api(
                server_key,
                query_string,
                size=self.size,
                username=username,
                tag=tag, since=since,
                before=before,
                cursor=cursor
            )
            response = {'loglines': results}
            if next_cursor is not None:
                results, _ = LogLine.search_api(
                    server_key,
                    query_string,
                    size=self.size,
                    username=username,
                    tag=tag,
                    since=since,
                    before=before,
                    cursor=next_cursor
                )
                if results:
                    response['cursor'] = next_cursor
            self.json_response(response, LOG_LINE_STRATEGY)
        else:
            query = LogLine.query_api(server_key, username=username, tag=tag, since=since, before=before)
            self.json_response(self.fetch_page(query, results_name='loglines'), LOG_LINE_STRATEGY)


class LogLineKeyHandler(ServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, server_key, key):
        server_key = self.get_server(server_key).key
        log_line = self.get_server_model_by_key(server_key, key)
        self.json_response(log_line, LOG_LINE_STRATEGY)


SCREEN_SHOT_FIELDS = ['random_id']
SCREEN_SHOT_FIELD_FUNCTIONS = {
    'key': lambda o: o.key.urlsafe(),
    'server_key': lambda o: o.server_key.urlsafe(),
    'user_key': lambda o: o.user.key.urlsafe() if o.user is not None else None,
    'original_url': lambda o: o.get_serving_url(),
    'blurred_url': lambda o: o.blurred_image_serving_url,
    'created': lambda o: api_datetime(o.created),
    'updated': lambda o: api_datetime(o.updated)
}
SCREEN_SHOT_STRATEGY = ModelStrategy(ScreenShot).include(*SCREEN_SHOT_FIELDS).include(**SCREEN_SHOT_FIELD_FUNCTIONS)


class ScreenShotForm(MultiPageForm):
    since = fields.DateTimeField(validators=[validators.Optional()])
    before = fields.DateTimeField(validators=[validators.Optional()])


class ScreenShotsHandler(MultiPageServerModelHandler):
    def get_user_by_key(self, key, abort=True):
        fail_code = 404
        if key == 'self':
            fail_code = 403
            user = self.request.user
        else:
            try:
                user_key = ndb.Key(urlsafe=key)
                user = user_key.get()
            except Exception:
                user = None
        if abort and not user:
            self.abort(fail_code)
        return user

    @authentication_required(authenticate=authenticate_user_required)
    @validate_params(form_class=ScreenShotForm)
    def get(self, server_key, key=None):
        server_key = self.get_server(server_key).key
        user_key = None
        if key:
            user = self.get_user_by_key(key)
            user_key = user.key
        since = self.request.form.since.data or None
        before = self.request.form.before.data or None
        query = ScreenShot.query_latest(server_key, user_key=user_key, since=since, before=before)
        self.json_response(self.fetch_page(query, results_name='screenshots'), SCREEN_SHOT_STRATEGY)


class ScreenShotKeyHandler(ServerModelHandler):
    @authentication_required(authenticate=authenticate_user_required)
    def get(self, server_key, key):
        server_key = self.get_server(server_key).key
        screenshot = self.get_server_model_by_key(server_key, key)
        self.json_response(screenshot, SCREEN_SHOT_STRATEGY)


routes = [
    webapp2.Route('/api/v1/agents/ping', 'api.PingHandler', name='api_agents_ping'),
    webapp2.Route('/api/v1/agents/logline', 'api.LogLineHandler', name='api_agents_logline'),
    webapp2.Route('/api/v1/agents/lastline', 'api.LastLineHandler', name='api_agents_lastline'),

    webapp2.Route('/api/v1/controllers/event', 'api.EventHandler', name='api_controllers_event'),

    webapp2.Route('/api/v1/users/<key>', 'api.UserKeyHandler', name='api_data_user_key'),
    webapp2.Route('/api/v1/users', 'api.UsersHandler', name='api_data_users'),

    webapp2.Route('/api/v1/servers/<server_key>/players/<key_username>/sessions', 'api.PlaySessionsHandler', name='api_data_player_sessions'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/players/<key_username>/chats', 'api.ChatHandler', name='api_data_player_chats'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/players/<key_username>/deaths', 'api.DeathHandler', name='api_data_player_deaths'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/players/<key_username>/achievements', 'api.AchievementHandler', name='api_data_player_achievements'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/players/<key_username>/loglines', 'api.LogLinesHandler', name='api_data_player_loglines'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/players/<key_username>', 'api.PlayerKeyUsernameHandler', name='api_data_player_key_username'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/players', 'api.PlayersHandler', name='api_data_players'),

    webapp2.Route('/api/v1/servers/<server_key>/sessions/<key>', 'api.PlaySessionKeyHandler', name='api_data_session_key'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/sessions', 'api.PlaySessionsHandler', name='api_data_sessions'),

    webapp2.Route('/api/v1/servers/<server_key>/chats/<key>', 'api.ChatKeyHandler', name='api_data_chat_key'),
    webapp2.Route('/api/v1/servers/<server_key>/chats', 'api.ChatHandler', name='api_data_chats'),

    webapp2.Route('/api/v1/servers/<server_key>/deaths/<key>', 'api.DeathKeyHandler', name='api_data_death_key'),
    webapp2.Route('/api/v1/servers/<server_key>/deaths', 'api.DeathHandler', name='api_data_deaths'),

    webapp2.Route('/api/v1/servers/<server_key>/achievements/<key>', 'api.AchievementKeyHandler', name='api_data_achievement_key'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/achievements', 'api.AchievementHandler', name='api_data_achievements'),

    webapp2.Route('/api/v1/servers/<server_key>/loglines/<key>', 'api.LogLineKeyHandler', name='api_data_logline_key'),
    webapp2.Route('/api/v1/servers/<server_key>/loglines', 'api.LogLinesHandler', name='api_data_loglines'),

    webapp2.Route('/api/v1/servers/<server_key>/screenshots/<key>', 'api.ScreenShotKeyHandler', name='api_data_screenshot_key'),  # noqa
    webapp2.Route('/api/v1/servers/<server_key>/screenshots', 'api.ScreenShotsHandler', name='api_data_screenshots'),
    webapp2.Route('/api/v1/servers/<server_key>/users/<key>/screenshots', 'api.ScreenShotsHandler', name='api_data_user_screenshots'),  # noqa

    webapp2.Route('/api/v1/servers/<key>/properties', 'api.ServerPropertiesHander', name='api_data_server_properties'),
    webapp2.Route('/api/v1/servers/<key>/queue/play', 'api.ServerPlayHandler', name='api_data_server_play'),
    webapp2.Route('/api/v1/servers/<key>/queue/pause', 'api.ServerPauseHandler', name='api_data_server_pause'),

    webapp2.Route('/api/v1/servers/<key>', 'api.ServerKeyHandler', name='api_data_server_key'),
    webapp2.Route('/api/v1/servers', 'api.ServersHandler', name='api_data_servers')
]
