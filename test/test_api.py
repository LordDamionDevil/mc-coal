import fix_dev_path  # noqa

import datetime
import json
import logging
import os
import random
import string

from google.appengine.ext import blobstore, testbed, ndb

import minimock

import image  # noqa
import main
import models
import patterns
from test_oauth import OauthTest


TIME_ZONE = 'America/Chicago'
LOG_LINE = 'Test line'
IMAGE_PATH = 'static/img/coal_sprite.png'

TIME_STAMP_LOG_LINE = '2012-10-07 15:10:09 [INFO] Preparing level "world"'
SERVER_START_LOG_LINE = '2012-10-15 16:05:00 [INFO] Starting minecraft server version 1.3.2'
SERVER_STOP_LOG_LINE = '2012-10-15 16:26:11 [INFO] Stopping server'
OVERLOADED_LOG_LINE = "2012-10-21 00:01:46 [WARNING] Can't keep up! Did the system time change, or is the server overloaded?"  # noqa
OVERLOADED_LOG_LINE_2 = "2014-02-13 22:07:55 [WARN] Can't keep up! Did the system time change, or is the server overloaded? Running 2850ms behind, skipping 57 tick(s)"  # noqa
CHAT_LOG_LINE = '2012-10-09 20:46:06 [INFO] <vesicular> yo yo'
CHAT_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] [Server] hello'
CHAT_LOG_LINE_3 = '2012-10-09 20:46:05 [INFO] [Server] <vesicular> yo yo'
CHAT_LOG_LINE_4 = '2012-10-09 20:46:05 [INFO] [Server] <t@gmail.com> yo yo'
DISCONNECT_LOG_LINE = '2012-10-09 20:50:08 [INFO] gumptionthomas lost connection: blah'
DISCONNECT_LOG_LINE_2 = '2013-03-13 23:03:39 [INFO] gumptionthomas lost connection: blah'
CONNECT_LOG_LINE = '2012-10-09 19:52:55 [INFO] gumptionthomas[/192.168.11.198:59659] logged in with entity id 14698 at (221.41534292614716, 68.0, 239.43154415221068)'  # noqa
CONNECT_LOG_LINE_2 = '2013-03-08 21:06:34 [INFO] gumptionthomas[/192.168.11.205:50167] logged in with entity id 3583968 at (1168.5659371692745, 63.0, -779.6390153758603)'  # noqa
ALL_LOG_LINES = [
    LOG_LINE, TIME_STAMP_LOG_LINE, SERVER_START_LOG_LINE, SERVER_STOP_LOG_LINE, OVERLOADED_LOG_LINE,
    CHAT_LOG_LINE, CHAT_LOG_LINE_2, CHAT_LOG_LINE_3, DISCONNECT_LOG_LINE, DISCONNECT_LOG_LINE_2,
    CONNECT_LOG_LINE, CONNECT_LOG_LINE_2
]
TIMESTAMP_LOG_LINES = [
    TIME_STAMP_LOG_LINE, SERVER_START_LOG_LINE, SERVER_STOP_LOG_LINE, OVERLOADED_LOG_LINE,
    CHAT_LOG_LINE, CHAT_LOG_LINE_2, CHAT_LOG_LINE_3, DISCONNECT_LOG_LINE, DISCONNECT_LOG_LINE_2,
    CONNECT_LOG_LINE, CONNECT_LOG_LINE_2
]
TIMESTAMP_LOG_LINES_CRON = [
    CHAT_LOG_LINE_2, DISCONNECT_LOG_LINE_2, CONNECT_LOG_LINE_2, OVERLOADED_LOG_LINE, SERVER_STOP_LOG_LINE,
    SERVER_START_LOG_LINE, DISCONNECT_LOG_LINE, CHAT_LOG_LINE, CHAT_LOG_LINE_3, CONNECT_LOG_LINE,
    TIME_STAMP_LOG_LINE
]
CHAT_LOG_LINES_CRON = [CHAT_LOG_LINE_2, CHAT_LOG_LINE, CHAT_LOG_LINE_3]
ANVIL_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas was squashed by a falling anvil'
PRICKED_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas was pricked to death'
CACTUS_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas walked into a cactus whilst trying to escape Skeleton'  # noqa
CACTUS_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas walked into a cactus whilst trying to escape vesicular'  # noqa
SHOT_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas was shot by arrow'
DROWNED_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas drowned'
DROWNED_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas drowned whilst trying to escape Skeleton'
DROWNED_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas drowned whilst trying to escape vesicular'
BLEW_UP_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas blew up'
BLEW_UP_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas was blown up by Creeper'
BLEW_UP_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas was blown up by vesicular'
FALLING_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas hit the ground too hard'
FALLING_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas fell off a ladder'
FALLING_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas fell off some vines'
FALLING_DEATH_LOG_LINE_4 = '2013-04-03 10:27:55 [INFO] gumptionthomas fell out of the water'
FALLING_DEATH_LOG_LINE_5 = '2013-04-03 10:27:55 [INFO] gumptionthomas fell from a high place'
FALLING_DEATH_LOG_LINE_6 = '2013-04-03 10:27:55 [INFO] gumptionthomas fell into a patch of fire'
FALLING_DEATH_LOG_LINE_7 = '2013-04-03 10:27:55 [INFO] gumptionthomas fell into a patch of cacti'
FALLING_DEATH_LOG_LINE_8 = '2013-04-03 10:27:55 [INFO] gumptionthomas was doomed to fall by Skeleton'
FALLING_DEATH_LOG_LINE_9 = '2013-04-03 10:27:55 [INFO] gumptionthomas was doomed to fall by vesicular'
FALLING_DEATH_LOG_LINE_10 = '2013-04-03 10:27:55 [INFO] gumptionthomas was shot off some vines by Skeleton'
FALLING_DEATH_LOG_LINE_11 = '2013-04-03 10:27:55 [INFO] gumptionthomas was shot off some vines by vesicular'
FALLING_DEATH_LOG_LINE_12 = '2013-04-03 10:27:55 [INFO] gumptionthomas was blown from a high place by Creeper'
FIRE_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas went up in flames'
FIRE_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas burned to death'
FIRE_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas was burnt to a crisp whilst fighting Skeleton'
FIRE_DEATH_LOG_LINE_4 = '2013-04-03 10:27:55 [INFO] gumptionthomas was burnt to a crisp whilst fighting vesicular'
FIRE_DEATH_LOG_LINE_5 = '2013-04-03 10:27:55 [INFO] gumptionthomas walked into a fire whilst fighting Skeleton'
FIRE_DEATH_LOG_LINE_6 = '2013-04-03 10:27:55 [INFO] gumptionthomas walked into a fire whilst fighting vesicular'
MOB_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas was slain by Skeleton'
MOB_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas was shot by Skeleton'
MOB_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas was fireballed by Ghast'
MOB_DEATH_LOG_LINE_4 = '2013-04-03 10:27:55 [INFO] gumptionthomas was killed by Whitch'
MOB_DEATH_LOG_LINE_5 = '2013-04-03 10:27:55 [INFO] gumptionthomas got finished off by Skeleton using Bow'
MOB_DEATH_LOG_LINE_6 = '2013-04-03 10:27:55 [INFO] gumptionthomas was slain by Skeleton using Bow'
LAVA_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas tried to swim in lava'
LAVA_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas tried to swim in lava while trying to escape Skeleton'  # noqa
LAVA_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas tried to swim in lava while trying to escape vesicular'  # noqa
OTHER_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas died'
PVP_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas got finished off by vesicular using Bow'
PVP_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas was slain by vesicular using Bow'
PVP_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas was shot by vesicular'
PVP_DEATH_LOG_LINE_4 = '2013-04-03 10:27:55 [INFO] gumptionthomas was killed by vesicular'
POTION_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas was killed by magic'
STARVATION_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas starved to death'
SUFFOCATION_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas suffocated in a wall'
THORNS_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas was killed while trying to hurt Skeleton'
THORNS_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas was killed while trying to hurt vesicular'
UNUSED_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas was pummeled by vesicular'
VOID_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas fell out of the world'
VOID_DEATH_LOG_LINE_2 = '2013-04-03 10:27:55 [INFO] gumptionthomas fell from a high place and fell out of the world'
VOID_DEATH_LOG_LINE_3 = '2013-04-03 10:27:55 [INFO] gumptionthomas was knocked into the void by Skeleton'
VOID_DEATH_LOG_LINE_4 = '2013-04-03 10:27:55 [INFO] gumptionthomas was knocked into the void by vesicular'
WITHER_DEATH_LOG_LINE = '2013-04-03 10:27:55 [INFO] gumptionthomas withered away'
DEATH_LOG_LINES_CRON = [ANVIL_DEATH_LOG_LINE, PRICKED_DEATH_LOG_LINE, CACTUS_DEATH_LOG_LINE]
ACHIEVEMENT_LOG_LINE = '2013-11-10 17:19:04 [INFO] gumptionthomas has just earned the achievement [Getting an Upgrade]'

