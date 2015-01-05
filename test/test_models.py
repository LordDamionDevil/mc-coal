import fix_dev_path  # noqa

import datetime
import os
import random
import string

from google.appengine.ext import blobstore, testbed, ndb

import webapp2_extras.appengine.auth.models as auth_models

import minimock

from base_test import BaseTest
from web_test import WebTest

import channel
import image
import main
import models


IMAGE_PATH = 'static/img/coal_sprite.png'
TIME_ZONE = 'America/Chicago'
LOG_LINE = '2013-03-23 19:01:19 [INFO] <quazifene> is there anybody in there?'


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
        self.assertEqual(
            expected_tasks,
            len(tasks),
            "Incorrect number of tasks: was {0}, should be {1}".format(repr(tasks), expected_tasks)
        )
        taskqueue_stub.FlushQueue("default")
        for task in tasks:
            url = task['url']
            key_string = url[13:url.find('/', 13)]
            screenshot = ndb.Key(urlsafe=key_string).get()
            screenshot.create_blurred()


class ScreenShotTest(BaseTest, ScreenShotTestBase):
    APPLICATION = main.application

    def setUp(self):
        super(ScreenShotTest, self).setUp()
        minimock.mock('image.NdbImage.post_data', returns_func=self.mock_post_data, tracker=None)
        self.server = models.Server.create()
        self.image_data = None
        self.screenshots = []
        blob_info = self.create_blob_info(IMAGE_PATH)
        for i in range(5):
            screenshot = models.ScreenShot.create(self.server.key, None, blob_info=blob_info)
            self.screenshots.append(screenshot)
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

    def create_blob_info(self, path, image_data=None):
        if not image_data:
            image_data = open(path, 'rb').read()
        path = os.path.basename(path)
        self.testbed.get_stub('blobstore').CreateBlob(path, image_data)
        return blobstore.BlobInfo(blobstore.BlobKey(path))

    def test_random(self):
        found_keys = set()
        for i in range(20):
            found_keys.add(models.ScreenShot.random(self.server.key).key)
        self.assertLess(0, len(found_keys))

    def test_create_data(self):
        self.image_data = open(IMAGE_PATH, 'rb').read()
        screenshot = models.ScreenShot.create(self.server.key, None, data=self.image_data, filename=IMAGE_PATH)
        self.assertIsNotNone(screenshot)
        self.assertEqual(self.image_data, screenshot.image_data)
        self.assertEqual(1, len(self.blobs))
        # Create the blurred version
        self.execute_tasks()
        self.assertIsNotNone(screenshot.blurred_image_serving_url)
        self.assertEqual(2, len(self.blobs))

    def test_create_blob(self):
        blob_info = self.create_blob_info(IMAGE_PATH)
        screenshot = models.ScreenShot.create(self.server.key, None, blob_info=blob_info)
        self.assertIsNotNone(screenshot)
        self.assertIsNone(screenshot.blurred_image_serving_url)
        image_data = open(IMAGE_PATH, 'rb').read()
        self.assertEqual(image_data, screenshot.image_data)
        self.assertEqual(1, len(self.blobs))
        # Create the blurred version
        self.execute_tasks()
        self.assertIsNotNone(screenshot.blurred_image_serving_url)
        self.assertEqual(2, len(self.blobs))

    def test_delete(self):
        blob_info = self.create_blob_info(IMAGE_PATH)
        screenshot = models.ScreenShot.create(self.server.key, None, blob_info=blob_info)
        # Create the blurred version
        self.execute_tasks()
        self.assertIsNotNone(screenshot)
        self.assertIsNotNone(screenshot.blurred_image_serving_url)
        self.assertEqual(6, models.ScreenShot.query().count())
        self.assertEqual(1, models.NdbImage.query().count())
        self.assertEqual(2, len(self.blobs))
        image_data = open(IMAGE_PATH, 'rb').read()
        self.assertEqual(image_data, screenshot.image_data)
        screenshot.key.delete()
        self.assertEqual(5, models.ScreenShot.query().count())
        self.assertEqual(0, models.NdbImage.query().count())
        self.assertEqual(0, len(self.blobs))


