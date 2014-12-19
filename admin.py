import fix_path  # noqa

import logging
import time
import zipfile

import cloudstorage

from dateutil import parser

from google.appengine.ext import blobstore, ndb
from google.appengine.ext.webapp import blobstore_handlers

import pytz

import webapp2
from webapp2_extras.routes import RedirectRoute

from wtforms import form, fields, validators, ValidationError

from forms import StringListField, AtLeastOneAdmin, UniqueUsernames, UniqueShortName
from forms import UniquePort, UniqueVersion, VersionUrlExists
import gce
import gcs
from models import Server, User, MinecraftDownload, Command
from server_handler import ServerHandlerBase, PagingHandler
from user_auth import ON_SERVER, UserBase, UserHandler, authentication_required, authenticate, authenticate_admin


RESULTS_PER_PAGE = 50


class AdminHandlerBase(ServerHandlerBase):
    pass


class AdminPagingHandler(AdminHandlerBase, PagingHandler):
    pass


class AdminHandler(AdminPagingHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self):
        results, previous_cursor, next_cursor = self.get_results_with_cursors(
            User.query_all(), User.query_all_reverse(), RESULTS_PER_PAGE
        )
        servers = []
        for server in Server.query():
            servers.append(server)
        instance = gce.Instance.singleton()
        status = instance.get_status()
        context = {'servers': servers, 'instance': instance, 'status': status}
        self.render_template('admin.html', context=context)


