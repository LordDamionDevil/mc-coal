import fix_dev_path  # noqa

import json

from google.appengine.api import channel as gae_channel

from base_test import BaseTest
from web_test import WebTest

import minimock

import channel
import models


class ServerChannelsTest(BaseTest):
    def setUp(self):
        super(ServerChannelsTest, self).setUp()

    def test_get_numeric_client_id(self):
        server = models.Server.create()
        models.User.create_user('1234', email='bill@example.com')
        user = models.User.lookup(email='bill@example.com')
        client_id = models.ServerChannels.get_client_id([server.key], user)
        self.assertTrue(client_id.startswith('{0}:{1}'.format(server.key.id(), user.key.id())))
        self.assertEqual([server.key], models.ServerChannels.get_server_keys(client_id))

    def test_get_alpha_client_id(self):
        server = models.Server.create(id='test_server')
        models.User.create_user('1234', email='bill@example.com')
        user = models.User.lookup(email='bill@example.com')
        client_id = models.ServerChannels.get_client_id([server.key], user)
        self.assertTrue(client_id.startswith('{0}:{1}'.format(server.key.id(), user.key.id())))
        self.assertEqual([server.key], models.ServerChannels.get_server_keys(client_id))


class SendLogLineTest(BaseTest):
    INTERESTING_LOG_LINE = '2013-03-23 19:01:19 [INFO] <quazifene> is there anybody in there?'
    UNINTERESTING_LOG_LINE = '2013-03-21 22:27:00 [INFO] Preparing spawn area: 35%'

    def setUp(self):
        super(SendLogLineTest, self).setUp()
        self.server = models.Server.create()
        models.User.create_user('1234', email='bill@example.com')
        self.user = models.User.lookup(email='bill@example.com')
        self.interesting_log_line = models.LogLine.create(self.server, self.INTERESTING_LOG_LINE, 'US/Central')
        self.uninteresting_log_line = models.LogLine.create(self.server, self.UNINTERESTING_LOG_LINE, 'US/Central')
        self.tracker = minimock.TraceTracker()
        minimock.mock('channel.ServerChannels.get_client_ids', returns=['client_id'], tracker=None)
        minimock.mock('channel.ServerChannels.send_message', tracker=self.tracker)

    def tearDown(self):
        super(SendLogLineTest, self).tearDown()
        minimock.restore()

    def test_sends_interesting_log_lines(self):
        self.interesting_log_line.send_message()
        minimock.assert_same_trace(self.tracker, "Called channel.ServerChannels.send_message({0}, u'chat')".format(self.interesting_log_line))

    def test_does_not_send_uninteresting_log_lines(self):
        self.uninteresting_log_line.send_message()
        minimock.assert_same_trace(self.tracker, '')

    def test_sends_message_to_all_connected_clients(self):
        minimock.restore()
        self.tracker = minimock.TraceTracker()
        models.User.create_user('4321', email='joe@example.com')
        user = models.User.lookup(email='bill@example.com')
        client_id = '{0}:{1}:1234.5678'.format(self.server.key.id(), self.user.key.id())
        client_id2 = '{0}:{1}:1234.5678'.format(self.server.key.id(), user.key.id())
        minimock.mock('channel.ServerChannels.get_client_ids', returns=[client_id, client_id2], tracker=None)
        minimock.mock('gae_channel.send_message', tracker=self.tracker)
        self.interesting_log_line.send_message()
        js = '{"username": "quazifene", "achievement_message": null, "chat": "is there anybody in there?", "time": "12:01am", "date": "Mar 24, 2013", "event": "chat", "death_message": null}'
        trace = "Called gae_channel.send_message(\n    '{0}',\n    '{1}')".format(client_id, js)
        trace += "\nCalled gae_channel.send_message(\n    '{0}',\n    '{1}')".format(client_id, js)
        minimock.assert_same_trace(self.tracker, trace)

    def test_sends_log_line_data_as_json(self):
        minimock.restore()
        self.user.timezone_name = 'US/Pacific'
        self.user.put()
        self.tracker = minimock.TraceTracker()
        client_id = '{0}:{1}:1234.5678'.format(self.server.key.id(), self.user.key.id())
        minimock.mock('channel.ServerChannels.get_client_ids', returns=[client_id], tracker=None)
        minimock.mock('gae_channel.send_message', tracker=self.tracker)
        js = '{"username": "quazifene", "achievement_message": null, "chat": "is there anybody in there?", "time": "05:01pm", "date": "Mar 23, 2013", "event": "chat", "death_message": null}'
        self.interesting_log_line.send_message()
        minimock.assert_same_trace(self.tracker, "Called gae_channel.send_message('{0}','{1}')".format(client_id, js))
        log_line = json.loads(js)
        self.assertEqual('chat', log_line['event'])
        self.assertEqual('Mar 23, 2013', log_line['date'])
        self.assertEqual('05:01pm', log_line['time'])
        self.assertEqual('quazifene', log_line['username'])
        self.assertEqual('is there anybody in there?', log_line['chat'])
        self.assertEqual(None, log_line['death_message'])


class ChannelHandlerTest(BaseTest, WebTest):
    APPLICATION = channel.application

    def tearDown(self):
        super(ChannelHandlerTest, self).tearDown()
        minimock.restore()


class ConnectedHandlerTest(ChannelHandlerTest):
    def test_returns_200_OK(self):
        response = self.post('/_ah/channel/connected/', params={'from': 'client-id'})
        self.assertOK(response)

    def test_adds_client_id_to_lookup_store(self):
        tracker = minimock.TraceTracker()
        minimock.mock('channel.ServerChannels.add_client_id', tracker=tracker)
        self.post('/_ah/channel/connected/', params={'from': 'client-id'})
        minimock.assert_same_trace(tracker, "Called channel.ServerChannels.add_client_id(u'client-id')")


class DisconnectedHandlerTest(ChannelHandlerTest):
    def test_returns_200_OK(self):
        response = self.post('/_ah/channel/disconnected/', params={'from': 'client-id'})
        self.assertOK(response)

    def test_removes_client_id_from_lookup_store(self):
        tracker = minimock.TraceTracker()
        minimock.mock('channel.ServerChannels.remove_client_id', tracker=tracker)
        self.post('/_ah/channel/disconnected/', params={'from': 'client-id-1'})
        minimock.assert_same_trace(tracker, "Called channel.ServerChannels.remove_client_id(u'client-id-1')")