class ScreenShotBlurredTaskTest(WebTest, BaseTest, ScreenShotTestBase):
    APPLICATION = main.application

    def setUp(self):
        super(ScreenShotBlurredTaskTest, self).setUp()
        minimock.mock('image.NdbImage.post_data', returns_func=self.mock_post_data, tracker=None)
        self.server = models.Server.create()
        self.image_data = None
        blob_info = self.create_blob_info(IMAGE_PATH)
        self.screenshot = models.ScreenShot.create(self.server.key, None, blob_info=blob_info)
        self.assertEqual(1, models.ScreenShot.query().count())

    def tearDown(self):
        super(ScreenShotBlurredTaskTest, self).tearDown()
        minimock.restore()

    def test_post(self):
        response = self.post("/screenshots/{0}/create_blur".format(self.screenshot.key.urlsafe()))
        self.assertOK(response)


class ServerTest(BaseTest):
    def setUp(self):
        super(ServerTest, self).setUp()
        self.server = models.Server.create()
        self.now = datetime.datetime.utcnow()

    def test_update_status(self):
        self.server.update_status(models.SERVER_RUNNING, self.now)
        self.assertTrue(self.server.is_running)
        self.assertEqual(self.now, self.server.last_ping)
        ping_time = self.now + datetime.timedelta(seconds=30)
        self.server.update_status(models.SERVER_RUNNING, ping_time)
        self.assertTrue(self.server.is_running)
        self.assertEqual(self.now, self.server.last_ping)
        ping_time = self.now + datetime.timedelta(seconds=61)
        self.server.update_status(models.SERVER_RUNNING, ping_time)
        self.assertTrue(self.server.is_running)
        self.assertEqual(ping_time, self.server.last_ping)

    def test_reserved_ports(self):
        self.server2 = models.Server.create()
        self.server.mc_properties.server_port = 25565
        self.server.mc_properties.put()
        self.server2.mc_properties.server_port = 25566
        self.server2.mc_properties.put()
        self.assertEqual([25566, 25565],  models.Server.reserved_ports())
        self.server3 = models.Server.create()
        self.server3.mc_properties.server_port = 25567
        self.server3.mc_properties.put()
        self.assertEqual([25567, 25565],  models.Server.reserved_ports(ignore_server=self.server2))
        self.server2.active = False
        self.server2.put()
        self.assertEqual([25567],  models.Server.reserved_ports(ignore_server=self.server))

    def test_short_name(self):
        self.assertTrue(self.server.set_short_name('My Server'))
        self.assertEqual('my-server', self.server.short_name)
        self.assertEqual(1, auth_models.Unique.query().count())
        self.assertTrue(self.server.set_short_name('my-server'))
        self.assertTrue(self.server.set_short_name(''))
        self.assertIsNone(self.server.short_name)
        self.assertEqual(0, auth_models.Unique.query().count())

    def test_short_name_2(self):
        self.assertTrue(self.server.set_short_name(u"\u5317\u4EB0"))
        self.assertEqual('bei-jing', self.server.short_name)
        self.assertIsNotNone(models.Server.get_by_short_name('bei-jing'))
        self.assertIsNone(models.Server.get_by_short_name(u"\u5317\u4EB0"))


class LogLineTest(BaseTest):
    def setUp(self):
        super(LogLineTest, self).setUp()
        self.server = models.Server.create()

    def tearDown(self):
        super(LogLineTest, self).tearDown()
        minimock.restore()

    def test_post_put_hook_sends_log_line_to_channel(self):
        tracker = minimock.TraceTracker()
        minimock.mock('channel.ServerChannels.get_client_ids', returns=['client_id'], tracker=None)
        minimock.mock('channel.ServerChannels.send_message', tracker=tracker)
        log_line = models.LogLine.create(self.server, LOG_LINE, TIME_ZONE)
        minimock.assert_same_trace(
            tracker, """Called channel.ServerChannels.send_message({0}, u'chat')""".format(log_line)
        )