class UserForm(form.Form):
    active = fields.BooleanField(u'Active', [validators.Optional()])
    admin = fields.BooleanField(u'Admin', [AtLeastOneAdmin()])
    usernames = StringListField(u'Usernames', validators=[validators.Optional(), UniqueUsernames()])

    def __init__(self, user=None, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.user = user


class UsersHandler(AdminPagingHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self):
        results, previous_cursor, next_cursor = self.get_results_with_cursors(
            User.query_all(), User.query_all_reverse(), RESULTS_PER_PAGE
        )
        context = {'users': results, 'previous_cursor': previous_cursor, 'next_cursor': next_cursor}
        self.render_template('users.html', context=context)


class UserEditHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            user_key = ndb.Key(urlsafe=key)
            user = user_key.get()
            if user is None:
                self.abort(404)
            form = UserForm(user=user, obj=user)
        except Exception, e:
            logging.error(u"Error GETting user: {0}".format(e))
            self.abort(404)
        context = {'edit_user': user, 'form': form}
        self.render_template('user.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            user_key = ndb.Key(urlsafe=key)
            user = user_key.get()
            if user is None:
                self.abort(404)
            form = UserForm(user=user, formdata=self.request.POST, obj=user)
            if form.validate():
                user.active = form.active.data
                user.admin = form.admin.data
                user.set_usernames(form.usernames.data)
                user.put()
                self.redirect(webapp2.uri_for('users'))
        except Exception, e:
            logging.error(u"Error POSTing user: {0}".format(e))
            self.abort(404)
        context = {'edit_user': user, 'form': form}
        self.render_template('user.html', context=context)


class UserRemoveHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            user_key = ndb.Key(urlsafe=key)
            user = user_key.get()
            if user is None:
                self.abort(404)
            if user.admin:
                raise Exception(u"Can't delete an administrator")
            context = {}
            context['question'] = u'Delete user "{0}"?'.format(user.nickname or user.email)
            context['confirmed_url'] = webapp2.uri_for('user_remove', key=user.key.urlsafe())
            context['cancelled_url'] = webapp2.uri_for('user', key=user.key.urlsafe())
            self.render_template('confirm.html', context=context)
        except Exception, e:
            message = u'User "{0}" could not be deleted (Reason: {1}).'.format(user.nickname or user.email, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
            self.redirect(webapp2.uri_for('users'))

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            user_key = ndb.Key(urlsafe=key)
            user = user_key.get()
            if user is None:
                self.abort(404)
            if user.admin:
                raise Exception(u"Can't delete an administrator")
            user.key.delete()
            message = u'User "{0}" deleted.'.format(user.nickname or user.email)
            logging.info(message)
            self.session.add_flash(message, level='info')
            time.sleep(1)
        except Exception, e:
            message = u'User "{0}" could not be deleted (Reason: {1}).'.format(user.nickname or user.email, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('users'))


class ServerForm(form.Form):
    name = fields.StringField(u'Name', [validators.Required()])
    short_name = fields.StringField(u'Short Name', [UniqueShortName()])

    def __init__(self, server=None, *args, **kwargs):
        super(ServerForm, self).__init__(*args, **kwargs)
        self.server = server


def set_form_short_name(server, form):
    short_name = form.short_name.data or None
    if server.set_short_name(short_name):
        return True
    else:
        form.short_name.errors.append("Short name '{0}' is already assigned to another world".format(short_name))
        return False


class ServerCreateHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self):
        form = ServerForm()
        context = {'form': form}
        self.render_template('server_create.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self):
        try:
            form = ServerForm(formdata=self.request.POST)
            if form.validate():
                server = Server.create(name=form.name.data, is_gce=False)
                if not set_form_short_name(server, form):
                    message = "Short name '{0}' is already assigned to another world".format(form.short_name.data)
                    self.session.add_flash(message, level='warn')
                self.redirect(webapp2.uri_for('home', server_key=server.url_key))
        except Exception, e:
            logging.error(u"Error POSTing server: {0}".format(e))
            self.abort(404)
        context = {'form': form}
        self.render_template('server_create.html', context=context)


class ServerEditHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            if server.is_gce:
                self.redirect(webapp2.uri_for('server_gce', key=server.key.urlsafe()))
            form = ServerForm(obj=server, server=server)
        except Exception, e:
            logging.error(u"Error GETting server: {0}".format(e))
            self.abort(404)
        context = {'edit_server': server, 'form': form, 'action': webapp2.uri_for('server', key=server.key.urlsafe())}
        self.render_template('server.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            form = ServerForm(formdata=self.request.POST, server=server)
            if form.validate():
                if set_form_short_name(server, form):
                    server.name = form.name.data
                    server.put()
                    self.redirect(webapp2.uri_for('home', server_key=server.url_key))
        except Exception, e:
            logging.error(u"Error POSTing server: {0}".format(e))
            self.abort(404)
        context = {'edit_server': server, 'form': form, 'action': webapp2.uri_for('server', key=server.key.urlsafe())}
        self.render_template('server.html', context=context)


class ServerPropertiesForm(ServerForm):
    server_port = fields.IntegerField(
        u'The minecraft server port to use (leave blank for first available)',
        validators=[validators.Optional(), validators.NumberRange(min=25565, max=25575), UniquePort()]
    )
    version = fields.SelectField(u'Minecraft Version', validators=[validators.DataRequired()])
    memory = fields.SelectField(u'Server memory', validators=[validators.DataRequired()], default='256M')
    operator = fields.StringField(u'Initial operator username', default='')
    idle_timeout = fields.IntegerField(
        u'Number of minutes before an idle server is automatically paused (zero means never)',
        validators=[validators.InputRequired(), validators.NumberRange(min=0, max=60)],
        default=5
    )
    motd = fields.StringField(u'Message of the day', default='An MC-COAL Minecraft Server')
    white_list = fields.BooleanField(u'Enable whitelist', default=False)
    gamemode = fields.SelectField(u'Game mode', default='0')
    force_gamemode = fields.BooleanField(u'Force players to join in the default game mode', default=False)
    level_type = fields.SelectField(u'Type of map', default='DEFAULT')
    level_seed = fields.StringField(u'Seed for the world', default='')
    generator_settings = fields.StringField(u'Settings used to customize Superflat world generation', default='')
    difficulty = fields.SelectField(u'Server difficulty', default='1')
    pvp = fields.BooleanField(u'Enable PvP', default=False)
    hardcore = fields.BooleanField(u'Hardcore mode (players will be permanently banned if they die)', default=False)
    allow_flight = fields.BooleanField(u'Allow users to use flight while in Survival mode', default=False)
    allow_nether = fields.BooleanField(u'Allow players to travel to the Nether', default=True)
    max_build_height = fields.IntegerField(
        u'Maximum height in which building is allowed',
        validators=[validators.NumberRange(min=0, max=1024)],
        default=256
    )
    generate_structures = fields.BooleanField(u'Generate structures', default=True)
    spawn_npcs = fields.BooleanField(u'Spawn villagers', default=True)
    spawn_animals = fields.BooleanField(u'Spawn animals', default=True)
    spawn_monsters = fields.BooleanField(u'Spawn monsters', default=True)
    view_distance = fields.IntegerField(
        u'Number of chunks of world data the server sends the client',
        validators=[validators.NumberRange(min=3, max=15)],
        default=10
    )
    player_idle_timeout = fields.IntegerField(
        u'Number of minutes before an idle player is kicked (zero means never)',
        validators=[validators.NumberRange(min=0, max=60)],
        default=0
    )
    max_players = fields.IntegerField(
        u'The maximum number of players that can play on the server at the same time',
        validators=[validators.NumberRange(min=0, max=10000)],
        default=20
    )
    max_world_size = fields.IntegerField(
        u'Sets the maximum possible size in blocks, expressed as a radius, that the world border can obtain',
        validators=[validators.NumberRange(min=1, max=29999984)],
        default=29999984
    )
    spawn_protection = fields.IntegerField(
        u'Radius of spawn area protection',
        validators=[validators.NumberRange(min=0, max=64)],
        default=16
    )
    enable_command_block = fields.BooleanField(u'Enable command blocks', default=False)
    snooper_enabled = fields.BooleanField(
        u'Send snoop data regularly to snoop.minecraft.net', default=True
    )
    resource_pack = fields.StringField(
        u'Prompt clients to download resource pack from this URL', default=''
    )
    op_permission_level = fields.SelectField(u'Ops permission level', default='4')
    eula_agree = fields.BooleanField(
        u"Agree to Mojang's EULA (https://account.mojang.com/documents/minecraft_eula)", default=False
    )

    def __init__(self, *args, **kwargs):
        super(ServerPropertiesForm, self).__init__(*args, **kwargs)
        self.version.choices = [
            (d.version, d.version) for d in MinecraftDownload.query().fetch(100)
        ]
        self.memory.choices = [
            ('256M', '256 Megabytes'),
            ('512M', '512 Megabytes'),
            ('1G', '1 Gigabyte'),
            ('2G', '2 Gigabytes'),
            ('3G', '3 Gigabytes'),
            ('4G', '4 Gigabytes'),
            ('5G', '5 Gigabytes'),
            ('6G', '6 Gigabytes'),
            ('7G', '7 Gigabytes'),
            ('8G', '8 Gigabytes')
        ]
        self.gamemode.choices = [
            ('0', 'Survival'),
            ('1', 'Creative'),
            ('2', 'Adventure')
        ]
        self.level_type.choices = [
            ('DEFAULT', 'Default: Standard world with hills, valleys, water, etc.'),
            ('FLAT', 'Flat: A flat world with no features, meant for building.'),
            ('LARGEBIOMES', 'Large Biomes: Same as default but all biomes are larger.'),
            ('AMPLIFIED', 'Amplified: Same as default but world-generation height limit is increased.')
        ]
        self.difficulty.choices = [
            ('0', 'Peaceful'),
            ('1', 'Easy'),
            ('2', 'Normal'),
            ('3', 'Hard')
        ]
        self.op_permission_level.choices = [
            ('1', 'Can bypass spawn protection'),
            ('2', 'Can use /clear, /difficulty, /effect, /gamemode, /gamerule, /give, and /tp, and can edit command blocks'),  # noqa
            ('3', 'Can use /ban, /deop, /kick, and /op'),
            ('4', 'Can use /stop')
        ]

    def validate_eula_agree(form, field):
        if not field.data:
            raise ValidationError("You must agree to the Mojang Minecraft EULA")


class ServerCreateGceHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self):
        username = ''
        usernames = self.request.user.usernames
        if usernames:
            username = usernames[0]
        form = ServerPropertiesForm(operator=username)
        context = {'form': form, 'action': webapp2.uri_for('server_create_gce')}
        self.render_template('server_create.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self):
        try:
            form = ServerPropertiesForm(formdata=self.request.POST)
            if form.validate():
                server = Server.create(
                    name=form.name.data,
                    is_gce=True,
                    version=form.version.data,
                    memory=form.memory.data,
                    operator=form.operator.data or None,
                    idle_timeout=form.idle_timeout.data
                )
                mc_properties = server.mc_properties
                for prop in form:
                    if prop.name not in ['name', 'version', 'memory', 'operator', 'idle_timeout']:
                        if prop.type == 'IntegerField' or prop.name in [
                            'gamemode', 'difficulty', 'op_permission_level'
                        ]:
                            if prop.data is not None:
                                setattr(mc_properties, prop.name, int(prop.data))
                        else:
                            setattr(mc_properties, prop.name, prop.data)
                mc_properties.put()
                if not set_form_short_name(server, form):
                    message = "Short name '{0}' is already assigned to another world".format(form.short_name.data)
                    self.session.add_flash(message, level='warn')
                self.redirect(webapp2.uri_for('home', server_key=server.url_key))
        except Exception, e:
            logging.error(u"Error POSTing GCE server: {0}".format(e))
            self.abort(404)
        context = {'form': form, 'action': webapp2.uri_for('server_create_gce')}
        self.render_template('server_create.html', context=context)


class ServerEditGceHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            if not server.is_gce:
                self.redirect(webapp2.uri_for('server', key=server.key.urlsafe()))
            form = ServerPropertiesForm(
                obj=server.mc_properties,
                server=server,
                name=server.name,
                short_name=server.short_name,
                version=server.version,
                memory=server.memory,
                operator=server.operator or '',
                idle_timeout=server.idle_timeout
            )
        except Exception, e:
            logging.error(u"Error GETting GCE server: {0}".format(e))
            self.abort(404)
        context = {
            'edit_server': server,
            'form': form,
            'action': webapp2.uri_for('server_gce', key=server.key.urlsafe())
        }
        self.render_template('server.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            form = ServerPropertiesForm(formdata=self.request.POST, server=server)
            if form.validate():
                if set_form_short_name(server, form):
                    server.is_gce = True
                    server.name = form.name.data
                    server.version = form.version.data
                    server.memory = form.memory.data
                    server.operator = form.operator.data or None
                    server.idle_timeout = form.idle_timeout.data
                    server.put()
                    mc_properties = server.mc_properties
                    for prop in form:
                        if prop.name not in ['name', 'version', 'memory', 'operator', 'idle_timeout']:
                            if prop.name == 'server_port':
                                if prop.data is not None:
                                    setattr(mc_properties, prop.name, int(prop.data))
                                else:
                                    setattr(mc_properties, prop.name, None)
                            elif prop.type == 'IntegerField' or prop.name in [
                                'gamemode', 'difficulty', 'op_permission_level'
                            ]:
                                setattr(mc_properties, prop.name, int(prop.data))
                            else:
                                setattr(mc_properties, prop.name, prop.data)
                    mc_properties.put()
                    self.redirect(webapp2.uri_for('home', server_key=server.url_key))
        except Exception, e:
            logging.error(u"Error POSTing GCE server: {0}".format(e))
            self.abort(404)
        context = {
            'edit_server': server,
            'form': form,
            'action': webapp2.uri_for('server_gce', key=server.key.urlsafe())
        }
        self.render_template('server.html', context=context)


class ServerDeactivateHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            context = {}
            context['question'] = u'Deactivate world "{0}"?'.format(server.name)
            context['confirmed_url'] = webapp2.uri_for('server_deactivate', key=server.key.urlsafe())
            context['cancelled_url'] = webapp2.uri_for('server', key=server.key.urlsafe())
            self.render_template('confirm.html', context=context)
        except webapp2.HTTPException:
            pass
        except Exception as e:
            message = u'World "{0}" could not be deactivated (Reason: {1}).'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
            self.redirect(webapp2.uri_for('admin'))

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            server.deactivate()
            message = u'World "{0}" deactivated.'.format(server.name)
            logging.info(message)
            self.session.add_flash(message, level='info')
            time.sleep(1)
        except webapp2.HTTPException:
            pass
        except Exception as e:
            message = u'Error deactivating world "{0}": {1}'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('admin'))


class ServerStartHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate)
    def post(self, key):
        server = self.get_server_by_key(key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        try:
            server.start()
            message = u'World "{0}" starting...'.format(server.name)
            logging.info(message)
        except Exception, e:
            logging.error(u"Error starting server: {0}".format(e))
        self.redirect(webapp2.uri_for('home', server_key=server.url_key))


class ServerBackupHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.redirect_to_server('home')
                return
            context = {}
            context['question'] = u'Save "{0}" game?'.format(server.name)
            context['confirmed_url'] = webapp2.uri_for('server_backup', key=server.key.urlsafe())
            context['cancelled_url'] = webapp2.uri_for('home', server_key=server.url_key)
            self.render_template('confirm.html', context=context)
        except webapp2.HTTPException:
            pass
        except Exception as e:
            message = u'"{0}" game could not be saved (Reason: {1}).'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
            self.redirect(webapp2.uri_for('home', server_key=server.url_key))

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        server = self.get_server_by_key(key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        try:
            server.backup()
            message = u'"{0}" game queued to save.'.format(server.name)
            logging.info(message)
            self.session.add_flash(message, level='info')
        except webapp2.HTTPException:
            pass
        except Exception, e:
            message = u'"{0}" game could not be saved (Reason: {1}).'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('home', server_key=server.url_key))


def human_size(size):
    size = int(size)
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return "%3.1f%s" % (size, x)
        size /= 1024.0
    return "%3.1f%s" % (size, 'TB')


def human_date(date_string, timezone):
    dt = parser.parse(date_string)
    if timezone is None:
        timezone = pytz.utc
    timezone_dt = dt.astimezone(timezone)
    return timezone_dt.strftime('%A, %B %d, %Y %I:%M:%S %p')


class ServerRestoreForm(form.Form):
    generation = fields.SelectField(u'Choose Saved Game to Restore', validators=[validators.DataRequired()])

    def __init__(self, versions=None, timezone=None, *args, **kwargs):
        super(ServerRestoreForm, self).__init__(*args, **kwargs)
        self.generation.choices = []
        if versions:
            for v in versions:
                generation = v['generation']
                name = "{0} ({1})".format(human_date(v['updated'], timezone), human_size(v['size']))
                if v.get('timeDeleted', None):
                    self.generation.choices.append((generation, name))


class ServerRestoreHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            if not server.is_gce:
                self.redirect(webapp2.uri_for('server', key=server.key.urlsafe()))
            versions = gcs.get_versions(server.key.urlsafe())
            current_version = versions[0] if versions else None
            if current_version:
                current_version_name = "{0} ({1})".format(
                    human_date(current_version['updated'], self.request.user.timezone),
                    human_size(current_version['size'])
                )
            form = ServerRestoreForm(
                versions=versions,
                timezone=self.request.user.timezone
            )
            url = webapp2.uri_for('server_uploaded', key=server.key.urlsafe())
            upload_url = blobstore.create_upload_url(
                url, gs_bucket_name="{0}/uploads/".format(gcs.get_default_bucket_name())
            )
        except Exception, e:
            logging.error(u"Error GETting GCE server restore: {0}".format(e))
            self.abort(404)
        context = {
            'edit_server': server,
            'current_version': current_version_name if current_version else None,
            'form': form,
            'action': webapp2.uri_for('server_restore', key=server.key.urlsafe()),
            'upload_url': upload_url
        }
        self.render_template('server_restore.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.abort(404)
            if not server.is_gce:
                self.redirect(webapp2.uri_for('home', server_key=server.url_key))
            form = ServerRestoreForm(
                formdata=self.request.POST,
                versions=gcs.get_versions(server.key.urlsafe()),
                timezone=self.request.user.timezone
            )
            if form.validate():
                gcs.restore_generation(server.key.urlsafe(), form.generation.data)
                name = None
                for choice in form.generation.choices:
                    if choice[0] == form.generation.data:
                        name = choice[1]
                        break
                message = u"Saved game restored."
                if name:
                    message = u"Saved game {0} restored.".format(name)
                logging.info(message)
                self.session.add_flash(message, level='info')
                self.redirect(webapp2.uri_for('home', server_key=server.url_key))
        except Exception, e:
            message = "Problem restoring game: {0}".format(e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        context = {
            'edit_server': server,
            'form': form,
            'action': webapp2.uri_for('server_restore', key=server.key.urlsafe())
        }
        self.render_template('server_restore.html', context=context)


class ServerRestartHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.redirect_to_server('home')
                return
            context = {}
            context['question'] = u'Restart world "{0}"?'.format(server.name)
            context['confirmed_url'] = webapp2.uri_for('server_restart', key=server.key.urlsafe())
            context['cancelled_url'] = webapp2.uri_for('home', server_key=server.url_key)
            self.render_template('confirm.html', context=context)
        except webapp2.HTTPException:
            pass
        except Exception as e:
            message = u'World "{0}" could not be restarted (Reason: {1}).'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
            self.redirect(webapp2.uri_for('home', server_key=server.url_key))

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        server = self.get_server_by_key(key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        try:
            server.restart()
            message = u'World "{0}" restarting...'.format(server.name)
            logging.info(message)
        except webapp2.HTTPException:
            pass
        except Exception, e:
            message = u'World "{0}" could not be restarted (Reason: {1}).'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('home', server_key=server.url_key))


class ServerStopHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None:
                self.redirect_to_server('home')
                return
            context = {}
            context['question'] = u'Pause world "{0}"?'.format(server.name)
            context['confirmed_url'] = webapp2.uri_for('server_stop', key=server.key.urlsafe())
            context['cancelled_url'] = webapp2.uri_for('home', server_key=server.url_key)
            self.render_template('confirm.html', context=context)
        except webapp2.HTTPException:
            pass
        except Exception as e:
            message = u'World "{0}" could not be paused (Reason: {1}).'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
            self.redirect(webapp2.uri_for('home', server_key=server.url_key))

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        server = self.get_server_by_key(key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        try:
            server.stop()
            message = u'World "{0}" pausing...'.format(server.name)
            logging.info(message)
        except webapp2.HTTPException:
            pass
        except Exception, e:
            message = u'World "{0}" could not be paused (Reason: {1}).'.format(server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('home', server_key=server.url_key))


class CommandForm(form.Form):
    command = fields.StringField(u'Command', validators=[validators.DataRequired()])


class ServerCommandHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def post(self, key=None):
        server = self.get_server_by_key(key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        try:
            form = CommandForm(self.request.POST)
            if form.validate():
                command = form.command.data
                username = self.request.user.get_server_play_name(server.key)
                if command and command.startswith(u'/say '):
                    if len(command) <= 5:
                        command = None
                    elif username:
                        command = u"/say <{0}> {1}".format(username, command[5:])
                if command:
                    Command.push(server.key, username, command)
                    message = u'Command "{0}" sent to world "{1}".'.format(command, server.name)
                    logging.info(message)
        except Exception, e:
            message = u'Command "{0}" could not be send to world "{1}" (Reason: {2}).'.format(command, server.name, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('home', server_key=server.url_key))


class ServerBackupDownloadHandler(blobstore_handlers.BlobstoreDownloadHandler, UserBase):
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
        self.request.server = server
        return self.request.server

    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        server = self.get_server_by_key(key)
        blobstore_filename = "/gs/{0}/{1}".format(
            gcs.get_default_bucket_name(), gcs.get_gcs_archive_name(server.key.urlsafe())
        )
        blob_key = blobstore.create_gs_key(blobstore_filename)
        self.send_blob(blob_key, save_as="{0}.zip".format(server.short_name or server.name or server.key.urlsafe()))


def validate_server_archive(gcs_file):
    valid = False
    if zipfile.is_zipfile(gcs_file):
        zf = zipfile.ZipFile(gcs_file, 'r')
        zip_infos = zf.infolist()
        filenames = [zi.filename for zi in zip_infos]
        required_filenames = ['world/']
        valid = True
        for r in required_filenames:
            if r not in filenames:
                valid = False
                break
    return valid


class ServerUploadedHandler(blobstore_handlers.BlobstoreUploadHandler, UserHandler):
    def get_server_by_key(self, key, abort=True):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
        except Exception:
            server = None
        if abort and not server:
            self.abort(404)
        self.request.server = server
        return self.request.server

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            object_name = None
            server = self.get_server_by_key(key)
            file_infos = self.get_file_infos()
            if file_infos:
                file_info = file_infos[0]
                object_name = file_info.gs_object_name[3:]
                gcs_file = cloudstorage.open(object_name)
                if validate_server_archive(gcs_file):
                    prefix = "/{0}/".format(gcs.get_default_bucket_name())
                    object_name.index(prefix)
                    gcs_object_name = object_name[len(prefix):]
                    gcs.copy_archive(server.key.urlsafe(), gcs_object_name)
                    message = u'Minecraft world successfully uploaded'
                    self.session.add_flash(message, level='info')
                else:
                    message = u'Invalid minecraft world archive'
                    logging.error(message)
                    self.session.add_flash(message, level='error')
            else:
                message = u'No file chosen'
                self.session.add_flash(message, level='error')
        except Exception as e:
            message = u'Minecraft world archive could not be uploaded (Reason: {0})'.format(e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        try:
            if object_name:
                cloudstorage.delete(object_name)
        except Exception as e:
            logging.error("Problem deleting uploaded server archive {0} (Reason: {1})".format(object_name, e))
        self.redirect(webapp2.uri_for('home', server_key=server.url_key))


class MinecraftDownloadForm(form.Form):
    version = fields.StringField(u'Version', validators=[validators.DataRequired(), UniqueVersion()])
    url = fields.StringField(u'Download URL', validators=[validators.URL(), VersionUrlExists()])


class MinecraftDownloadHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self):
        form = MinecraftDownloadForm()
        downloads = MinecraftDownload.query().fetch(100)
        context = {'form': form, 'downloads': downloads}
        self.render_template('versions.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self):
        form = MinecraftDownloadForm(self.request.POST)
        if form.validate():
            try:
                download = MinecraftDownload.create(form.version.data, form.url.data)
                download.put()
                message = u'Minecraft version "{0}" created.'.format(download.version)
                logging.info(message)
                self.session.add_flash(message, level='info')
                time.sleep(1)
                self.redirect(webapp2.uri_for('minecraft_versions'))
            except webapp2.HTTPException:
                pass
            except Exception, e:
                message = u'Minecraft version "{0}" could not be created (Reason: {1}).'.format(form.version.data, e)
                logging.error(message)
                self.session.add_flash(message, level='error')
        downloads = MinecraftDownload.query().fetch(100)
        context = {'form': form, 'downloads': downloads}
        self.render_template('versions.html', context=context)


class MinecraftDownloadRemoveHandler(AdminHandlerBase):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            version_key = ndb.Key(urlsafe=key)
            version = version_key.get()
            if version is None:
                self.abort(404)
            context = {}
            context['question'] = u'Delete version "{0}"?'.format(version.version)
            context['confirmed_url'] = webapp2.uri_for('minecraft_version_remove', key=version.key.urlsafe())
            context['cancelled_url'] = webapp2.uri_for('minecraft_versions')
            self.render_template('confirm.html', context=context)
        except Exception, e:
            message = u'Version "{0}" could not be deleted (Reason: {1}).'.format(version.version, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
            self.redirect(webapp2.uri_for('minecraft_versions'))

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            version_key = ndb.Key(urlsafe=key)
            version = version_key.get()
            if version is None:
                self.abort(404)
            version.key.delete()
            message = u'Version "{0}" deleted.'.format(version.version)
            logging.info(message)
            self.session.add_flash(message, level='info')
            time.sleep(1)
        except Exception, e:
            message = u'Version "{0}" could not be deleted (Reason: {1}).'.format(version.version, e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('minecraft_versions'))


class InstanceForm(form.Form):
    zone = fields.SelectField(u'Zone', validators=[validators.DataRequired()])
    machine_type = fields.SelectField(u'Machine Type', validators=[validators.DataRequired()])
    disk_size = fields.IntegerField(u'Disk Size (GB)', validators=[validators.DataRequired(), validators.NumberRange(min=10, max=10240)], default=100)  # noqa
    backup_depth = fields.IntegerField(u'Number Of Saved Games', validators=[validators.DataRequired(), validators.NumberRange(min=1, max=1000)], default=10)  # noqa
    reserved_ip = fields.BooleanField(u'Use Reserved IP Address')

    def __init__(self, *args, **kwargs):
        super(InstanceForm, self).__init__(*args, **kwargs)
        self.zone.choices = [(z, z) for z in gce.get_zones() or []]
        self.machine_type.choices = [
            ('f1-micro', '1 vCPU (shared physical core), 0.6 GB RAM'),
            ('g1-small', '1 vCPU (shared physical core), 1.7 GB RAM'),
            ('n1-standard-1', '1 vCPU, 3.75 GB RAM'),
            ('n1-standard-2', '2 vCPUs, 7.5 GB RAM'),
            ('n1-highcpu-2', '2 vCPUs, 1.8 GB RAM'),
            ('n1-highmem-2', '2 vCPUs, 13GB RAM'),
            ('n1-standard-4', '4 vCPUs, 15 GB RAM'),
            ('n1-highcpu-4', '4 vCPUs, 3.6 GB RAM'),
            ('n1-highmem-4', '4 vCPUs, 26GB RAM'),
            ('n1-standard-8', '8 vCPUs, 30 GB RAM'),
            ('n1-highcpu-8', '8 vCPUs, 7.2 GB RAM'),
            ('n1-highmem-8', '8 vCPUs, 52GB RAM')
        ]


class InstanceConfigureHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self):
        instance = gce.Instance.singleton()
        form = InstanceForm(obj=instance)
        context = {'form': form, 'instance': instance}
        self.render_template('instance_configure.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self):
        form = InstanceForm(self.request.POST)
        if form.validate():
            instance = gce.Instance.singleton()
            instance.zone = form.zone.data
            instance.machine_type = form.machine_type.data
            instance.disk_size = form.disk_size.data
            instance.backup_depth = form.backup_depth.data
            instance.reserved_ip = form.reserved_ip.data
            instance.put()
            self.redirect(webapp2.uri_for('admin'))
        context = {'form': form, 'instance': instance}
        self.render_template('instance_configure.html', context=context)


class InstanceStartHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def post(self):
        instance = gce.Instance.singleton()
        instance.start()
        self.redirect(webapp2.uri_for('admin'))


class InstanceStopHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self):
        try:
            context = {}
            context['question'] = u'Kill the GCE instance?'
            context['confirmed_url'] = webapp2.uri_for('instance_stop')
            context['cancelled_url'] = webapp2.uri_for('admin')
            self.render_template('confirm.html', context=context)
        except webapp2.HTTPException:
            pass
        except Exception as e:
            message = u'GCE instance could not be killed (Reason: {0}).'.format(e)
            logging.error(message)
            self.session.add_flash(message, level='error')
            self.redirect(webapp2.uri_for('admin'))

    @authentication_required(authenticate=authenticate_admin)
    def post(self):
        try:
            instance = gce.Instance.singleton()
            instance.stop()
            message = u'GCE instance killed.'
            logging.info(message)
            self.session.add_flash(message, level='info')
            time.sleep(1)
        except webapp2.HTTPException:
            pass
        except Exception, e:
            message = u'GCE instance could not be killed (Reason: {0}).'.format(e)
            logging.error(message)
            self.session.add_flash(message, level='error')
        self.redirect(webapp2.uri_for('admin'))


class ServerLogHandler(UserHandler):
    @authentication_required(authenticate=authenticate_admin)
    def get(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None or ON_SERVER:
                self.abort(404)
        except Exception:
            self.abort(404)
        context = {'edit_server': server, 'action': webapp2.uri_for('server_upload_log', key=server.key.urlsafe())}
        self.render_template('server_log.html', context=context)

    @authentication_required(authenticate=authenticate_admin)
    def post(self, key):
        try:
            server_key = ndb.Key(urlsafe=key)
            server = server_key.get()
            if server is None or ON_SERVER:
                self.abort(404)
            file = self.request.POST['file']
            import StringIO
            from models import LogLine
            buf = StringIO.StringIO(file.value)
            for raw_line in buf.readlines():
                line = raw_line.decode('ISO-8859-2', errors='ignore')
                line = line.strip()
                existing_line = LogLine.lookup_line(server.key, line)
                if existing_line is None:
                    log_line = LogLine.create(server, line, 'UTC')
                    logging.info(log_line.line)
        except Exception, e:
            logging.error(u"Error POSTing server: {0}".format(e))
            self.abort(404)
        context = {
            'edit_server': server,
            'form': form,
            'action': webapp2.uri_for('server_upload_log', key=server.key.urlsafe())
        }
        self.render_template('server_log.html', context=context)


routes = [
    RedirectRoute('/admin', handler=AdminHandler, strict_slash=True, name="admin"),
    RedirectRoute('/admin/users', handler=UsersHandler, strict_slash=True, name="users"),
    RedirectRoute('/admin/users/<key>', handler=UserEditHandler, strict_slash=True, name="user"),
    RedirectRoute('/admin/users/<key>/remove', handler=UserRemoveHandler, strict_slash=True, name="user_remove"),
    RedirectRoute('/admin/server_create', handler=ServerCreateHandler, strict_slash=True, name="server_create"),
    RedirectRoute('/admin/server_create_gce', handler=ServerCreateGceHandler, strict_slash=True, name="server_create_gce"),  # noqa
    RedirectRoute('/admin/servers/<key>', handler=ServerEditHandler, strict_slash=True, name="server"),
    RedirectRoute('/admin/servers/<key>/gce', handler=ServerEditGceHandler, strict_slash=True, name="server_gce"),
    RedirectRoute('/admin/servers/<key>/deactivate', handler=ServerDeactivateHandler, strict_slash=True, name="server_deactivate"),  # noqa
    RedirectRoute('/admin/servers/<key>/start', handler=ServerStartHandler, strict_slash=True, name="server_start"),
    RedirectRoute('/admin/servers/<key>/backup', handler=ServerBackupHandler, strict_slash=True, name="server_backup"),  # noqa
    RedirectRoute('/admin/servers/<key>/download', handler=ServerBackupDownloadHandler, strict_slash=True, name="server_backup_download"),  # noqa
    RedirectRoute('/admin/servers/<key>/uploaded', handler=ServerUploadedHandler, strict_slash=True, name="server_uploaded"),  # noqa
    RedirectRoute('/admin/servers/<key>/restore', handler=ServerRestoreHandler, strict_slash=True, name="server_restore"),  # noqa
    RedirectRoute('/admin/servers/<key>/restart', handler=ServerRestartHandler, strict_slash=True, name="server_restart"),  # noqa
    RedirectRoute('/admin/servers/<key>/stop', handler=ServerStopHandler, strict_slash=True, name="server_stop"),
    RedirectRoute('/admin/servers/<key>/command', handler=ServerCommandHandler, strict_slash=True, name="server_command"),  # noqa
    RedirectRoute('/admin/servers/<key>/upload_log', handler=ServerLogHandler, strict_slash=True, name="server_upload_log"),  # noqa
    RedirectRoute('/admin/versions', handler=MinecraftDownloadHandler, strict_slash=True, name="minecraft_versions"),
    RedirectRoute('/admin/versions/<key>/remove', handler=MinecraftDownloadRemoveHandler, strict_slash=True, name="minecraft_version_remove"),  # noqa
    RedirectRoute('/admin/instance/configure', handler=InstanceConfigureHandler, strict_slash=True, name="instance_configure"),  # noqa
    RedirectRoute('/admin/instance/start', handler=InstanceStartHandler, strict_slash=True, name="instance_start"),
    RedirectRoute('/admin/instance/stop', handler=InstanceStopHandler, strict_slash=True, name="instance_stop"),
]
