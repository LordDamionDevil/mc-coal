import fix_path  # noqa

import logging
import os
import urllib2

from google.appengine.api import lib_config
from google.appengine.api import users as google_users
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers

import pytz

import webapp2

from webapp2_extras.routes import RedirectRoute

from wtforms import form, fields, validators

from base_handler import uri_for_pagination
from channel import ServerChannels
from forms import ValidTimezone
from models import User, Player, LogLine, PlaySession, ScreenShot, Command, Server, MojangException
import search
from server_handler import ServerHandlerBase, PagingHandler
from user_auth import UserBase, authentication_required, authenticate, mojang_authentication


ON_SERVER = not os.environ.get('SERVER_SOFTWARE', 'Development').startswith('Development')
RESULTS_PER_PAGE = 50
TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.common_timezones if tz.startswith('U')] + \
    [(tz, tz) for tz in pytz.common_timezones if not tz.startswith('U')]


class MainHandlerBase(ServerHandlerBase):
    pass


class MainPagingHandler(MainHandlerBase, PagingHandler):
    pass


class UserEmailForm(form.Form):
    email = fields.StringField(u'Contact Email', validators=[validators.Email(message=u'Invalid email address.')])


class MainHandler(MainHandlerBase):
    def get(self):
        context = {'title': main_config.TITLE, 'description': main_config.DESCRIPTION}
        user = self.user
        if user:
            if user.active:
                servers = Server.query_all().fetch(100)
                if servers and len(servers) == 1:
                    self.redirect(webapp2.uri_for('home', server_key=servers[0].url_key))
                    return
                context = {
                    'servers': servers
                }
                self.render_template('main.html', context=context)
            else:
                form = UserEmailForm(obj=user)
                context['form'] = form
                self.render_template('main_inactive.html', context=context)
        else:
            self.render_template('main_unauth.html', context=context)

    def post(self):
        user = self.user
        if user and not user.active:
            form = UserEmailForm(self.request.POST, user)
            if form.validate():
                user.email = form.email.data
                user.put()
                self.redirect(webapp2.uri_for('main'))
            context = {
                'title': main_config.TITLE,
                'description': main_config.DESCRIPTION,
                'form': form
            }
            self.render_template('main_inactive.html', context=context)
        else:
            self.redirect(webapp2.uri_for('main'))


class HomeHandler(MainHandlerBase):
    @authentication_required(authenticate=authenticate)
    def get(self, server_key=None):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        # Get new chats
        new_chats_query = LogLine.query_latest_events(server.key)
        last_chat_view = self.request.user.last_chat_view
        if last_chat_view is not None:
            new_chats_query = new_chats_query.filter(LogLine.timestamp > last_chat_view)
        new_chats, chats_cursor, more = new_chats_query.fetch_page(20)
        if new_chats:
            self.request.user.record_chat_view(new_chats[0].timestamp)
        user = self.request.user
        channel_token = ServerChannels.create_channel(server.key, user)
        # Render with context
        context = {
            'open_sessions': server.open_sessions,
            'new_chats': new_chats,
            'chats_cursor': chats_cursor,
            'channel_token': channel_token,
            'username': user.get_server_play_name(server.key),
        }
        self.render_template('home.html', context=context)


class ChatForm(form.Form):
    chat = fields.StringField(u'Chat', validators=[validators.DataRequired()])


