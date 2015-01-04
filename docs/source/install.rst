===============
Installing COAL
===============

-------------
Prerequisites
-------------

* A free `Google Cloud Platform <https://cloud.google.com/>`_ account.
* Optional But Recommended: A free `Github <https://github.com/>`_ account.

--------
Versions
--------
^^^^^^^^^^^^^^^^^^^^
Golden Carrot (v1.1)
^^^^^^^^^^^^^^^^^^^^
1. Dynamic world status updates.
2. Better handling of crashed Minecraft server processes.
3. Collapse 'Chats' and 'Players' pages to the world home page.

`Tagged on January 4, 2015 <https://github.com/mc-coal/mc-coal/releases/tag/golden_carrot_v1.1>`_

^^^^^^^^^^
Steak (v1)
^^^^^^^^^^
1. Initial release.

`Tagged on October 20, 2014 <https://github.com/mc-coal/mc-coal/releases/tag/steak_v1>`_

------------
Instructions
------------
1. `Create a Google Cloud Project <https://cloud.google.com/console/project>`_ for your new COAL installation. Take note of the Project ID you select (e.g. `[my-project-id]`).
2. Optionally, in ``Settings``, enable billing. COAL should be able to run comfortably under the daily free App Engine quota for most relatively small, lightly-populated worlds.
3. `Fork <https://help.github.com/articles/fork-a-repo>`_, clone, or download the `MC COAL code repository <https://github.com/mc-coal/mc-coal>`_. Make sure any new fork or clone is a private repository as it will contain sensitive information (like the ``main_SECRET_KEY``).

  .. note:: The master/trunk of the `MC COAL code repository <https://github.com/mc-coal/mc-coal>`_ will always contain the latest tagged, stable release. Ongoing (potentially unstable) development will be done on branches.

4. Change the application name (i.e. ``my-mc-coal``) in the first line of your repository's `app.yaml <app.yaml>`_ to the Project ID you created above.
5. Update your installation settings in your repository's `appengine_config.py <appengine_config.py>`_ file:

  a. Change the ``main_SECRET_KEY`` value to a unique random string. You can use this `random.org link <http://www.random.org/strings/?num=1&len=20&digits=on&upperalpha=on&loweralpha=on&unique=on&format=html&rnd=new>`_ to generate a unique string value.
  b. Change the ``main_TITLE`` and ``main_DESCRIPTION`` to strings that are appropriate for your COAL installation.
  c. You do not have to change ``oauth_SECRET_KEY`` or ``oauth_TOKEN_EXPIRES_IN``. The defaults will work just fine.

6. Complete the sub-steps below if you intend to host worlds on Google Compute Engine:

  a. In ``Settings`` enable billing if you haven't already. There is no daily free Google Compute Engine quota.
  b. In ``APIs``, make sure that ``Google Compute Engine``, ``Google Cloud Storage`` and ``Google Cloud Storage JSON API`` are ``ON``.
  c. In ``Permissions`` make note of the Google Compute Engine service account email address. This should be of the form ``[project number]@developer.gserviceaccount.com`` or ``[project number]@project.gserviceaccount.com``. Also, make sure there is an entry for ``[my-project-id]@appspot.gserviceaccount.com``. If it isn't there, add it as a owner member.
  d. Add the Google Compute Engine service account email address to the ``acl`` section of `queue.yaml <queue.yaml>`_. When finished, the file should look something like this

    ::

      queue:
      - name: default
        rate: 5/s

      - name: controller
        mode: pull
        acl:
        - user_email: 1234567890@developer.gserviceaccount.com

7. Deploy your modified code in either of two ways:

  * Use the `Push-to-Deploy Release Pipeline <https://developers.google.com/cloud/devtools/repo/push-to-deploy>`_ to deploy automatically from your github repository.

    a. Finish the steps under `Setting up a Release Pipeline <https://developers.google.com/cloud/devtools/repo/push-to-deploy#setting_up_a_release_pipeline>`_

    .. note:: You do not have to complete Step 1 (install Git on your local system) if you intend to deploy only from a Github-hosted fork of the `MC COAL code repository <https://github.com/mc-coal/mc-coal>`_.

    b. Click the "Connect to a repository hosted on Github" button.
    c. After authenticating with github, choose the clone or fork of the repository you created in step 3 above.
    d. Choose the "Deploy Source Only" option.
    e. Optionally enter your email address to receive status updates for your deployments.
    f. Make a change to any file in your repository (for instance, add a blank line or comment to `appengine_config.py <appengine_config.py>`_) and save/push the change. This should initiate a deploy. If you entered your email address when setting up the Release Pipeline you should get an email when the deploy completes.

  * If you are familiar with `Google Cloud Platform <https://cloud.google.com/>`_ python development, feel free to use the `App Engine python developer tools <https://developers.google.com/appengine/docs/python/tools/uploadinganapp>`_

8. After the deployment has completed, browse to your COAL administrator page at ``https://[my-project-id].appspot.com/admin``.

  .. note:: It may take a few minutes after an initial successful deployment for database indexes to build. If you get a 500 error response when browing your COAL site right after deployment, you might have to wait a few minutes for the indexes to finish building.

  .. warning:: For bootstrapping purposes, the first user to request this page is made an administrator, so make sure to do this as soon as possible.

