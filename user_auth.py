import fix_path  # noqa

import datetime
from functools import wraps
import json
import logging
import os
import time
import urllib2
import urlparse

from google.appengine.api import users, urlfetch, app_identity, mail

import webapp2
from webapp2_extras import auth, sessions
from webapp2_extras.routes import RedirectRoute

from wtforms import form, fields, validators

from base_handler import JinjaHandler
from models import User, MojangException


ON_SERVER = not os.environ.get('SERVER_SOFTWARE', 'Development').startswith('Development')


def get_gae_callback_uri(handler, next_url=None):
    try:
        callback_url = handler.uri_for('gae_login_callback')
    except:
        callback_url = '/gae_login_callback'
    if next_url:
        callback_url = "{0}?next_url={1}".format(callback_url, urllib2.quote(next_url))
    return callback_url


def get_gae_login_uri(handler, next_url=None):
    return users.create_login_url(get_gae_callback_uri(handler, next_url=next_url))


def get_login_uri(handler, next_url=None):
    query_params = {}
    if next_url is not None:
        query_params['next_url'] = next_url
    return handler.uri_for('login', **query_params)


def authenticate_abort_403(handler):
    handler.abort(403)


def authentication_required(authenticate=None, request_property_name='user', require_https=False):
    if authenticate is None:
        authenticate = authenticate_abort_403

    def decorator(request_method):
        @wraps(request_method)
        def wrapped(self, *args, **kwargs):
            if require_https:
                scheme, netloc, path, query, fragment = urlparse.urlsplit(self.request.url)
                if ON_SERVER and scheme and scheme.lower() != 'https':
                    self.abort(403)
            setattr(self.request, request_property_name, authenticate(self))
            request_method(self, *args, **kwargs)
        return wrapped
    return decorator


def https_authentication_required(authenticate=None):
    return authentication_required(authenticate=authenticate, require_https=True)


def authenticate(handler, required=True, admin=False):
    next_url = handler.request.path_qs
    user = handler.user
    if user is not None:
        update = False
        if admin and not user.admin and User.query().filter(User.admin == True).count(keys_only=True, limit=1) == 0:  # noqa
            user.admin = True
            user.active = True
            update = True
        if update:
            user.put()
    if required and not (user and user.active):
        handler.redirect(get_login_uri(handler, next_url), abort=True)
    if admin and not user.admin:
        handler.redirect(get_login_uri(handler, next_url), abort=True)
    return user


def authenticate_public(handler):
    return authenticate(handler, required=False, admin=False)


def authenticate_admin(handler):
    return authenticate(handler, required=True, admin=True)


class UserBase(object):
    @webapp2.cached_property
    def session(self):
        return self.session_store.get_session()

    @webapp2.cached_property
    def auth(self):
        return auth.get_auth(request=self.request)

    @webapp2.cached_property
    def user_info(self):
        return self.auth.get_user_by_session()

    @webapp2.cached_property
    def user(self):
        user_model = None
        if self.user_info:
            user_model = self.auth.store.user_model.get_by_id(self.user_info['user_id'])
        return user_model


class UserHandler(JinjaHandler, UserBase):
    @property
    def logged_in(self):
        return self.user is not None

    def logout(self, redirect_url=None):
        redirect_url = redirect_url or webapp2.uri_for('main')
        self.auth.unset_session()
        self.redirect(redirect_url)

    def dispatch(self):
        self.session_store = sessions.get_store(request=self.request)
        try:
            super(UserHandler, self).dispatch()
        finally:
            self.session_store.save_sessions(self.response)

    def get_template_context(self, context=None):
        template_context = super(UserHandler, self).get_template_context(context=context)
        if context:
            template_context.update(context)
        template_context['flashes'] = self.session.get_flashes()
        template_context['request'] = self.request
        template_context['user'] = self.user
        return template_context

    def head(self):
        self.get()
        self.response.clear()


class MojangLoginForm(form.Form):
    username = fields.StringField(u'Username', validators=[validators.DataRequired()])
    password = fields.PasswordField(u'Password', validators=[validators.DataRequired()])


class LoginHandler(UserHandler):
    def get(self):
        next_url = self.request.params.get('next_url', webapp2.uri_for('main'))
        if self.logged_in:
            if self.user.active:
                self.redirect(next_url or webapp2.uri_for('main'))
            else:
                self.redirect(webapp2.uri_for('main'))
            return
        gae_login_uri = get_gae_login_uri(self, next_url)
        form = MojangLoginForm()
        context = {
            'gae_login_uri': gae_login_uri,
            'mojang_login_form': form,
            'next_url': next_url
        }
        self.render_template('login.html', context=context)