DEATH_LOG_LINES = [
    (ANVIL_DEATH_LOG_LINE, "was squashed by a falling anvil", None, None),
    (PRICKED_DEATH_LOG_LINE, "was pricked to death", None, None),
    (CACTUS_DEATH_LOG_LINE, "walked into a cactus whilst trying to escape Skeleton", "Skeleton", None),
    (CACTUS_DEATH_LOG_LINE_2, "walked into a cactus whilst trying to escape vesicular", "vesicular", None),
    (SHOT_DEATH_LOG_LINE, "was shot by arrow", None, None),
    (DROWNED_DEATH_LOG_LINE, "drowned", None, None),
    (DROWNED_DEATH_LOG_LINE_2, "drowned whilst trying to escape Skeleton", "Skeleton", None),
    (DROWNED_DEATH_LOG_LINE_3, "drowned whilst trying to escape vesicular", "vesicular", None),
    (BLEW_UP_DEATH_LOG_LINE, "blew up", None, None),
    (BLEW_UP_DEATH_LOG_LINE_2, "was blown up by Creeper", "Creeper", None),
    (BLEW_UP_DEATH_LOG_LINE_3, "was blown up by vesicular", "vesicular", None),
    (FALLING_DEATH_LOG_LINE, "hit the ground too hard", None, None),
    (FALLING_DEATH_LOG_LINE_2, "fell off a ladder", None, None),
    (FALLING_DEATH_LOG_LINE_3, "fell off some vines", None, None),
    (FALLING_DEATH_LOG_LINE_4, "fell out of the water", None, None),
    (FALLING_DEATH_LOG_LINE_5, "fell from a high place", None, None),
    (FALLING_DEATH_LOG_LINE_6, "fell into a patch of fire", None, None),
    (FALLING_DEATH_LOG_LINE_7, "fell into a patch of cacti", None, None),
    (FALLING_DEATH_LOG_LINE_8, "was doomed to fall by Skeleton", "Skeleton", None),
    (FALLING_DEATH_LOG_LINE_9, "was doomed to fall by vesicular", "vesicular", None),
    (FALLING_DEATH_LOG_LINE_10, "was shot off some vines by Skeleton", "Skeleton", None),
    (FALLING_DEATH_LOG_LINE_11, "was shot off some vines by vesicular", "vesicular", None),
    (FALLING_DEATH_LOG_LINE_12, "was blown from a high place by Creeper", "Creeper", None),
    (FIRE_DEATH_LOG_LINE, "went up in flames", None, None),
    (FIRE_DEATH_LOG_LINE_2, "burned to death", None, None),
    (FIRE_DEATH_LOG_LINE_3, "was burnt to a crisp whilst fighting Skeleton", "Skeleton", None),
    (FIRE_DEATH_LOG_LINE_4, "was burnt to a crisp whilst fighting vesicular", "vesicular", None),
    (FIRE_DEATH_LOG_LINE_5, "walked into a fire whilst fighting Skeleton", "Skeleton", None),
    (FIRE_DEATH_LOG_LINE_6, "walked into a fire whilst fighting vesicular", "vesicular", None),
    (MOB_DEATH_LOG_LINE, "was slain by Skeleton", "Skeleton", None),
    (MOB_DEATH_LOG_LINE_2, "was shot by Skeleton", "Skeleton", None),
    (MOB_DEATH_LOG_LINE_3, "was fireballed by Ghast", "Ghast", None),
    (MOB_DEATH_LOG_LINE_4, "was killed by Whitch", "Whitch", None),
    (MOB_DEATH_LOG_LINE_5, "got finished off by Skeleton using Bow", "Skeleton", "Bow"),
    (MOB_DEATH_LOG_LINE_6, "was slain by Skeleton using Bow", "Skeleton", "Bow"),
    (LAVA_DEATH_LOG_LINE, "tried to swim in lava", None, None),
    (LAVA_DEATH_LOG_LINE_2, "tried to swim in lava while trying to escape Skeleton", "Skeleton", None),
    (LAVA_DEATH_LOG_LINE_3, "tried to swim in lava while trying to escape vesicular", "vesicular", None),
    (OTHER_DEATH_LOG_LINE, "died", None, None),
    (PVP_DEATH_LOG_LINE, "got finished off by vesicular using Bow", "vesicular", "Bow"),
    (PVP_DEATH_LOG_LINE_2, "was slain by vesicular using Bow", "vesicular", "Bow"),
    (PVP_DEATH_LOG_LINE_3, "was shot by vesicular", "vesicular", None),
    (PVP_DEATH_LOG_LINE_4, "was killed by vesicular", "vesicular", None),
    (POTION_DEATH_LOG_LINE, "was killed by magic", None, None),
    (STARVATION_DEATH_LOG_LINE, "starved to death", None, None),
    (SUFFOCATION_DEATH_LOG_LINE, "suffocated in a wall", None, None),
    (THORNS_DEATH_LOG_LINE, "was killed while trying to hurt Skeleton", "Skeleton", None),
    (THORNS_DEATH_LOG_LINE_2, "was killed while trying to hurt vesicular", "vesicular", None),
    (UNUSED_DEATH_LOG_LINE, "was pummeled by vesicular", "vesicular", None),
    (VOID_DEATH_LOG_LINE, "fell out of the world", None, None),
    (VOID_DEATH_LOG_LINE_2, "fell from a high place and fell out of the world", None, None),
    (VOID_DEATH_LOG_LINE_3, "was knocked into the void by Skeleton", "Skeleton", None),
    (VOID_DEATH_LOG_LINE_4, "was knocked into the void by vesicular", "vesicular", None),
    (WITHER_DEATH_LOG_LINE, "withered away", None, None),
]

ACHIEVEMENT_LOG_LINES = [ACHIEVEMENT_LOG_LINE]

COLOR_CODE_CHAT_LOG_LINE = u'2012-10-09 20:46:06 [INFO] <\xa7bvesicular\xa7r> yo yo'
COLOR_CODE_PVP_LOG_LINE = u'2013-04-03 10:27:55 [INFO] \xa7agumptionthomas\xa7r got finished off by \xa7bvesicular\xa7r using Bow'

ADMIN_EMAIL = 'admin@example.com'

NUM_PLAYER_FIELDS = 7
NUM_USER_FIELDS = 9
NUM_SERVER_FIELDS = 14
NUM_SERVER_PROPERTIES_FIELDS = 32
NUM_PLAY_SESSION_FIELDS = 12
NUM_CHAT_FIELDS = 10
NUM_DEATH_FIELDS = 10
NUM_ACHIEVEMENT_FIELDS = 11
NUM_LOG_LINE_FIELDS = 15
NUM_SCREENSHOT_FIELDS = 8


class ApiTest(OauthTest):
    APPLICATION = main.application
    URL = None
    ALLOWED = []

    @property
    def url(self):
        return self.URL

    def setUp(self):
        super(ApiTest, self).setUp()
        self.server = models.Server.create()
        self.access_token, self.refresh_token = self.get_tokens()

    def tearDown(self):
        super(ApiTest, self).tearDown()
        logging.disable(logging.NOTSET)

    def assertCreated(self, response):
        error = u'Response did not return a 201 CREATED (status code was {0})\nBody: {1}'.format(
            response.status_int, response.body
        )
        self.assertEqual(response.status_int, 201, error)

    def assertAccepted(self, response):
        error = u'Response did not return a 202 ACCEPTED (status code was {0})\nBody: {1}'.format(
            response.status_int, response.body
        )
        self.assertEqual(response.status_int, 202, error)

    def assertMethodNotAllowed(self, response):
        error = u'Response did not return a 405 METHOD NOT ALLOWED (status code was {0})\nBody: {1}'.format(
            response.status_int, response.body
        )
        self.assertEqual(response.status_int, 405, error)

    def get(self, url=None, params=None, headers=None, bearer_token=None):
        url = url or self.url
        return super(ApiTest, self).get(
            url,
            params=params,
            headers=headers,
            bearer_token=bearer_token or getattr(self, 'access_token', None)
        )

    def post(self, url=None, params='', headers=None, upload_files=None, bearer_token=None):
        url = url or self.url
        return super(ApiTest, self).post(
            url,
            params=params,
            headers=headers,
            upload_files=upload_files,
            bearer_token=bearer_token or getattr(self, 'access_token', None)
        )

    def post_json(self, params, url=None, json=None, headers=None, bearer_token=None):
        url = url or self.url
        return super(ApiTest, self).post_json(
            url,
            params,
            headers=headers,
            bearer_token=bearer_token or getattr(self, 'access_token', None)
        )

    def test_get_no_auth(self):
        if self.url:
            self.access_token = None
            response = self.get()
            if 'GET' in self.ALLOWED:
                self.assertUnauthorized(response)
            else:
                self.assertMethodNotAllowed(response)

    def test_post_no_auth(self):
        if self.url:
            self.access_token = None
            response = self.post()
            if 'POST' in self.ALLOWED:
                self.assertUnauthorized(response)
            else:
                self.assertMethodNotAllowed(response)

    def test_get_inactive(self):
        if self.url:
            self.server.active = False
            self.server.put()
            response = self.get()
            if 'GET' in self.ALLOWED:
                self.assertNotFound(response)
            else:
                self.assertMethodNotAllowed(response)