class ChatsHandler(MainPagingHandler):
    @authentication_required(authenticate=authenticate)
    def get(self, server_key=None):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('chats')
            return
        self.request.user.record_chat_view()
        query_string = self.request.get('q', None)
        # Search
        if query_string:
            page = 0
            cursor = self.request.get('cursor', None)
            if cursor and cursor.startswith('PAGE_'):
                page = int(cursor.strip()[5:])
            offset = page*RESULTS_PER_PAGE
            results, number_found, _ = search.search_log_lines(
                'chat:{0}'.format(query_string),
                server_key=server.key,
                limit=RESULTS_PER_PAGE,
                offset=offset
            )
            previous_cursor = next_cursor = None
            if page > 0:
                previous_cursor = u'PAGE_{0}&q={1}'.format(page - 1 if page > 0 else 0, query_string)
            if number_found > offset + RESULTS_PER_PAGE:
                next_cursor = u'PAGE_{0}&q={1}'.format(page + 1, query_string)
        # Latest
        else:
            results, previous_cursor, next_cursor = self.get_results_with_cursors(
                LogLine.query_latest_events(server.key), LogLine.query_oldest_events(server.key), RESULTS_PER_PAGE
            )
        context = {'chats': results, 'query_string': query_string or ''}
        if self.request.is_xhr:
            self.render_xhr_response(server.key, context, next_cursor)
        else:
            self.render_html_response(server.key, context, next_cursor, previous_cursor)

    def render_xhr_response(self, server_key, context, next_cursor):
        if next_cursor:
            context.update({
                'next_uri': uri_for_pagination('chats', server_key=server_key.urlsafe(), cursor=next_cursor)
            })
        self.response.headers['Content-Type'] = 'text/javascript'
        self.render_template('chats.js', context=context)

    def render_html_response(self, server_key, context, next_cursor, previous_cursor):
        user = self.request.user
        channel_token = ServerChannels.create_channel(server_key, user)
        context.update({
            'next_cursor': next_cursor,
            'previous_cursor': previous_cursor,
            'channel_token': channel_token,
            'username': user.get_server_play_name(server_key),
        })
        self.render_template('chats.html', context=context)

    @authentication_required(authenticate=authenticate)
    def post(self, server_key=None):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('chats')
            return
        try:
            user = self.request.user
            if not (user and user.active):
                self.abort(404)
            form = ChatForm(self.request.POST)
            if form.validate():
                chat = form.chat.data
                username = user.get_server_play_name(server.key)
                if chat:
                    if username:
                        chat = u"/say <{0}> {1}".format(username, chat)
                    else:
                        chat = u"/say {0}".format(chat)
                    Command.push(server.key, username, chat)
        except Exception, e:
            logging.error(u"Error POSTing chat: {0}".format(e))
            self.abort(500)
        self.response.set_status(201)


class PlayersHandler(MainPagingHandler):
    @authentication_required(authenticate=authenticate)
    def get(self, server_key=None):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('players')
            return
        results, previous_cursor, next_cursor = self.get_results_with_cursors(
            Player.query_all_reverse(server.key), Player.query_all(server.key), RESULTS_PER_PAGE
        )
        context = {'players': results, 'previous_cursor': previous_cursor, 'next_cursor': next_cursor}
        self.render_template('players.html', context=context)


class PlaySessionsHandler(MainPagingHandler):
    @authentication_required(authenticate=authenticate)
    def get(self, server_key=None):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('play_sessions')
            return
        results, previous_cursor, next_cursor = self.get_results_with_cursors(
            PlaySession.query_latest(server.key), PlaySession.query_oldest(server.key), RESULTS_PER_PAGE
        )
        context = {'play_sessions': results, 'previous_cursor': previous_cursor, 'next_cursor': next_cursor}
        self.render_template('play_sessions.html', context=context)


class ScreenShotUploadHandler(MainHandlerBase):
    @authentication_required(authenticate=authenticate)
    def get(self, server_key):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        url = webapp2.uri_for('screenshot_uploaded', server_key=server.key.urlsafe())
        upload_url = blobstore.create_upload_url(url)
        context = {'upload_url': upload_url}
        self.render_template('screen_shot_upload.html', context=context)


class ScreenShotUploadedHandler(blobstore_handlers.BlobstoreUploadHandler, UserBase):
    def redirect_to_server(self, route_name):
        servers = Server.query_all().fetch(2)
        if servers and len(servers) == 1:
            self.redirect(webapp2.uri_for(route_name, server_key=servers[0].url_key))
        else:
            self.redirect(webapp2.uri_for('main'))

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

    @authentication_required(authenticate=authenticate)
    def post(self, server_key):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('home')
            return
        blob_info = self.get_uploads('file')[0]
        ScreenShot.create(server.key, self.request.user, blob_info=blob_info)
        self.redirect(webapp2.uri_for('screenshots', server_key=server.url_key))


class ScreenShotsHandler(MainPagingHandler):
    @authentication_required(authenticate=authenticate)
    def get(self, server_key=None):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('screenshots')
            return
        results, previous_cursor, next_cursor = self.get_results_with_cursors(
            ScreenShot.query_latest(server.key), ScreenShot.query_oldest(server.key), 5
        )
        context = {'screenshots': results, 'previous_cursor': previous_cursor, 'next_cursor': next_cursor}
        self.render_template('screen_shots.html', context=context)