def send_new_user_email(user):
    subject = "User registration: {0}".format(user.name)
    body = "User registration: {0}\nStatus: {1}\n\nYou can click the URL below to {2}, edit, or remove the user account.\n\n{3}".format(  # noqa
        user.name,
        'ACTIVE' if user.active else 'INACTIVE',
        'inactivate' if user.active else 'activate',
        webapp2.uri_for('user', key=user.key.urlsafe(), _scheme='https')
    )
    User.send_admin_email(subject, body)


class AuthHandler(UserHandler):
    def login_auth_id(self, auth_id, is_admin=False, email=None, nickname=None, username=None):
        next_url = self.request.params.get('next_url', None)
        if self.logged_in:
            self.redirect(next_url or webapp2.uri_for('main'))
            return
        user = self.auth.store.user_model.get_by_auth_id(auth_id)
        if user:
            self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)
        else:
            ok = False
            if username is not None:
                user = User.lookup(username=username)
                if user is not None:
                    user.add_auth_id(auth_id)
                    ok = True
            if not ok:
                ok, user = self.auth.store.user_model.create_user(auth_id, email=email, nickname=nickname)
                if ok:
                    send_new_user_email(user)
            if ok:
                self.auth.set_session(self.auth.store.user_to_dict(user), remember=True)
                next_url = webapp2.uri_for('user_profile', next_url=next_url or webapp2.uri_for('main'))
            else:
                self.auth.unset_session()
                user = None
                next_url = None
        if user:
            if is_admin and not (user.active and user.admin):
                user.active = True
                user.admin = True
            user.last_login = datetime.datetime.utcnow()
            if username is not None:
                user.add_username(username)
            user.put()
            if ON_SERVER:
                time.sleep(2)
            if not user.active:
                next_url = webapp2.uri_for('main')
        self.redirect(next_url or webapp2.uri_for('main'))


class GoogleAppEngineUserHandler(AuthHandler):
    def login_callback(self):
        gae_user = users.get_current_user()
        auth_id = User.get_gae_user_auth_id(gae_user=gae_user) if gae_user else None
        is_admin = users.is_current_user_admin()
        email = gae_user.email() if gae_user else None
        nickname = gae_user.nickname() if gae_user else None
        self.login_auth_id(auth_id, is_admin=is_admin, email=email, nickname=nickname)


def mojang_authentication(username, password):
    u = uuid = access_token = None
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "agent": {
            "name": "Minecraft",
            "version": 1
        },
        "username": username,
        "password": password,
        "clientToken": "{0}.appspot.com".format(app_identity.get_application_id())
    }
    result = urlfetch.fetch(
        url="https://authserver.mojang.com/authenticate",
        payload=json.dumps(payload),
        method=urlfetch.POST,
        headers=headers
    )
    data = json.loads(result.content)
    access_token = data.get('accessToken', None)
    if access_token:
        selectedProfile = data.get('selectedProfile', None)
        if selectedProfile:
            uuid = selectedProfile['id']
            u = selectedProfile['name']
        else:
            availableProfiles = data.get('availableProfiles', None)
            if availableProfiles:
                selectedProfile = availableProfiles[0]
                uuid = selectedProfile['id']
                u = selectedProfile['name']
    else:
        message = data.get('errorMessage', None)
        if message:
            raise MojangException(message)
    return u, uuid, access_token


class MojangUserHandler(AuthHandler):
    def post(self):
        next_url = self.request.params.get('next_url', webapp2.uri_for('main'))
        form = MojangLoginForm(self.request.POST)
        if form.validate():
            username = form.username.data
            password = form.password.data
            try:
                u, uuid, access_token = mojang_authentication(username, password)
                if u:
                    email = None
                    if '@' in username:
                        email = username
                    auth_id = User.get_mojang_auth_id(uuid=uuid)
                    self.login_auth_id(auth_id, nickname=u, username=u, email=email)
                    self.redirect(next_url)
                    return
            except MojangException as me:
                message = u'Mojang authentication failed (Reason: {0}).'.format(me)
                self.session.add_flash(message, level='error')
        gae_login_uri = get_gae_login_uri(self, next_url)
        context = {
            'gae_login_uri': gae_login_uri,
            'mojang_login_form': form,
            'next_url': next_url
        }
        self.render_template('login.html', context=context)


routes = [
    RedirectRoute('/login', handler='user_auth.LoginHandler', name='login'),
    RedirectRoute('/logout', handler='user_auth.UserHandler:logout', name='logout'),
    RedirectRoute('/gae_login_callback', handler='user_auth.GoogleAppEngineUserHandler:login_callback', name='gae_login_callback'),  # noqa
    RedirectRoute('/mojang_login', handler='user_auth.MojangUserHandler', name='mojang_login')
]