=============
World Hosting
=============

There are two options for hosting your minecraft world(s): let your COAL host your world on Google Compute Engine (easy!) or host your world elsewhere (more work for you!). You can mix both kinds of hosted worlds on a single COAL install.

----------------------------------------
Hosting Worlds On Google Compute Engine
----------------------------------------

1. Define a new minecraft version in ``Admin/Define New Minecraft Version/URL``. Enter a version name (i.e. ``1.7.10``) and the URL where the Minecraft Server JAR for that version can be downloaded (i.e. ``https://s3.amazonaws.com/Minecraft.Download/versions/1.7.10/minecraft_server.1.7.10.jar``).

  .. note:: A list of all available versions and server JAR download links is available at `mcversions.net <https://mcversions.net/>`_. COAL has been tested with versions as far back as 1.4.7.

2. Create a new server in ``Admin/Create GCE-Hosted World``. Then hit the play button to start the server. This can take a few minutes if a GCE instance has to be started up for the first time.
3. When the world status is "Playing" the IP address of the server will be shown. Use this IP address to connect your minecraft client to the new world.
4. Play! No additional infrastructure set up needed.
5. Additional administrator settings are available in ``Admin/Configure``.  Here you can modify settings such as the type of machine instance to use (which determines the speed of the CPU and amount of memory available), the size of the disk (larger disks are faster), the number of saved game versions to keep in the cloud, and whether to use a static IP address.

  .. note:: Changes made on the Admin Configuration page won't be live until a new GCE instance is started. To shut down the currently running instance, click the "Kill Instance" button on the ``Admin`` page. To start a new instance, hit "Play" for one of your worlds.

  .. warning:: Make sure all worlds are paused before killing the instance. Failure to do so may result in corrupted world files. Note that large worlds can take a few minutes to shutdown and save.

-------------------------------
Hosting Worlds On Other Servers
-------------------------------

If you already have a Minecraft multi-player world running on a UNIX-based server you can connect it to your COAL.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Hosting Server Prerequisites
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following libraries are required to be installed on the server that is hosting your world.

* Python 2.7
* `pytz <http://pytz.sourceforge.net/>`_
* `pyyaml <http://pyyaml.org/>`_
* `requests <http://docs.python-requests.org/>`_
* `NBT <https://github.com/twoolie/NBT>`_

^^^^^^^^^^^^^^^^^^
Agent Installation
^^^^^^^^^^^^^^^^^^

1. Create a new directory called ``mc-coal`` in your minecraft server's directory (the one with ``server.properties``).
2. Download the following files from your COAL into the new ``mc-coal`` directory:

  ::

    wget https://[my-project-id].appspot.com/mc/timezones.py -o timezones.py
    wget https://[my-project-id].appspot.com/mc/mc_coal_agent.py -o mc_coal_agent.py

3. Download the following files from your COAL into your minecraft server's directory

  ::

    wget https://[my-project-id].appspot.com/mc/log4j2.xml -o log4j2.xml
    wget https://[my-project-id].appspot.com/mc/mc-start.sh -o mc-start.sh
    wget https://[my-project-id].appspot.com/mc/mc-stop.sh -o mc-stop.sh

^^^^^^^^^
Run Agent
^^^^^^^^^

1. Create a new COAL world by clicking the ``Admin/Create External-Server-Hosted World`` and note the ``Agent Client ID`` and ``Agent Secret``.
2. On your Minecraft server host, in the ``mc-coal`` directory, run ``mc_coal_agent.py`` with the ``coal_host``, ``agent_client_id``, and ``agent_secret`` for your server:

  ::

    [~/minecraft-server/mc-coal] $ python mc_coal_agent.py --coal_host=[my-project-id].appspot.com --agent_client_id=mc-coal-agent-12345 --agent_secret=ow9mLT8rev1e8og5AWeN1TyBM7EXZYiCntw8dj4d
    2014-01-01 23:00:01 : main     INFO   Monitoring '../server.log' and reporting to '[my-project-id].appspot.com'...

3. Edit the java configuration parameters within the `mc-start.sh <mc-start.sh>`_ script as desired.
4. Start the minecraft server with the ``mc-start.sh`` script:

  ::

    [~/minecraft-server] $ ./mc-start.sh
    2014-01-21 22:15:09,540 DEBUG Generated plugins in 0.000023000 seconds
    ...
    2014-01-21 22:15:09,588 DEBUG Shutting down OutputStreamManager SYSTEM_OUT
    2014-01-21 22:15:09,588 DEBUG Reconfiguration completed

5. To stop the minecraft server later, use the ``mc-stop.sh`` script:

  ::

    [~/minecraft_server] $ ./mc-stop.sh
    Stopping MineCraft Server PID=5989
    2014-01-22 22:12:19,540 DEBUG ServletContext not present - WebLookup not added
    2014-01-22 22:12:19,541 DEBUG Shutting down FileManager server.log
    MineCraft shutdown complete.