class ScreenShotBlurHandler(MainHandlerBase):
    def post(self, key=None):
        try:
            screenshot = ndb.Key(urlsafe=key).get()
            if screenshot is not None:
                screenshot.create_blurred()
        except Exception, e:
            logging.error(u"Error creating blurred screen shot: {0}".format(e))


class ScreenShotRemoveHandler(MainHandlerBase):
    @authentication_required(authenticate=authenticate)
    def post(self, server_key, key):
        server = self.get_server_by_key(server_key, abort=False)
        if server is None:
            self.redirect_to_server('screenshots')
            return
        try:
            screenshot_key = ndb.Key(urlsafe=key)
            if screenshot_key.parent() != server.key:
                self.abort(404)
            screenshot = screenshot_key.get()
            if screenshot is not None:
                screenshot.key.delete()
        except Exception, e:
            logging.error(u"Error removing screen shot: {0}".format(e))
        self.redirect(webapp2.uri_for('screenshots', server_key=server.key.url_key))


class UserProfileForm(form.Form):
    email = fields.StringField(
        u'Email', validators=[validators.Optional(), validators.Email(message=u'Invalid email address.')]
    )
    nickname = fields.StringField(u'Nickname', validators=[validators.Optional()])
    timezone_name = fields.SelectField(u'Timezone', choices=TIMEZONE_CHOICES, validators=[ValidTimezone()])


class UsernameClaimForm(form.Form):
    username = fields.StringField(u'Username', validators=[validators.DataRequired()])
    password = fields.PasswordField(u'Password', validators=[validators.DataRequired()])


class UserProfileHandler(MainHandlerBase):
    @authentication_required(authenticate=authenticate)
    def get(self):
        next_url = self.request.params.get('next_url', webapp2.uri_for('main'))
        user = self.request.user
        form = UserProfileForm(obj=user)
        claim_form = UsernameClaimForm()
        gae_claim_uri = get_gae_claim_uri(self, next_url)
        context = {
            'edit_user': user,
            'form': form,
            'claim_form': claim_form,
            'gae_claim_uri': gae_claim_uri,
            'next_url': next_url
        }
        self.render_template('user_profile.html', context=context)

    @authentication_required(authenticate=authenticate)
    def post(self):
        next_url = self.request.params.get('next_url', webapp2.uri_for('main'))
        user = self.request.user
        form = UserProfileForm(self.request.POST, user)
        if form.validate():
            user.email = form.email.data
            user.nickname = form.nickname.data
            user.timezone_name = form.timezone_name.data
            user.put()
            self.redirect(next_url)
        claim_form = UsernameClaimForm()
        gae_claim_uri = get_gae_claim_uri(self, next_url)
        context = {
            'edit_user': user,
            'form': form,
            'claim_form': claim_form,
            'gae_claim_uri': gae_claim_uri,
            'next_url': next_url
        }
        self.render_template('user_profile.html', context=context)


def get_gae_callback_uri(handler, next_url=None):
    try:
        callback_url = handler.uri_for('gae_claim_callback')
    except:
        callback_url = '/gae_claim_callback'
    if next_url:
        callback_url = "{0}?next_url={1}".format(callback_url, urllib2.quote(next_url))
    return callback_url


def get_gae_claim_uri(handler, next_url=None):
    return google_users.create_login_url(get_gae_callback_uri(handler, next_url=next_url))


class GoogleAppEngineUserClaimHandler(MainHandlerBase):
    @authentication_required(authenticate=authenticate)
    def get(self):
        user = self.request.user
        gae_user = google_users.get_current_user()
        auth_id = User.get_gae_user_auth_id(gae_user=gae_user) if gae_user else None
        existing_user = self.auth.store.user_model.get_by_auth_id(auth_id)
        if existing_user is not None and user.key != existing_user.key:
            user.merge(existing_user)
        else:
            user.add_auth_id(auth_id)
            user.put()
        self.redirect(webapp2.uri_for('user_profile'))


