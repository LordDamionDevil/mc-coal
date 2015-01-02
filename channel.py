import datetime
import logging
import random
import time

from google.appengine.api import channel
from google.appengine.ext import ndb

from webapp2 import WSGIApplication, RequestHandler, Route
from webapp2_extras.json import json

from filters import datetime_filter


KEY_NAME = 'channels'


class ServerChannels(ndb.Model):
    client_ids = ndb.StringProperty(repeated=True)
    created = ndb.DateTimeProperty(auto_now_add=True)
    updated = ndb.DateTimeProperty(auto_now=True)

    @classmethod
    def get_client_id(cls, server_keys, user):
        string_id = '.'.join(
            server_key.string_id() or '{0}'.format(server_key.integer_id()) for server_key in server_keys
        )
        return '{0}:{1}:{2}{3}'.format(
            string_id,
            user.key.id(),
            int(time.time()),
            random.randrange(999)
        )

    @classmethod
    def get_server_keys(cls, client_id):
        key_ids = client_id[:client_id.find(':')]
        server_keys = []
        for key_id in key_ids.split('.'):
            try:
                key_id = int(key_id)
            except ValueError:
                pass
            server_keys.append(ndb.Key('Server', key_id))
        return server_keys

    @classmethod
    def get_user_key(cls, client_id):
        i = client_id.find(':')
        key_id = client_id[i+1:client_id.find(':', i+1)]
        try:
            key_id = int(key_id)
        except ValueError:
            pass
        return ndb.Key('User', key_id)

    @classmethod
    def get_key(cls, server_key):
        return ndb.Key(cls, KEY_NAME, parent=server_key)

    @classmethod
    def get_client_ids(cls, server_key):
        server_channels = cls.get_key(server_key).get()
        if server_channels is not None:
            return server_channels.client_ids
        return []

    @classmethod
    def create_channel(cls, server_keys, user):
        return channel.create_channel(cls.get_client_id(server_keys, user))

    @classmethod
    def send_message(cls, log_line, event):
        message = {
            'event': event,
            'date': datetime_filter(log_line.timestamp, format='%b %d, %Y'),
            'time': datetime_filter(log_line.timestamp, format='%I:%M%p'),
            'username': log_line.username,
            'chat': log_line.chat,
            'death_message': log_line.death_message,
            'achievement_message': log_line.achievement_message
        }
        client_ids = cls.get_client_ids(log_line.server_key)
        if client_ids:
            for client_id in client_ids:
                try:
                    user = cls.get_user_key(client_id).get()
                    if user is not None:
                        timezone = user.timezone
                        message['date'] = datetime_filter(log_line.timestamp, format='%b %d, %Y', timezone=timezone)
                        message['time'] = datetime_filter(log_line.timestamp, format='%I:%M%p', timezone=timezone)
                        message_json = json.dumps(message)
                        channel.send_message(client_id, message_json)
                except:
                    pass

    @classmethod
    def send_status(cls, server):
        client_ids = cls.get_client_ids(server.key)
        if client_ids:
            last_ping = datetime.datetime.utcnow()
            message = {
                'event': "SERVER_STATUS",
                'server_id': server.key.id(),
                'date': datetime_filter(last_ping, format='%b %d, %Y') if last_ping else None,
                'time': datetime_filter(last_ping, format='%I:%M%p') if last_ping else None,
                'status': server.status,
                'is_gce': server.is_gce,
                'address': server.address,
                'server_day': server.server_day,
                'server_time': server.server_time,
                'is_raining': server.is_raining,
                'is_thundering': server.is_thundering,
                'is_running': server.is_running,
                'is_stopped': server.is_stopped,
                'is_queued_start': server.is_queued_start,
                'is_queued_restart': server.is_queued_restart,
                'is_queued_stop': server.is_queued_stop,
                'is_queued': server.is_queued,
                'is_loading': server.is_loading,
                'is_saving': server.is_saving,
                'completed': server.completed,
                'idle_shutdown_in': None,
                'is_unknown': server.is_unknown,
                'is_eula_agree': server.mc_properties.eula_agree,
                'num_overloads': server.num_overloads
            }
            idle_shutdown_in = server.idle_shutdown_in
            if idle_shutdown_in:
                if idle_shutdown_in.total_seconds() > 60:
                    days = idle_shutdown_in.days
                    hours = idle_shutdown_in.seconds / 3600
                    mins = (idle_shutdown_in.seconds % 3600) / 60
                    shutdown_text = "Pausing in ~"
                    if days:
                        shutdown_text += "{0}d".format(days)
                    if hours:
                        shutdown_text += "{0}h".format(hours)
                    shutdown_text += "{0}m".format(mins)
                else:
                    shutdown_text = "Pause imminent!"
                message['idle_shutdown_in'] = shutdown_text
            for client_id in client_ids:
                try:
                    user = cls.get_user_key(client_id).get()
                    if user is not None:
                        if last_ping is not None:
                            timezone = user.timezone
                            message['date'] = datetime_filter(last_ping, format='%b %d, %Y', timezone=timezone)
                            message['time'] = datetime_filter(last_ping, format='%I:%M:%S%p', timezone=timezone)
                        message['username'] = user.get_server_username(server.key) or user.name
                        message['admin'] = user.admin
                        message_json = json.dumps(message)
                        channel.send_message(client_id, message_json)
                except:
                    pass

    @classmethod
    def add_client_id(cls, client_id):
        server_keys = cls.get_server_keys(client_id)
        server_channels_to_put = []
        for server_key in server_keys:
            server_channels = cls.get_or_insert(KEY_NAME, parent=server_key)
            if server_channels is not None and client_id not in server_channels.client_ids:
                server_channels.client_ids.append(client_id)
                server_channels_to_put.append(server_channels)
        if server_channels_to_put:
            ndb.put_multi(server_channels_to_put)

    @classmethod
    def remove_client_id(cls, client_id):
        server_keys = cls.get_server_keys(client_id)
        server_channels_to_put = []
        for server_key in server_keys:
            server_channels = cls.get_key(server_key).get()
            if server_channels is not None:
                try:
                    server_channels.client_ids.remove(client_id)
                    server_channels_to_put.append(server_channels)
                except ValueError:
                    pass
        if server_channels_to_put:
            ndb.put_multi(server_channels_to_put)


class ConnectedHandler(RequestHandler):
    def post(self):
        client_id = self.request.get('from')
        logging.info(u'channel client %s connected!' % client_id)
        ServerChannels.add_client_id(client_id)


class DisconnectedHandler(RequestHandler):
    def post(self):
        client_id = self.request.get('from')
        logging.info(u'channel client %s disconnected!' % client_id)
        ServerChannels.remove_client_id(client_id)


application = WSGIApplication(
    [
        Route('/_ah/channel/connected/', ConnectedHandler),
        Route('/_ah/channel/disconnected/', DisconnectedHandler),
    ],
    debug=False
)