class AgentApiTest(ApiTest):
    def setUp(self):
        super(AgentApiTest, self).setUp()
        self.access_token, self.refresh_token = self.get_agent_tokens()

    def get_agent_tokens(self, email=None):
        agent_client = self.server.agent
        url = '/oauth/v1/token'
        params = {
            'code': agent_client.secret,
            'grant_type': 'authorization_code',
            'client_id': agent_client.client_id,
            'client_secret': agent_client.secret,
            'redirect_uri': '/',
            'scope': 'agent'
        }
        response = self.post(url=url, params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(4, body)
        return (body['access_token'], body['refresh_token'])

    def test_get_unauth(self):
        if self.url:
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.get()
            if 'GET' in self.ALLOWED:
                self.assertUnauthorized(response)
            else:
                self.assertMethodNotAllowed(response)

    def test_post_unauth(self):
        if self.url:
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.post()
            if 'POST' in self.ALLOWED:
                self.assertUnauthorized(response)
            else:
                self.assertMethodNotAllowed(response)


class PingTest(AgentApiTest):
    URL = '/api/v1/agents/ping'
    ALLOWED = ['POST']

    def test_post(self):
        params = {'server_name': 'test'}
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        self.assertEmpty(body['commands'])
        self.assertEqual(models.SERVER_UNKNOWN, models.Server.query().get().status)

    def test_post_no_server_name(self):
        logging.disable(logging.ERROR)
        response = self.post()
        self.assertBadRequest(response)
        body = json.loads(response.body)
        self.assertEqual({u'errors': {u'server_name': [u'This field is required.']}}, body)

    def test_post_server_running(self):
        params = {'server_name': 'test', 'is_server_running': True}
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        self.assertEmpty(body['commands'])
        self.assertTrue(models.Server.query().get().is_running)

    def test_post_server_not_running(self):
        params = {'server_name': 'test', 'is_server_running': False}
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        self.assertEmpty(body['commands'])
        self.assertFalse(models.Server.query().get().is_running)

    def post_level_data(self, now=None, timestamp=None, server_day=None, server_time=None):
        now = now or datetime.datetime.utcnow()
        timestamp = timestamp or now
        params = {
            'server_name': 'test',
            'is_server_running': True,
            'server_day': 10,
            'server_time': 1000,
            'timestamp': timestamp.strftime(u"%Y-%m-%d %H:%M:%S")
        }
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        self.assertEmpty(body['commands'])
        return body

    def test_post_level_data(self):
        self.post_level_data()
        server = models.Server.query().get()
        self.assertTrue(server.is_running)
        self.assertEqual(10, server.last_server_day)
        self.assertEqual(1000, server.last_server_time)
        self.assertEqual(server.last_server_day, server.server_day)
        self.assertLess(abs(server.server_time - server.last_server_time), 100)  # Within 5 seconds

    def test_post_level_data_past(self):
        now = datetime.datetime.utcnow()
        self.post_level_data(now=now, timestamp=now - datetime.timedelta(seconds=20))
        server = models.Server.query().get()
        self.assertTrue(server.is_running)
        self.assertEqual(10, server.last_server_day)
        self.assertEqual(1000, server.last_server_time)
        self.assertEqual(server.last_server_day, server.server_day)
        self.assertGreaterEqual(server.server_time, 1400)

    def test_post_level_data_day_past(self):
        now = datetime.datetime.utcnow()
        self.post_level_data(now=now, timestamp=now - datetime.timedelta(seconds=1220))  # One game day + 400 ticks
        server = models.Server.query().get()
        self.assertTrue(server.is_running)
        self.assertEqual(10, server.last_server_day)
        self.assertEqual(1000, server.last_server_time)
        self.assertEqual(server.last_server_day, server.server_day)
        self.assertGreaterEqual(server.server_time, 1400)

    def test_post_commands(self):
        self.server.status = models.SERVER_RUNNING
        self.server.put()
        commands = []
        for i in range(5):
            command = models.Command.push(self.server.key, 'gumptionthomas', '/say hello world')
            commands.append(command.to_dict)
        params = {'line': TIME_STAMP_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(url=LogLineTest.URL, params=params)
        self.assertCreated(response)
        params = {'server_name': 'test', 'is_server_running': True}
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        self.assertEqual(body['commands'], commands)


class LogLineTest(AgentApiTest):
    URL = '/api/v1/agents/logline'
    ALLOWED = ['POST']

    def test_post_missing_param(self):
        logging.disable(logging.ERROR)
        params = {'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertBadRequest(response)
        body = json.loads(response.body)
        self.assertEqual({u'errors': {u'line': [u'This field is required.']}}, body)
        params = {'line': LOG_LINE}
        response = self.post(params=params)
        self.assertBadRequest(response)
        body = json.loads(response.body)
        self.assertEqual({u'errors': {u'zone': [u'This field is required.']}}, body)
        response = self.post()
        self.assertBadRequest(response)
        body = json.loads(response.body)
        self.assertEqual(
            {u'errors': {u'zone': [u'This field is required.'], u'line': [u'This field is required.']}}, body
        )

    def test_post_log_line(self):
        params = {'line': LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual([u'unknown'], log_line.tags)

    def test_post_time_stamp_log_line(self):
        params = {'line': TIME_STAMP_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(TIME_STAMP_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 7, 20, 10, 9), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual([u'timestamp', u'unknown'], log_line.tags)

    def test_post_server_start_log_line(self):
        params = {'line': SERVER_START_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual('1.3.2', models.Server.query().get().running_version)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(SERVER_START_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 15, 21, 5), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual(patterns.STARTING_TAGS, log_line.tags)

    def test_post_server_stop_log_line(self):
        params = {'line': SERVER_STOP_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(SERVER_STOP_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 15, 21, 26, 11), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual(patterns.STOPPING_TAGS, log_line.tags)

    def test_post_overloaded_log_line(self):
        params = {'line': OVERLOADED_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(OVERLOADED_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 21, 5, 1, 46), log_line.timestamp)
        self.assertEqual('WARNING', log_line.log_level)
        self.assertEqual(patterns.OVERLOADED_TAGS, log_line.tags)

    def test_post_overloaded_log_line_2(self):
        params = {'line': OVERLOADED_LOG_LINE_2, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(OVERLOADED_LOG_LINE_2, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2014, 2, 14, 4, 7, 55), log_line.timestamp)
        self.assertEqual('WARN', log_line.log_level)
        self.assertEqual(patterns.OVERLOADED_TAGS, log_line.tags)

    def test_post_chat_log_line(self):
        params = {'line': CHAT_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(CHAT_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 10, 1, 46, 6), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('vesicular', log_line.username)
        self.assertEqual('yo yo', log_line.chat)
        self.assertEqual(patterns.CHAT_TAGS, log_line.tags)
        self.assertEqual(1, models.Player.query().count())
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNotNone(player)

    def test_post_chat_log_line_2(self):
        params = {'line': CHAT_LOG_LINE_2, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(CHAT_LOG_LINE_2, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2013, 4, 3, 15, 27, 55), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertIsNone(log_line.username)
        self.assertEqual('hello', log_line.chat)
        self.assertEqual(patterns.CHAT_TAGS, log_line.tags)
        self.assertEqual(0, models.Player.query().count())

    def test_post_chat_log_line_3(self):
        params = {'line': CHAT_LOG_LINE_3, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(CHAT_LOG_LINE_3, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 10, 1, 46, 5), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('vesicular', log_line.username)
        self.assertEqual('yo yo', log_line.chat)
        self.assertEqual(patterns.CHAT_TAGS, log_line.tags)
        self.assertEqual(1, models.Player.query().count())
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNotNone(player)

    def test_post_chat_log_line_4(self):
        params = {'line': CHAT_LOG_LINE_4, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(CHAT_LOG_LINE_4, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 10, 1, 46, 5), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('t@gmail.com', log_line.username)
        self.assertEqual('yo yo', log_line.chat)
        self.assertEqual(patterns.CHAT_TAGS, log_line.tags)
        self.assertEqual(0, models.Player.query().count())

    def test_post_disconnect_line(self):
        params = {'line': DISCONNECT_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(DISCONNECT_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 10, 1, 50, 8), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('gumptionthomas', log_line.username)
        self.assertEqual(patterns.LOGOUT_TAGS, log_line.tags)
        self.assertEqual(0, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNone(play_session)
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNone(player.last_login_timestamp)
        self.assertIsNone(player.last_session_duration)
        log_line.key.delete()

        params = {'line': DISCONNECT_LOG_LINE_2, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(DISCONNECT_LOG_LINE_2, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2013, 3, 14, 4, 3, 39), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('gumptionthomas', log_line.username)
        self.assertEqual(patterns.LOGOUT_TAGS, log_line.tags)
        self.assertEqual(0, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNone(play_session)
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNone(player.last_login_timestamp)
        self.assertIsNone(player.last_session_duration)

    def test_post_connect_line(self):
        params = {'line': CONNECT_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(CONNECT_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 10, 0, 52, 55), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('gumptionthomas', log_line.username)
        self.assertEqual(patterns.LOGIN_TAGS, log_line.tags)
        self.assertEqual(1, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNotNone(play_session)
        self.assertEqual(1, models.Player.query().count())
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNotNone(player)
        self.assertTrue(player.is_playing)
        self.assertEqual(datetime.datetime(2012, 10, 10, 0, 52, 55), player.last_login_timestamp)
        self.assertIsNotNone(player.last_session_duration)
        log_line.key.delete()

        params = {'line': CONNECT_LOG_LINE_2, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(CONNECT_LOG_LINE_2, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2013, 3, 9, 3, 6, 34), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('gumptionthomas', log_line.username)
        self.assertEqual(patterns.LOGIN_TAGS, log_line.tags)
        self.assertEqual(2, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNotNone(play_session)
        self.assertEqual(1, models.Player.query().count())
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNotNone(player)
        self.assertTrue(player.is_playing)
        self.assertEqual(datetime.datetime(2013, 3, 9, 3, 6, 34), player.last_login_timestamp)
        self.assertIsNotNone(player.last_session_duration)

    def test_post_all(self):
        for line in ALL_LOG_LINES:
            params = {'line': line, 'zone': TIME_ZONE}
            response = self.post(params=params)
            self.assertCreated(response)
            body = json.loads(response.body)
            self.assertLength(0, body)
        self.assertEqual(len(ALL_LOG_LINES), models.LogLine.query().count())
        self.assertEqual(len(TIMESTAMP_LOG_LINES), models.LogLine.query_latest_with_timestamp(self.server.key).count())
        self.assertEqual(1, models.LogLine.query_by_tags(self.server.key, patterns.OVERLOADED_TAG).count())
        self.assertEqual(3, models.LogLine.query_latest_chats(self.server.key).count())
        self.assertEqual(2, models.LogLine.query_latest_logins(self.server.key).count())
        self.assertEqual(2, models.LogLine.query_latest_logouts(self.server.key).count())

    def test_post_log_line_twice(self):
        params = {'line': LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())

    def test_login_logout(self):
        params = {'line': CONNECT_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        self.assertEqual(1, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNotNone(play_session)
        params = {'line': DISCONNECT_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        self.assertEqual(1, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNone(play_session)

    def test_login_server_stop(self):
        params = {'line': CONNECT_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        self.assertEqual(1, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNotNone(play_session)
        params = {'line': SERVER_STOP_LOG_LINE, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        self.assertEqual(1, models.PlaySession.query().count())
        play_session = models.PlaySession.current(self.server.key, 'gumptionthomas')
        self.assertIsNone(play_session)


class DeathLogLineTest(AgentApiTest):
    URL = '/api/v1/agents/logline'
    ALLOWED = ['POST']

    def test_all_deaths(self):
        for (line, death_message, username_mob, weapon) in DEATH_LOG_LINES:
            params = {'line': line, 'zone': TIME_ZONE}
            response = self.post(params=params)
            self.assertCreated(response)
            self.assertEqual(1, models.LogLine.query().count())
            log_line = models.LogLine.query().get()
            self.assertEqual(line, log_line.line)
            self.assertEqual(TIME_ZONE, log_line.zone)
            self.assertEqual(datetime.datetime(2013, 4, 3, 15, 27, 55), log_line.timestamp)
            self.assertEqual('INFO', log_line.log_level)
            self.assertEqual(
                'gumptionthomas',
                log_line.username,
                msg="Incorrect death username: '{0}' [{1}]".format(log_line.username, log_line.line)
            )
            self.assertEqual(
                death_message,
                log_line.death_message,
                msg="Incorrect death message: '{0}' [{1}]".format(log_line.death_message, log_line.line)
            )
            self.assertEqual(
                username_mob,
                log_line.username_mob,
                msg="Incorrect username/mob: '{0}' [{1}]".format(log_line.username_mob, log_line.line)
            )
            self.assertEqual(weapon, log_line.weapon)
            self.assertEqual(patterns.DEATH_TAGS, log_line.tags)
            self.assertEqual(1, models.Player.query().count())
            player = models.Player.lookup(self.server.key, log_line.username)
            self.assertIsNotNone(player)
            log_line.key.delete()


class AchievementLogLineTest(AgentApiTest):
    URL = '/api/v1/agents/logline'
    ALLOWED = ['POST']

    def test_achievement(self):
        line = ACHIEVEMENT_LOG_LINE
        params = {'line': line, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(line, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2013, 11, 10, 23, 19, 4), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual(
            'gumptionthomas',
            log_line.username,
            msg="Incorrect achievement username: '{0}' [{1}]".format(log_line.username, log_line.line)
        )
        self.assertEqual(
            'Getting an Upgrade',
            log_line.achievement,
            msg="Incorrect achievement: '{0}' [{1}]".format(log_line.achievement, log_line.line)
        )
        self.assertEqual(
            'has just earned the achievement [Getting an Upgrade]',
            log_line.achievement_message,
            msg="Incorrect achievement message: '{0}' [{1}]".format(log_line.achievement, log_line.line)
        )
        self.assertEqual(patterns.ACHIEVEMENT_TAGS, log_line.tags)
        self.assertEqual(1, models.Player.query().count())
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNotNone(player)


class ColorCodeLineTest(AgentApiTest):
    URL = '/api/v1/agents/logline'
    ALLOWED = ['POST']

    def test_post_chat_log_line(self):
        line = COLOR_CODE_CHAT_LOG_LINE.encode('utf8')
        params = {u'line': line, u'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(0, body)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(COLOR_CODE_CHAT_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2012, 10, 10, 1, 46, 6), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual('vesicular', log_line.username)
        self.assertEqual('yo yo', log_line.chat)
        self.assertEqual(patterns.CHAT_TAGS, log_line.tags)
        self.assertEqual(1, models.Player.query().count())
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNotNone(player)

    def test_post_pvp_log_line(self):
        line = COLOR_CODE_PVP_LOG_LINE.encode('utf8')
        params = {'line': line, 'zone': TIME_ZONE}
        response = self.post(params=params)
        self.assertCreated(response)
        self.assertEqual(1, models.LogLine.query().count())
        log_line = models.LogLine.query().get()
        self.assertEqual(COLOR_CODE_PVP_LOG_LINE, log_line.line)
        self.assertEqual(TIME_ZONE, log_line.zone)
        self.assertEqual(datetime.datetime(2013, 4, 3, 15, 27, 55), log_line.timestamp)
        self.assertEqual('INFO', log_line.log_level)
        self.assertEqual(
            'gumptionthomas',
            log_line.username,
            msg=u"Incorrect death username: '{0}' [{1}]".format(log_line.username, log_line.line)
        )
        self.assertEqual(
            u'got finished off by vesicular using Bow',
            log_line.death_message,
            msg=u"Incorrect death message: '{0}' [{1}]".format(log_line.death_message, log_line.line)
        )
        self.assertEqual(
            'vesicular',
            log_line.username_mob,
            msg=u"Incorrect username/mob: '{0}' [{1}]".format(log_line.username_mob, log_line.line)
        )
        self.assertEqual('Bow', log_line.weapon)
        self.assertEqual(patterns.DEATH_TAGS, log_line.tags)
        self.assertEqual(1, models.Player.query().count())
        player = models.Player.lookup(self.server.key, log_line.username)
        self.assertIsNotNone(player)
        log_line.key.delete()


class LastLineTest(AgentApiTest):
    URL = '/api/v1/agents/lastline'
    ALLOWED = ['GET']

    def setUp(self):
        super(LastLineTest, self).setUp()
        self.line = TIME_STAMP_LOG_LINE
        params = {'line': self.line, 'zone': TIME_ZONE}
        response = self.post(url=LogLineTest.URL, params=params)
        self.assertCreated(response)
        self.assertEqual(1, models.LogLine.query().count())

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        lastline = body['lastline']
        self.assertEqual(self.line, lastline)


class MultiPageApiTest(ApiTest):
    def test_get_invalid_cursor(self):
        if self.url:
            logging.disable(logging.ERROR)
            response = self.get(url='{0}?cursor={1}'.format(self.url, 'invalid_cursor_xxx'))
            logging.disable(logging.NOTSET)
            self.assertBadRequest(response)
            body = json.loads(response.body)
            errors = body['errors']
            self.assertEqual({'cursor': 'Invalid cursor invalid_cursor_xxx. Details: Incorrect padding'}, errors)

    def test_get_invalid_size(self):
        if self.url:
            logging.disable(logging.ERROR)
            response = self.get(url='{0}?size={1}'.format(self.url, 0))
            logging.disable(logging.NOTSET)
            self.assertBadRequest(response)
            body = json.loads(response.body)
            errors = body['errors']
            self.assertEqual({'size': ['Number must be between 1 and 50.']}, errors)

    def test_get_empty_size(self):
        if self.url:
            logging.disable(logging.ERROR)
            response = self.get(url='{0}?size={1}'.format(self.url, ''))
            logging.disable(logging.NOTSET)
            self.assertBadRequest(response)
            body = json.loads(response.body)
            errors = body['errors']
            self.assertEqual({'size': ['Not a valid integer value', 'Number must be between 1 and 50.']}, errors)


class KeyApiTest(ApiTest):
    def test_get_invalid_key(self):
        if self.url:
            url = "{0}/{1}".format(self.url, 'invalid_key')
            response = self.get(url=url)
            self.assertNotFound(response)


class UsersTest(MultiPageApiTest):
    URL = '/api/v1/users'
    ALLOWED = ['GET']

    def setUp(self):
        super(UsersTest, self).setUp()
        self.users = [models.User.query().get()]
        for i in range(9):
            user = self.log_in_user(email="user_{0}@test.com".format(i))
            self.log_out_user()
            self.users.append(user)

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        reponse_users = body['users']
        self.assertLength(len(self.users), reponse_users)
        for i, user in enumerate(reponse_users):
            self.assertEqual(NUM_USER_FIELDS, len(user))
            self.assertEqual(self.users[i].usernames, user['usernames'])
            self.assertIsNotNone(user['last_coal_login'])

    def test_get_inactive(self):
        pass


class UserKeyTest(KeyApiTest):
    URL = '/api/v1/users'
    ALLOWED = ['GET']

    @property
    def url(self):
        return "{0}/{1}".format(self.URL, self.user.key.urlsafe())

    def setUp(self):
        super(UserKeyTest, self).setUp()
        self.user = self.log_in_user("user@test.com")
        self.user.last_login = datetime.datetime.utcnow()
        self.user.put()
        self.log_out_user()

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        user = json.loads(response.body)
        self.assertEqual(NUM_USER_FIELDS, len(user))
        self.assertEqual(self.user.key.urlsafe(), user['key'])
        self.assertEqual(self.user.usernames, user['usernames'])
        self.assertIsNotNone(user['last_coal_login'])

    def test_get_self(self):
        self.access_token, self.refresh_token = self.get_tokens(email="user@test.com")
        url = "{0}/{1}".format(self.URL, 'self')
        response = self.get(url=url)
        self.assertOK(response)
        response_user = json.loads(response.body)
        self.assertEqual(NUM_USER_FIELDS, len(response_user))
        self.assertEqual(self.user.key.urlsafe(), response_user['key'])
        self.assertIsNotNone(response_user['last_coal_login'])

    def test_get_inactive(self):
        pass


class AdminApiTest(ApiTest):
    def setUp(self):
        super(AdminApiTest, self).setUp()
        self.log_in_admin(email='admin@test.com')
        self.access_token, self.refresh_token = self.get_tokens(email='admin@test.com')

    def test_get_unauth(self):
        if self.url:
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.get()
            if 'GET' in self.ALLOWED:
                self.assertForbidden(response)
            else:
                self.assertMethodNotAllowed(response)

    def test_post_unauth(self):
        if self.url:
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.post()
            if 'POST' in self.ALLOWED:
                self.assertForbidden(response)
            else:
                self.assertMethodNotAllowed(response)


class ServersTest(AdminApiTest, MultiPageApiTest):
    URL = '/api/v1/servers'
    ALLOWED = ['GET', 'POST']

    def setUp(self):
        super(ServersTest, self).setUp()
        self.servers = [self.server]
        for i in range(4):
            self.servers.append(models.Server.create(name='world {0}'.format(i)))

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        reponse_servers = body['servers']
        self.assertLength(len(self.servers), reponse_servers)
        for i, server in enumerate(reponse_servers):
            self.assertEqual(NUM_SERVER_FIELDS, len(server))
            self.assertEqual(models.SERVER_STOPPED, server['status'])

    def test_get_unauth(self):
        if self.url:
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.get()
            self.assertOK(response)

    def test_get_inactive(self):
        self.server.active = False
        self.server.put()
        response = self.get()
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        reponse_servers = body['servers']
        self.assertLength(len(self.servers)-1, reponse_servers)
        for i, server in enumerate(reponse_servers):
            self.assertEqual(NUM_SERVER_FIELDS, len(server))
            self.assertEqual(models.SERVER_STOPPED, server['status'])

    def test_post(self):
        name = 'Brave New World'
        params = {'name': name, 'gce': False}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(len(self.servers)+1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)
        self.assertFalse(body['gce'])
        self.assertFalse(server.is_gce)

    def test_post_boolean(self):
        name = 'Brave New World'
        params = {'name': name, 'gce': '0'}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(len(self.servers)+1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)
        self.assertFalse(body['gce'])
        self.assertFalse(server.is_gce)

    def test_post_boolean_2(self):
        name = 'Brave New World'
        params = {'name': name, 'gce': 'no'}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(len(self.servers)+1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)
        self.assertFalse(body['gce'])
        self.assertFalse(server.is_gce)

    def test_post_boolean_json(self):
        name = 'Brave New World'
        params = {'name': name, 'gce': '0'}
        response = self.post_json(params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(len(self.servers)+1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)
        self.assertFalse(body['gce'])
        self.assertFalse(server.is_gce)

    def test_post_gce(self):
        name = 'Brave New World'
        params = {'name': name, 'gce': 't'}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(len(self.servers)+1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)
        self.assertTrue(body['gce'])
        self.assertTrue(server.is_gce)

    def test_post_gce_boolean(self):
        name = 'Brave New World'
        params = {'name': name, 'gce': 'yes'}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(len(self.servers)+1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)
        self.assertTrue(body['gce'])
        self.assertTrue(server.is_gce)

    def test_post_gce_boolean_2(self):
        name = 'Brave New World'
        params = {'name': name, 'gce': 'affirmative'}
        response = self.post(params=params)
        self.assertCreated(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(len(self.servers)+1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)
        self.assertTrue(body['gce'])
        self.assertTrue(server.is_gce)

    def test_post_no_name(self):
        params = {'gce': False}
        logging.disable(logging.ERROR)
        response = self.post(params=params)
        logging.disable(logging.NOTSET)
        self.assertBadRequest(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        error = body['errors']
        self.assertLength(1, error)
        self.assertEqual([u'This field is required.'], error['name'])
        self.assertEqual(len(self.servers), models.Server.query().count())

    def test_post_no_gce(self):
        name = 'Brave New World'
        params = {'name': name}
        logging.disable(logging.ERROR)
        response = self.post(params=params)
        logging.disable(logging.NOTSET)
        self.assertBadRequest(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        error = body['errors']
        self.assertLength(1, error)
        self.assertEqual([u'This field is required.'], error['gce'])
        self.assertEqual(len(self.servers), models.Server.query().count())


class ServerKeyTest(AdminApiTest, KeyApiTest):
    URL = '/api/v1/servers'
    ALLOWED = ['GET', 'POST']

    @property
    def url(self):
        return "{0}/{1}".format(self.URL, self.server.key.urlsafe())

    def setUp(self):
        super(ServerKeyTest, self).setUp()

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        server = json.loads(response.body)
        self.assertEqual(NUM_SERVER_FIELDS, len(server))
        self.assertEqual(self.server.key.urlsafe(), server['key'])
        self.assertEqual(self.server.name, server['name'])
        self.assertEqual(models.SERVER_STOPPED, server['status'])

    def test_get_unauth(self):
        if self.url:
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.get()
            self.assertOK(response)

    def test_post(self):
        name = 'Not So Brave New World'
        params = {'name': name}
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)

    def test_post_json(self):
        name = 'Not So Brave New World'
        params = {'name': name}
        response = self.post_json(params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_FIELDS, body)
        self.assertEqual(1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual(name, body['name'])
        self.assertEqual(name, server.name)


class ServerPropertiesTest(AdminApiTest):
    URL = '/api/v1/servers'
    ALLOWED = ['GET', 'POST']

    @property
    def url(self):
        return "{0}/{1}/properties".format(self.URL, self.server.key.urlsafe())

    def setUp(self):
        super(ServerPropertiesTest, self).setUp()
        self.server.is_gce = True
        self.server.put()

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        server_props = json.loads(response.body)
        self.assertEqual(NUM_SERVER_PROPERTIES_FIELDS, len(server_props))
        self.assertEqual(self.server.key.urlsafe(), server_props['key'])
        self.assertEqual(self.server.memory, server_props['memory'])
        self.assertEqual(self.server.mc_properties.difficulty, server_props['difficulty'])
        self.assertEqual(self.server.mc_properties.pvp, server_props['pvp'])
        self.assertIsNone(server_props['server_port'])

    def test_get_unauth(self):
        if self.url:
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.get()
            self.assertOK(response)

    def test_post(self):
        params = {'memory': '1G', 'difficulty': '3', 'pvp': True, 'server_port': 25566}
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_PROPERTIES_FIELDS, body)
        self.assertEqual(1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual('1G', body['memory'])
        self.assertEqual('1G', server.memory)
        self.assertEqual(3, body['difficulty'])
        self.assertEqual(3, server.mc_properties.difficulty)
        self.assertEqual(True, body['pvp'])
        self.assertEqual(True, server.mc_properties.pvp)
        self.assertEqual(25566, body['server_port'])
        self.assertEqual(25566, server.mc_properties.server_port)

    def test_post_empty_port(self):
        self.server.server_port = 25565
        self.server.put()
        params = {'memory': '1G', 'difficulty': '3', 'pvp': True, 'server_port': ''}
        response = self.post(params=params)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(NUM_SERVER_PROPERTIES_FIELDS, body)
        self.assertEqual(1, models.Server.query().count())
        server_key = ndb.Key(urlsafe=body['key'])
        server = server_key.get()
        self.assertEqual('1G', body['memory'])
        self.assertEqual('1G', server.memory)
        self.assertEqual(3, body['difficulty'])
        self.assertEqual(3, server.mc_properties.difficulty)
        self.assertEqual(True, body['pvp'])
        self.assertEqual(True, server.mc_properties.pvp)
        self.assertIsNone(body['server_port'])
        self.assertIsNone(server.mc_properties.server_port)

    def test_get_invalid_key(self):
        if self.url:
            url = "{0}/{1}/properties".format(self.URL, 'invalid_key')
            response = self.get(url=url)
            self.assertNotFound(response)


class ServerPlayTest(AdminApiTest):
    URL = '/api/v1/servers'
    ALLOWED = ['POST']

    @property
    def url(self):
        return "{0}/{1}/queue/play".format(self.URL, self.server.key.urlsafe())

    def setUp(self):
        super(ServerPlayTest, self).setUp()
        path = os.path.dirname(__file__) + '/../'
        self.testbed.init_taskqueue_stub(root_path=path)
        models.MinecraftDownload.create(
            '1.7.4',
            'https://s3.amazonaws.com/Minecraft.Download/versions/1.7.4/minecraft_server.1.7.4.jar',
            verify=False
        )
        self.server.is_gce = True
        self.server.version = '1.7.4'
        self.server.mc_properties.eula_agree = True
        self.server.mc_properties.put()
        self.server.put()

    def test_post(self):
        logging.disable(logging.ERROR)
        response = self.post()
        self.assertAccepted(response)
        taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = taskqueue_stub.GetTasks('controller')
        self.assertEqual(1, len(tasks), "Incorrect number of tasks: was {0}, should be {1}".format(
            len(tasks), 1)
        )
        taskqueue_stub.FlushQueue("controller")

    def test_post_unauth(self):
        if self.url:
            logging.disable(logging.ERROR)
            self.access_token, self.refresh_token = self.get_tokens()
            response = self.post()
            self.assertAccepted(response)

    def test_post_invalid_key(self):
        if self.url:
            url = "{0}/{1}/queue/play".format(self.URL,  'invalid_key')
            response = self.post(url=url)
            self.assertNotFound(response)


class ServerPauseTest(AdminApiTest):
    URL = '/api/v1/servers'
    ALLOWED = ['POST']

    @property
    def url(self):
        return "{0}/{1}/queue/pause".format(self.URL, self.server.key.urlsafe())

    def setUp(self):
        super(ServerPauseTest, self).setUp()
        path = os.path.dirname(__file__) + '/../'
        self.testbed.init_taskqueue_stub(root_path=path)
        self.server.is_gce = True
        self.server.status = models.SERVER_RUNNING
        self.server.put()

    def test_post(self):
        logging.disable(logging.ERROR)
        response = self.post()
        self.assertAccepted(response)
        taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = taskqueue_stub.GetTasks('controller')
        self.assertEqual(1, len(tasks), "Incorrect number of tasks: was {0}, should be {1}".format(
            len(tasks), 1)
        )
        taskqueue_stub.FlushQueue("controller")

    def test_post_invalid_key(self):
        if self.url:
            url = "{0}/{1}/queue/paly".format(self.URL,  'invalid_key')
            response = self.post(url=url)
            self.assertNotFound(response)


class ServerModelTestBase(object):
    URL = '/api/v1/servers/{0}/'

    def test_get_invalid_server_key(self):
        url = self.url.replace(self.server.key.urlsafe(), 'invalid_key')
        response = self.get(url=url)
        self.assertNotFound(response)

    def test_get_wrong_server(self):
        server = models.Server.create()
        url = self.url.replace(self.server.key.urlsafe(), server.key.urlsafe())
        response = self.get(url=url)
        self.assertNotFound(response)


class PlayersTest(MultiPageApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'players'
    ALLOWED = ['GET']

    def setUp(self):
        super(PlayersTest, self).setUp()
        self.players = []
        for i in range(10):
            self.players.append(models.Player.get_or_create(self.server.key, "Player_{0}".format(i)))
            self.players[i].last_login_timestamp = datetime.datetime.utcnow()

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe())

    def test_get_wrong_server(self):
        pass

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        players = body['players']
        self.assertLength(len(self.players), players)
        for i, player in enumerate(players):
            self.assertEqual(NUM_PLAYER_FIELDS, len(player))
            self.assertEqual(self.players[i].key.urlsafe(), player['key'])
            self.assertEqual(self.players[i].server_key.urlsafe(), player['server_key'])
            self.assertEqual(self.players[i].username, player['username'])
            self.assertIsNotNone(player['last_login'])


class PlayerKeyTest(KeyApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'players/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.player.key.urlsafe())

    def setUp(self):
        super(PlayerKeyTest, self).setUp()
        self.player = models.Player.get_or_create(self.server.key, "Test_Player")
        self.player.last_login_timestamp = datetime.datetime.utcnow()

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        player = json.loads(response.body)
        self.assertEqual(NUM_PLAYER_FIELDS, len(player))
        self.assertEqual(self.player.key.urlsafe(), player['key'])
        self.assertEqual(self.player.server_key.urlsafe(), player['server_key'])
        self.assertEqual(self.player.username, player['username'])
        self.assertIsNotNone(player['last_login'])


class PlayerUsernameTest(KeyApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'players/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.player.username)

    def setUp(self):
        super(PlayerUsernameTest, self).setUp()
        self.player = models.Player.get_or_create(self.server.key, "Test_Player")
        self.player.last_login_timestamp = datetime.datetime.utcnow()

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        player = json.loads(response.body)
        self.assertEqual(NUM_PLAYER_FIELDS, len(player))
        self.assertEqual(self.player.key.urlsafe(), player['key'])
        self.assertEqual(self.player.server_key.urlsafe(), player['server_key'])
        self.assertEqual(self.player.username, player['username'])
        self.assertIsNotNone(player['last_login'])


class PlaySessionsTest(MultiPageApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'sessions'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe())

    def setUp(self):
        super(PlaySessionsTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.players = []
        for i in range(2):
            self.players.append(models.Player.get_or_create(self.server.key, "Player_{0}".format(i)))
            self.players[i].last_login_timestamp = datetime.datetime.utcnow()
        self.play_sessions = []
        for i in range(10):
            player = self.players[i % 2]
            play_session = models.PlaySession.create(
                self.server.key,
                player.username,
                self.now - datetime.timedelta(seconds=10*i),
                TIME_ZONE,
                None
            )
            self.play_sessions.append(play_session)

    def test_get_wrong_server(self):
        pass

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        play_sessions = body['sessions']
        self.assertLength(len(self.play_sessions), play_sessions)
        for i, play_session in enumerate(play_sessions):
            self.assertEqual(NUM_PLAY_SESSION_FIELDS, len(play_session))
            self.assertEqual(self.play_sessions[i].key.urlsafe(), play_session['key'])
            self.assertEqual(self.play_sessions[i].server_key.urlsafe(), play_session['server_key'])
            self.assertEqual(self.play_sessions[i].username, play_session['username'])
            self.assertIsNotNone(play_session['login_timestamp'])

    def test_get_since_before(self):
        url = "{0}?since={1}".format(self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        play_sessions = body['sessions']
        self.assertLength(1, play_sessions)
        for i, play_session in enumerate(play_sessions):
            self.assertEqual(NUM_PLAY_SESSION_FIELDS, len(play_session))
            self.assertEqual(self.play_sessions[i].key.urlsafe(), play_session['key'])
            self.assertEqual(self.play_sessions[i].server_key.urlsafe(), play_session['server_key'])
            self.assertEqual(self.play_sessions[i].username, play_session['username'])
            self.assertIsNotNone(play_session['login_timestamp'])
        url = "{0}?before={1}".format(self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        play_sessions = body['sessions']
        self.assertLength(9, play_sessions)
        for i, play_session in enumerate(play_sessions):
            self.assertEqual(NUM_PLAY_SESSION_FIELDS, len(play_session))
            self.assertEqual(self.play_sessions[i+1].key.urlsafe(), play_session['key'])
            self.assertEqual(self.play_sessions[i+1].server_key.urlsafe(), play_session['server_key'])
            self.assertEqual(self.play_sessions[i+1].username, play_session['username'])
            self.assertIsNotNone(play_session['login_timestamp'])
        url = "{0}?since={1}&before={2}".format(
            self.url,
            self.play_sessions[9].login_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        play_sessions = body['sessions']
        self.assertLength(9, play_sessions)
        for i, play_session in enumerate(play_sessions):
            self.assertEqual(NUM_PLAY_SESSION_FIELDS, len(play_session))
            self.assertEqual(self.play_sessions[i+1].key.urlsafe(), play_session['key'])
            self.assertEqual(self.play_sessions[i+1].server_key.urlsafe(), play_session['server_key'])
            self.assertEqual(self.play_sessions[i+1].username, play_session['username'])
            self.assertIsNotNone(play_session['login_timestamp'])
        url = "{0}?since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        play_sessions = body['sessions']
        self.assertLength(0, play_sessions)


class PlaySessionsPlayerTest(PlaySessionsTest):
    URL = ServerModelTestBase.URL + 'players/{1}/sessions'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())

    def setUp(self):
        super(PlaySessionsPlayerTest, self).setUp()
        new_sessions = []
        for play_session in self.play_sessions:
            if play_session.username == self.players[0].username:
                new_sessions.append(play_session)
            else:
                new_sessions.append(
                    models.PlaySession.create(
                        self.server.key, self.players[0].username, play_session.login_timestamp, play_session.zone, None
                    )
                )
        self.play_sessions = new_sessions


class PlaySessionKeyTest(KeyApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'sessions/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.play_session.key.urlsafe())

    def setUp(self):
        super(PlaySessionKeyTest, self).setUp()
        self.player = models.Player.get_or_create(self.server.key, "Test_Player")
        self.player.last_login_timestamp = datetime.datetime.utcnow()
        self.play_session = models.PlaySession.create(
            self.server.key, self.player.username, datetime.datetime.utcnow(), TIME_ZONE, None
        )

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        play_session = json.loads(response.body)
        self.assertEqual(NUM_PLAY_SESSION_FIELDS, len(play_session))
        self.assertEqual(self.play_session.key.urlsafe(), play_session['key'])
        self.assertEqual(self.play_session.server_key.urlsafe(), play_session['server_key'])
        self.assertEqual(self.play_session.username, play_session['username'])
        self.assertIsNotNone(play_session['login_timestamp'])


class ChatsTest(MultiPageApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'chats'
    ALLOWED = ['GET', 'POST']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe())

    def setUp(self):
        super(ChatsTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.players = []
        self.players.append(models.Player.get_or_create(self.server.key, "gumptionthomas"))
        self.players.append(models.Player.get_or_create(self.server.key, "vesicular"))
        self.log_lines = []
        for i in range(len(CHAT_LOG_LINES_CRON)):
            log_line = models.LogLine.create(self.server, CHAT_LOG_LINES_CRON[i], TIME_ZONE)
            self.log_lines.append(log_line)
        log_line = models.LogLine.create(self.server, TIME_STAMP_LOG_LINE, TIME_ZONE)
        self.post_username = None

    def test_get_wrong_server(self):
        pass

    def test_get(self):
        response = self.get(url='{0}?size={1}'.format(self.url, 50))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(len(self.log_lines), log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertEqual(self.log_lines[i].chat, log_line['chat'])
            self.assertEqual(self.log_lines[i].username, log_line['username'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_since_before(self):
        url = "{0}?since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?before={1}".format(self.url, self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(len(self.log_lines)-2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?since={1}&before={2}".format(
            self.url,
            self.log_lines[2].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(0, log_lines)

    def test_post(self):
        username = "gumptionthomas"
        self.player = models.Player.get_or_create(self.server.key, username)
        self.user.usernames = [username]
        self.user.put()
        chat = u'Hello world...'
        params = {'chat': chat}
        response = self.post(params=params)
        self.assertAccepted(response)
        self.assertEqual(1, models.Command.query().count())
        command = models.Command.query().get()
        self.assertEqual(username, command.username)
        self.assertEqual(u'/say <gumptionthomas> {0}'.format(chat), command.command)

    def test_post_no_player(self):
        play_name = self.user.get_server_play_name(self.server.key)
        nickname = self.user.nickname
        chat = u'Hello world...'
        params = {'chat': chat}
        response = self.post(params=params)
        self.assertAccepted(response)
        self.assertEqual(1, models.Command.query().count())
        command = models.Command.query().get()
        self.assertEqual('*{0}'.format(nickname), play_name)
        self.assertEqual(play_name, command.username)
        self.assertEqual(u'/say <*admin@example.com> {0}'.format(chat), command.command)

    def test_post_no_player_no_nickname(self):
        self.user.nickname = None
        self.user.put()
        play_name = self.user.get_server_play_name(self.server.key)
        email = self.user.email
        chat = u'Hello world...'
        params = {'chat': chat}
        response = self.post(params=params)
        self.assertAccepted(response)
        self.assertEqual(1, models.Command.query().count())
        command = models.Command.query().get()
        self.assertEqual(email, play_name)
        self.assertEqual(play_name, command.username)
        self.assertEqual(u'/say <admin@example.com> {0}'.format(chat), command.command)

    def test_post_no_access_token(self):
        self.access_token = None
        response = self.post(params={'chat': u"Hello world..."})
        self.assertUnauthorized(response)

    def test_post_invalid_access_token(self):
        self.access_token = 'invalid_token'
        response = self.post(params={'chat': u"Hello world..."})
        self.assertUnauthorized(response)


class ChatsPlayerTest(ChatsTest):
    URL = ServerModelTestBase.URL + 'players/{1}/chats'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())

    def setUp(self):
        super(ChatsPlayerTest, self).setUp()
        new_log_lines = []
        i = 7
        for log_line in self.log_lines:
            if log_line.username != self.players[0].username:
                new_line = '2012-10-09 20:46:0{0} [INFO] <{1}> yo yo'.format(i, self.players[0].username)
                new_log_lines.append(models.LogLine.create(self.server, new_line, log_line.zone))
                i += 1
        self.log_lines = new_log_lines

    def test_get_since_before(self):
        pass

    def test_post_no_player(self):
        pass

    def test_post_no_player_no_nickname(self):
        pass

    def test_post_invalid_username(self):
        self.assertEmpty(self.user.usernames)
        chat = u'Hello world...'
        params = {'chat': chat}
        response = self.post(params=params)
        self.assertForbidden(response)


class ChatsQueryTest(ChatsTest):
    def setUp(self):
        super(ChatsQueryTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.log_lines = []
        for i in range(25):
            dt = self.now - datetime.timedelta(minutes=i)
            chat_log_line = '{0} [INFO] <gumptionthomas> foobar {1}'.format(dt.strftime("%Y-%m-%d %H:%M:%S"), i)
            log_line = models.LogLine.create(self.server, chat_log_line, TIME_ZONE)
            self.log_lines.append(log_line)

    def test_get_wrong_server(self):
        pass

    def test_get(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'yo'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertIn('yo', log_line['line'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_multi(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'foobar'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['chats']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i), log_line['chat'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'foobar', next_cursor))
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['chats']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i+10), log_line['chat'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'foobar', next_cursor))
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(5, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i+20), log_line['chat'])

    def test_get_since_before(self):
        url = "{0}?q=foobar&since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?q=foobar&before={1}&size=50".format(
            self.url, self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(len(self.log_lines)-2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?q=foobar&since={1}&before={2}".format(
            self.url,
            self.log_lines[4].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?q=foobar&since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(0, log_lines)


class ChatsQueryPlayerTest(ChatsTest):
    URL = ServerModelTestBase.URL + 'players/{1}/chats'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())

    def setUp(self):
        super(ChatsQueryPlayerTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        new_log_lines = []
        i = 7
        for log_line in self.log_lines:
            if log_line.username != self.players[0].username:
                new_line = '2012-10-09 20:46:0{0} [INFO] <{1}> yo yo'.format(i, self.players[0].username)
                new_log_lines.append(models.LogLine.create(self.server, new_line, log_line.zone))
                i += 1
        self.log_lines = new_log_lines
        self.log_lines = []
        for i in range(25):
            dt = self.now - datetime.timedelta(minutes=i)
            chat_log_line = '{0} [INFO] <gumptionthomas> foobar {1}'.format(dt.strftime("%Y-%m-%d %H:%M:%S"), i)
            log_line = models.LogLine.create(self.server, chat_log_line, TIME_ZONE)
            self.log_lines.append(log_line)

    def test_get(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'yo'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertIn('yo', log_line['line'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_multi(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'foobar'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['chats']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i), log_line['chat'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'foobar', next_cursor))
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['chats']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i+10), log_line['chat'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'foobar', next_cursor))
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(5, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i+20), log_line['chat'])

    def test_get_since_before(self):
        url = "{0}?q=foobar&since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?q=foobar&before={1}&size=50".format(
            self.url, self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(len(self.log_lines)-2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?q=foobar&since={1}&before={2}".format(
            self.url,
            self.log_lines[4].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        url = "{0}?q=foobar&since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['chats']
        self.assertLength(0, log_lines)

    def test_post_invalid_username(self):
        self.assertEmpty(self.user.usernames)
        chat = u'Hello world...'
        params = {'chat': chat}
        response = self.post(params=params)
        self.assertForbidden(response)

    def test_get_wrong_server(self):
        pass

    def test_post_no_player(self):
        pass

    def test_post_no_player_no_nickname(self):
        pass


class ChatKeyTest(KeyApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'chats/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.log_line.key.urlsafe())

    def setUp(self):
        super(ChatKeyTest, self).setUp()
        self.player = models.Player.get_or_create(self.server.key, "vesicular")
        self.log_line = models.LogLine.create(self.server, CHAT_LOG_LINE, TIME_ZONE)

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        log_line = json.loads(response.body)
        self.assertEqual(NUM_CHAT_FIELDS, len(log_line))
        self.assertEqual(self.log_line.key.urlsafe(), log_line['key'])
        self.assertEqual(self.log_line.username, log_line['username'])


class DeathsTest(MultiPageApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'deaths'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe())

    def setUp(self):
        super(DeathsTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.players = []
        self.players.append(models.Player.get_or_create(self.server.key, "gumptionthomas"))
        self.players.append(models.Player.get_or_create(self.server.key, "vesicular"))
        self.log_lines = []
        for i in range(len(DEATH_LOG_LINES_CRON)):
            log_line = models.LogLine.create(self.server, DEATH_LOG_LINES_CRON[i], TIME_ZONE)
            self.log_lines.append(log_line)
        log_line = models.LogLine.create(self.server, TIME_STAMP_LOG_LINE, TIME_ZONE)
        death_log_line = '{0} [INFO] vesicular tried to swim in lava'.format(self.now.strftime("%Y-%m-%d %H:%M:%S"))
        log_line = models.LogLine.create(self.server, death_log_line, TIME_ZONE)
        self.log_lines.insert(0, log_line)

    def test_get(self):
        response = self.get(url='{0}?size={1}'.format(self.url, 50))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(len(self.log_lines), log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
            self.assertEqual(self.log_lines[i].death_message, log_line['message'])
            self.assertEqual(self.log_lines[i].username, log_line['username'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_since_before(self):
        url = "{0}?since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
        url = "{0}?before={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(len(self.log_lines)-1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
        url = "{0}?since={1}&before={2}".format(
            self.url,
            self.log_lines[2].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
        url = "{0}?since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(0, log_lines)

    def test_get_wrong_server(self):
        pass


class DeathsPlayerTest(DeathsTest):
    URL = ServerModelTestBase.URL + 'players/{1}/deaths'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())

    def setUp(self):
        super(DeathsPlayerTest, self).setUp()
        self.log_lines.pop(0)
        death_log_line = '{0} [INFO] gumptionthomas tried to swim in lava'.format(
            self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        log_line = models.LogLine.create(self.server, death_log_line, TIME_ZONE)
        self.log_lines.insert(0, log_line)

    def test_get_since_before(self):
        pass


class DeathsQueryTest(DeathsTest):
    def setUp(self):
        super(DeathsQueryTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.log_lines = []
        for i in range(25):
            dt = self.now - datetime.timedelta(minutes=i)
            death_log_line = '{0} [INFO] gumptionthomas was squashed by a falling anvil'.format(
                dt.strftime("%Y-%m-%d %H:%M:%S")
            )
            log_line = models.LogLine.create(self.server, death_log_line, TIME_ZONE)
            self.log_lines.append(log_line)

    def test_get(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'cactus'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
            self.assertIn('cactus', log_line['line'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_multi(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'anvil'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['deaths']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'anvil', next_cursor))
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['deaths']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'anvil', next_cursor))
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(6, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])

    def test_get_since_before(self):
        url = "{0}?q=anvil&since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
        url = "{0}?q=anvil&before={1}&size=50".format(
            self.url, self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(len(self.log_lines)-1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
        url = "{0}?q=anvil&since={1}&before={2}".format(
            self.url,
            self.log_lines[4].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
        url = "{0}?q=anvil&since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['deaths']
        self.assertLength(0, log_lines)


class DeathsQueryPlayerTest(DeathsQueryTest):
    URL = ServerModelTestBase.URL + 'players/{1}/deaths'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())


class DeathKeyTest(KeyApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'deaths/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.log_line.key.urlsafe())

    def setUp(self):
        super(DeathKeyTest, self).setUp()
        self.player = models.Player.get_or_create(self.server.key, "gumptionthomas")
        self.log_line = models.LogLine.create(self.server, SHOT_DEATH_LOG_LINE, TIME_ZONE)

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        log_line = json.loads(response.body)
        self.assertEqual(NUM_DEATH_FIELDS, len(log_line))
        self.assertEqual(self.log_line.key.urlsafe(), log_line['key'])
        self.assertEqual(self.log_line.username, log_line['username'])


class AchievementsTest(MultiPageApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'achievements'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe())

    def setUp(self):
        super(AchievementsTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.players = []
        self.players.append(models.Player.get_or_create(self.server.key, "gumptionthomas"))
        self.players.append(models.Player.get_or_create(self.server.key, "vesicular"))
        self.log_lines = []
        for i in range(5):
            dt = self.now - datetime.timedelta(minutes=i+1)
            achievement_log_line = '{0} [INFO] gumptionthomas has just earned the achievement [Getting an Upgrade]'.format(dt.strftime("%Y-%m-%d %H:%M:%S"))
            log_line = models.LogLine.create(self.server, achievement_log_line, TIME_ZONE)
            self.log_lines.append(log_line)
        log_line = models.LogLine.create(self.server, TIME_STAMP_LOG_LINE, TIME_ZONE)
        achievement_log_line = '{0} [INFO] vesicular has just earned the achievement [Getting an Upgrade]'.format(
            self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        log_line = models.LogLine.create(self.server, achievement_log_line, TIME_ZONE)
        self.log_lines.insert(0, log_line)

    def test_get(self):
        response = self.get(url='{0}?size={1}'.format(self.url, 50))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(len(self.log_lines), log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
            self.assertEqual(self.log_lines[i].achievement, log_line['name'])
            self.assertEqual(self.log_lines[i].achievement_message, log_line['message'])
            self.assertEqual(self.log_lines[i].username, log_line['username'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_since_before(self):
        url = "{0}?since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
        url = "{0}?before={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(len(self.log_lines)-1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
        url = "{0}?since={1}&before={2}".format(
            self.url,
            self.log_lines[2].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
        url = "{0}?since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(0, log_lines)

    def test_get_wrong_server(self):
        pass


class AchievementsPlayerTest(AchievementsTest):
    URL = ServerModelTestBase.URL + 'players/{1}/achievements'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())

    def setUp(self):
        super(AchievementsPlayerTest, self).setUp()
        self.log_lines.pop(0)
        achievement_log_line = '{0} [INFO] gumptionthomas has just earned the achievement [Getting an Upgrade]'.format(
            self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        log_line = models.LogLine.create(self.server, achievement_log_line, TIME_ZONE)
        self.log_lines.insert(0, log_line)

    def test_get_since_before(self):
        pass


class AchievementsQueryTest(AchievementsTest):
    def setUp(self):
        super(AchievementsQueryTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.log_lines = []
        for i in range(25):
            dt = self.now - datetime.timedelta(minutes=i)
            achievement_log_line = '{0} [INFO] gumptionthomas has just earned the achievement [Taking Inventory]'.format(dt.strftime("%Y-%m-%d %H:%M:%S"))
            log_line = models.LogLine.create(self.server, achievement_log_line, TIME_ZONE)
            self.log_lines.append(log_line)
        dt = self.now - datetime.timedelta(minutes=25)
        achievement_log_line = '{0} [INFO] gumptionthomas has just earned the achievement [The Lie]'.format(
            dt.strftime("%Y-%m-%d %H:%M:%S")
        )
        log_line = models.LogLine.create(self.server, achievement_log_line, TIME_ZONE)
        self.log_lines.append(log_line)

    def test_get(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'Lie'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
            self.assertIn('Lie', log_line['line'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_multi(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'Inventory'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['achievements']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'Inventory', next_cursor))
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['achievements']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
        response = self.get(url='{0}?q={1}&cursor={2}'.format(self.url, 'Inventory', next_cursor))
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(5, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])

    def test_get_since_before(self):
        url = "{0}?q=Inventory&since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
        url = "{0}?q=Inventory&before={1}&size=50".format(
            self.url, self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(len(self.log_lines)-3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
        url = "{0}?q=Inventory&since={1}&before={2}".format(
            self.url,
            self.log_lines[4].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
        url = "{0}?q=Inventory&since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['achievements']
        self.assertLength(0, log_lines)


class AchievementsQueryPlayerTest(AchievementsQueryTest):
    URL = ServerModelTestBase.URL + 'players/{1}/achievements'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())


class AchievementKeyTest(KeyApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'achievements/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.log_line.key.urlsafe())

    def setUp(self):
        super(AchievementKeyTest, self).setUp()
        self.player = models.Player.get_or_create(self.server.key, "gumptionthomas")
        self.log_line = models.LogLine.create(self.server, ACHIEVEMENT_LOG_LINE, TIME_ZONE)

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        log_line = json.loads(response.body)
        self.assertEqual(NUM_ACHIEVEMENT_FIELDS, len(log_line))
        self.assertEqual(self.log_line.key.urlsafe(), log_line['key'])
        self.assertEqual(self.log_line.achievement, log_line['name'])
        self.assertEqual(self.log_line.achievement_message, log_line['message'])
        self.assertEqual(self.log_line.username, log_line['username'])


class LogLinesTest(MultiPageApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'loglines'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe())

    def setUp(self):
        super(LogLinesTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.players = []
        self.players.append(models.Player.get_or_create(self.server.key, "gumptionthomas"))
        self.players.append(models.Player.get_or_create(self.server.key, "vesicular"))
        self.log_lines = []
        for i in range(len(TIMESTAMP_LOG_LINES_CRON)):
            log_line = models.LogLine.create(self.server, TIMESTAMP_LOG_LINES_CRON[i], TIME_ZONE)
            self.log_lines.append(log_line)

    def test_get(self):
        response = self.get(url='{0}?size={1}'.format(self.url, 50))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(len(self.log_lines), log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
            self.assertEqual(self.log_lines[i].line, log_line['line'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_since_before(self):
        url = "{0}?since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
        url = "{0}?before={1}".format(self.url, self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(len(self.log_lines)-2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
        url = "{0}?since={1}&before={2}".format(
            self.url,
            self.log_lines[4].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
        url = "{0}?since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(0, log_lines)

    def test_get_chats(self):
        url = "{0}?tag={1}".format(self.url, 'chat')
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
            self.assertIn('chat', log_line['tags'])

    def test_get_wrong_server(self):
        pass


class LogLinesPlayerTest(LogLinesTest):
    URL = ServerModelTestBase.URL + 'players/{1}/loglines'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())

    def setUp(self):
        super(LogLinesPlayerTest, self).setUp()
        for log_line in models.LogLine.query():
            log_line.key.delete()
        self.log_lines = []
        for i in range(3):
            dt = self.now - datetime.timedelta(minutes=i)
            chat_log_line = '{0} [INFO] <gumptionthomas> foobar {1}'.format(dt.strftime("%Y-%m-%d %H:%M:%S"), i)
            log_line = models.LogLine.create(self.server, chat_log_line, TIME_ZONE)
            self.log_lines.append(log_line)

    def test_get_since_before(self):
        pass


class LogLinesQueryTest(LogLinesTest):
    def setUp(self):
        super(LogLinesQueryTest, self).setUp()
        self.now = datetime.datetime.utcnow()
        self.log_lines = []
        for i in range(25):
            dt = self.now - datetime.timedelta(minutes=i)
            chat_log_line = '{0} [INFO] <gumptionthomas> foobar {1}'.format(dt.strftime("%Y-%m-%d %H:%M:%S"), i)
            log_line = models.LogLine.create(self.server, chat_log_line, TIME_ZONE)
            self.log_lines.append(log_line)

    def test_get(self):
        response = self.get(url='{0}?q={1}'.format(self.url, 'yo'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
            self.assertIn('yo', log_line['line'])
            self.assertIsNotNone(log_line['timestamp'])

    def test_get_multi(self):
        response = self.get('{0}?q={1}&tag=chat'.format(self.url, 'foobar'))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['loglines']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i), log_line['chat'])
        response = self.get(url='{0}?q={1}&tag=chat&cursor={2}'.format(self.url, 'foobar', next_cursor))
        body = json.loads(response.body)
        self.assertLength(2, body)
        next_cursor = body['cursor']
        log_lines = body['loglines']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i+10), log_line['chat'])
        response = self.get(url='{0}?q={1}&tag=chat&cursor={2}'.format(self.url, 'foobar', next_cursor))
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(5, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])
            self.assertEqual('foobar {0}'.format(i+20), log_line['chat'])

    def test_get_chats(self):
        url = "{0}?q=foobar&tag=chat".format(self.url)
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(2, body)
        log_lines = body['loglines']
        self.assertLength(10, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
            self.assertEqual('gumptionthomas', log_line['username'])

    def test_get_since_before(self):
        url = "{0}?q=foobar&since={1}".format(self.url, self.log_lines[0].timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(1, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
        url = "{0}?q=foobar&before={1}&size=50".format(
            self.url, self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(len(self.log_lines)-2, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
        url = "{0}?q=foobar&since={1}&before={2}".format(
            self.url,
            self.log_lines[4].timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.log_lines[1].timestamp.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(3, log_lines)
        for i, log_line in enumerate(log_lines):
            self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
        url = "{0}?q=foobar&since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        log_lines = body['loglines']
        self.assertLength(0, log_lines)


class LogLinesQueryPlayerTest(LogLinesQueryTest):
    URL = ServerModelTestBase.URL + 'players/{1}/loglines'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.players[0].key.urlsafe())

    def setUp(self):
        super(LogLinesQueryPlayerTest, self).setUp()
        for i in range(2):
            dt = self.now - datetime.timedelta(minutes=i)
            chat_log_line = '{0} [INFO] <gumptionthomas> yo {1}'.format(dt.strftime("%Y-%m-%d %H:%M:%S"), i)
            log_line = models.LogLine.create(self.server, chat_log_line, TIME_ZONE)
            self.log_lines.append(log_line)

    def test_get_since_before(self):
        pass


class LogLineKeyTest(KeyApiTest, ServerModelTestBase):
    URL = ServerModelTestBase.URL + 'loglines/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.log_line.key.urlsafe())

    def setUp(self):
        super(LogLineKeyTest, self).setUp()
        self.player = models.Player.get_or_create(self.server.key, "gumptionthomas")
        self.log_line = models.LogLine.create(self.server, CONNECT_LOG_LINE, TIME_ZONE)

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        log_line = json.loads(response.body)
        self.assertEqual(NUM_LOG_LINE_FIELDS, len(log_line))
        self.assertEqual(self.log_line.key.urlsafe(), log_line['key'])
        self.assertEqual(self.log_line.username, log_line['username'])


class ScreenShotTestBase(object):
    def mock_post_data(self, data, filename=None, mime_type=None):
        if not filename:
            filename = ''.join([random.choice(string.ascii_uppercase) for x in xrange(50)])
        blob_info = self.create_blob_info(filename, image_data=data)
        return blob_info.key()

    def create_blob_info(self, path, image_data=None):
        if not image_data:
            image_data = open(path, 'rb').read()
        path = os.path.basename(path)
        self.testbed.get_stub('blobstore').CreateBlob(path, image_data)
        return blobstore.BlobInfo(blobstore.BlobKey(path))

    def execute_tasks(self, expected_tasks=1):
        taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        tasks = taskqueue_stub.GetTasks('default')
        self.assertEqual(expected_tasks, len(tasks), "Incorrect number of tasks: was {0}, should be {1}".format(
            repr(tasks), expected_tasks)
        )
        taskqueue_stub.FlushQueue("default")
        for task in tasks:
            url = task['url']
            key_string = url[13:url.find('/', 13)]
            screenshot = ndb.Key(urlsafe=key_string).get()
            screenshot.create_blurred()


class ScreenShotTest(MultiPageApiTest, ScreenShotTestBase):
    URL = ServerModelTestBase.URL + 'screenshots'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe())

    def setUp(self):
        super(ScreenShotTest, self).setUp()
        minimock.mock('image.NdbImage.post_data', returns_func=self.mock_post_data, tracker=None)
        self.user.usernames = ['gumptionthomas']
        self.user.put()
        self.now = datetime.datetime.utcnow()
        self.players = []
        self.players.append(models.Player.get_or_create(self.server.key, "gumptionthomas"))
        self.players.append(models.Player.get_or_create(self.server.key, "vesicular"))
        self.screenshots = []
        self.blob_info = self.create_blob_info(IMAGE_PATH)
        for i in range(5):
            screenshot = models.ScreenShot.create(self.server.key, self.user, blob_info=self.blob_info)
            self.screenshots.insert(0, screenshot)
        self.assertEqual(5, models.ScreenShot.query().count())
        #For speed, don't actually generate the blurs for these images
        taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
        taskqueue_stub.FlushQueue('default')

    def tearDown(self):
        super(ScreenShotTest, self).tearDown()
        minimock.restore()

    @property
    def blobs(self):
        return self.testbed.get_stub('blobstore').storage._blobs

    def test_get(self):
        for i in range(5):
            screenshot = models.ScreenShot.create(
                self.server.key,
                self.user,
                blob_info=self.blob_info,
                created=self.now - datetime.timedelta(minutes=1)
            )
            self.screenshots.append(screenshot)
        self.assertEqual(10, models.ScreenShot.query().count())
        self.execute_tasks(expected_tasks=5)
        response = self.get(url='{0}?size={1}'.format(self.url, 50))
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        screenshots = body['screenshots']
        self.assertLength(len(self.screenshots), screenshots)
        for i, screenshot in enumerate(screenshots):
            self.assertEqual(NUM_SCREENSHOT_FIELDS, len(screenshot))
            self.assertEqual(self.screenshots[i].get_serving_url(), screenshot['original_url'])
            self.assertEqual(self.screenshots[i].blurred_image_serving_url, screenshot['blurred_url'])
            self.assertEqual(self.screenshots[i].user_key.urlsafe(), screenshot['user_key'])

    def test_get_since_before(self):
        for screenshot in self.screenshots:
            screenshot.key.delete()
        import time
        self.screenshots = []
        for i in range(5):
            screenshot = models.ScreenShot.create(self.server.key, self.user, blob_info=self.blob_info)
            self.screenshots.insert(0, screenshot)
            time.sleep(1)
        url = "{0}?since={1}".format(self.url, self.screenshots[0].created.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        screenshots = body['screenshots']
        self.assertLength(1, screenshots)
        for i, screenshot in enumerate(screenshots):
            self.assertEqual(NUM_SCREENSHOT_FIELDS, len(screenshot))
        url = "{0}?before={1}".format(self.url, self.screenshots[1].created.strftime("%Y-%m-%d %H:%M:%S"))
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        screenshots = body['screenshots']
        self.assertLength(len(self.screenshots)-2, screenshots)
        for i, screenshot in enumerate(screenshots):
            self.assertEqual(NUM_SCREENSHOT_FIELDS, len(screenshot))
        url = "{0}?since={1}&before={2}".format(
            self.url,
            self.screenshots[4].created.strftime("%Y-%m-%d %H:%M:%S"),
            self.screenshots[1].created.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        screenshots = body['screenshots']
        self.assertLength(3, screenshots)
        for i, screenshot in enumerate(screenshots):
            self.assertEqual(NUM_SCREENSHOT_FIELDS, len(screenshot))
        url = "{0}?since={1}&before={1}".format(
            self.url, self.now.strftime("%Y-%m-%d %H:%M:%S"), self.now.strftime("%Y-%m-%d %H:%M:%S")
        )
        response = self.get(url=url)
        self.assertOK(response)
        body = json.loads(response.body)
        self.assertLength(1, body)
        screenshots = body['screenshots']
        self.assertLength(0, screenshots)


class ScreenShotUserTest(ScreenShotTest):
    URL = ServerModelTestBase.URL + 'users/{1}/screenshots'

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.user.key.urlsafe())


class ScreenShotKeyTest(KeyApiTest, ScreenShotTestBase):
    URL = ServerModelTestBase.URL + 'screenshots/{1}'
    ALLOWED = ['GET']

    @property
    def url(self):
        return self.URL.format(self.server.key.urlsafe(), self.screenshot.key.urlsafe())

    def setUp(self):
        super(ScreenShotKeyTest, self).setUp()
        minimock.mock('image.NdbImage.post_data', returns_func=self.mock_post_data, tracker=None)
        self.user.usernames = ['gumptionthomas']
        self.user.put()
        self.now = datetime.datetime.utcnow()
        self.blob_info = self.create_blob_info(IMAGE_PATH)
        self.player = models.Player.get_or_create(self.server.key, "gumptionthomas")
        self.screenshot = models.ScreenShot.create(
            self.server.key,
            self.user,
            blob_info=self.blob_info,
            created=self.now-datetime.timedelta(minutes=1)
        )
        self.execute_tasks()

    def tearDown(self):
        super(ScreenShotKeyTest, self).tearDown()
        minimock.restore()

    @property
    def blobs(self):
        return self.testbed.get_stub('blobstore').storage._blobs

    def test_get(self):
        response = self.get()
        self.assertOK(response)
        screenshot = json.loads(response.body)
        self.assertEqual(NUM_SCREENSHOT_FIELDS, len(screenshot))
        self.assertEqual(self.screenshot.get_serving_url(), screenshot['original_url'])
        self.assertEqual(self.screenshot.blurred_image_serving_url, screenshot['blurred_url'])
        self.assertEqual(self.screenshot.user.key.urlsafe(), screenshot['user_key'])