class UsernameClaimHandler(MainHandlerBase):
    @authentication_required(authenticate=authenticate)
    def post(self):
        next_url = self.request.params.get('next_url', webapp2.uri_for('user_profile'))
        form = UsernameClaimForm(self.request.POST)
        if form.validate():
            username = form.username.data
            password = form.password.data
            try:
                u, uuid, access_token = mojang_authentication(username, password)
                if u:
                    user = self.request.user
                    auth_id = User.get_mojang_auth_id(uuid=uuid)
                    existing_user = self.auth.store.user_model.get_by_auth_id(auth_id)
                    if existing_user is not None and user.key != existing_user.key:
                        user.merge(existing_user)
                    existing_user = User.lookup(username=u)
                    if existing_user is not None and user.key != existing_user.key:
                        user.merge(existing_user)
                    else:
                        user.add_username(u)
                        auth_id = User.get_mojang_auth_id(uuid=uuid)
                        user.add_auth_id(auth_id)
                        user.put()
            except MojangException as me:
                message = u'Mojang authentication failed (Reason: {0}).'.format(me)
                logging.error(message)
                self.session.add_flash(message, level='error')
        self.redirect(next_url)


main_config = lib_config.register('main', {
    'SECRET_KEY': 'a_secret_string',
    'COOKIE_MAX_AGE': 2592000,
    'TITLE': 'An MC-COAL Installation',
    'DESCRIPTION': 'This is an installation of the MC-COAL open source project'
})


def get_home_redirect(handler, *args, **kwargs):
    short_name = kwargs.get('short_name', None)
    if not short_name:
        return handler.uri_for('main')
    server = Server.get_by_short_name(short_name)
    if not server:
        return handler.uri_for('main')
    return handler.uri_for('home', server_key=server.short_name)


application = webapp2.WSGIApplication(
    [
        RedirectRoute('/', handler=MainHandler, name="main"),
        RedirectRoute('/gae_claim_callback', handler=GoogleAppEngineUserClaimHandler, name='gae_claim_callback'),  # noqa
        RedirectRoute('/players/claim', handler=UsernameClaimHandler, strict_slash=True, name="username_claim"),
        RedirectRoute('/chats', handler=ChatsHandler, strict_slash=True, name="naked_chats"),
        RedirectRoute('/players', handler=PlayersHandler, strict_slash=True, name="naked_players"),
        RedirectRoute('/sessions', handler=PlaySessionsHandler, strict_slash=True, name="naked_play_sessions"),
        RedirectRoute('/screenshots', handler=ScreenShotsHandler, strict_slash=True, name="naked_screenshots_lol"),
        RedirectRoute('/screenshots/<key>/create_blur', handler=ScreenShotBlurHandler, strict_slash=True, name="naked_screenshots_blur"),  # noqa
        RedirectRoute('/servers/<server_key>', handler=HomeHandler, name="home"),
        RedirectRoute('/servers/<server_key>/chats', handler=ChatsHandler, strict_slash=True, name="chats"),
        RedirectRoute('/servers/<server_key>/players', handler=PlayersHandler, strict_slash=True, name="players"),
        RedirectRoute('/servers/<server_key>/sessions', handler=PlaySessionsHandler, strict_slash=True, name="play_sessions"),  # noqa
        RedirectRoute('/servers/<server_key>/screenshot_upload', handler=ScreenShotUploadHandler, strict_slash=True, name="screenshot_upload"),  # noqa
        RedirectRoute('/servers/<server_key>/screenshot_uploaded', handler=ScreenShotUploadedHandler, strict_slash=True, name="screenshot_uploaded"),  # noqa
        RedirectRoute('/servers/<server_key>/screenshots', handler=ScreenShotsHandler, strict_slash=True, name="screenshots"),  # noqa
        RedirectRoute('/servers/<server_key>/screenshots/<key>/remove', handler=ScreenShotRemoveHandler, strict_slash=True, name="screenshot_remove"),  # noqa
        RedirectRoute('/profile', handler=UserProfileHandler, strict_slash=True, name="user_profile"),
    ],
    config={
        'webapp2_extras.sessions': {
            'secret_key': main_config.SECRET_KEY,
            'cookie_args': {'max_age': main_config.COOKIE_MAX_AGE}
        },
        'webapp2_extras.auth': {'user_model': 'models.User', 'token_max_age': main_config.COOKIE_MAX_AGE}
    },
    debug=not ON_SERVER
)

from admin import routes as admin_routes
from user_auth import routes as user_auth_routes
from api import routes as api_routes
from image import routes as image_routes
from oauth import routes as oauth_routes
routes = admin_routes + user_auth_routes + api_routes + image_routes + oauth_routes
for route in routes:
    application.router.add(route)
application.router.add(RedirectRoute('/<short_name>', handler=webapp2.RedirectHandler, defaults={'_uri': get_home_redirect}, name="home_redirect"))