class ServerChannelsTest(BaseTest):
    def setUp(self):
        super(ServerChannelsTest, self).setUp()
        self.server = models.Server.create()

    def test_returns_emtpy_list_if_no_entity(self):
        self.assertEqual([], channel.ServerChannels.get_client_ids(self.server.key))


class AddServerChannelTest(BaseTest):
    def setUp(self):
        super(AddServerChannelTest, self).setUp()
        self.server = models.Server.create()
        models.User.create_user('1234', email='bill@example.com')
        self.user = models.User.lookup(email='bill@example.com')

    def test_adds_client_id_to_lookup_store_despite_missing_lookup_entity(self):
        client_id = channel.ServerChannels.get_client_id([self.server.key], self.user)
        channel.ServerChannels.add_client_id(client_id)
        self.assertEqual([client_id], channel.ServerChannels.get_client_ids(self.server.key))

    def test_adds_client_id_to_existing_lookup_store(self):
        client_id = channel.ServerChannels.get_client_id([self.server.key], self.user)
        channel.ServerChannels.add_client_id(client_id)
        models.User.create_user('5678', email='ted@example.com')
        user2 = models.User.lookup(email='ted@example.com')
        client_id2 = channel.ServerChannels.get_client_id([self.server.key], user2)
        channel.ServerChannels.add_client_id(client_id2)
        self.assertEqual([client_id, client_id2], channel.ServerChannels.get_client_ids(self.server.key))

    def test_does_not_add_client_id_to_lookup_store_if_already_exists_there(self):
        client_id = channel.ServerChannels.get_client_id([self.server.key], self.user)
        channel.ServerChannels.add_client_id(client_id)
        channel.ServerChannels.add_client_id(client_id)
        self.assertEqual([client_id], channel.ServerChannels.get_client_ids(self.server.key))


class RemoveServerChannelTest(BaseTest):
    def setUp(self):
        super(RemoveServerChannelTest, self).setUp()
        self.server = models.Server.create()
        models.User.create_user('1234', email='bill@example.com')
        self.user = models.User.lookup(email='bill@example.com')

    def test_removes_client_id_from_lookup_store(self):
        client_id = channel.ServerChannels.get_client_id([self.server.key], self.user)
        channel.ServerChannels.add_client_id(client_id)
        models.User.create_user('5678', email='ted@example.com')
        user2 = models.User.lookup(email='ted@example.com')
        client_id2 = channel.ServerChannels.get_client_id([self.server.key], user2)
        channel.ServerChannels.add_client_id(client_id2)
        channel.ServerChannels.remove_client_id(client_id)
        self.assertEqual([client_id2], channel.ServerChannels.get_client_ids(self.server.key))

    def test_no_ops_if_missing_lookup_entity(self):
        client_id = channel.ServerChannels.get_client_id([self.server.key], self.user)
        channel.ServerChannels.remove_client_id(client_id)
        self.assertEqual([], channel.ServerChannels.get_client_ids(self.server.key))

    def test_no_ops_if_client_id_is_not_in_lookup_store(self):
        client_id = channel.ServerChannels.get_client_id([self.server.key], self.user)
        channel.ServerChannels.add_client_id(client_id)
        models.User.create_user('5678', email='ted@example.com')
        user2 = models.User.lookup(email='ted@example.com')
        client_id2 = channel.ServerChannels.get_client_id([self.server.key], user2)
        channel.ServerChannels.remove_client_id(client_id2)
        self.assertEqual([client_id], channel.ServerChannels.get_client_ids(self.server.key))


class PlayerTest(BaseTest):
    def setUp(self):
        super(PlayerTest, self).setUp()
        self.server = models.Server.create()
        models.User.create_user('1234', email='bill@example.com')
        self.user = models.User.lookup(email='bill@example.com')
        models.User.create_user('1235', email='ted@example.com')
        self.user2 = models.User.lookup(email='ted@example.com')
        self.player = models.Player.get_or_create(self.server.key, 'bill')
        self.player.put()
        self.user.usernames = [self.player.username]
        self.user.put()

    def test_is_user(self):
        self.assertTrue(self.player.is_user(self.user))
        self.assertFalse(self.player.is_user(self.user2))
