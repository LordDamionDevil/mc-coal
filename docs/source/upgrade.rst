==============
Upgrading COAL
==============

------------
Instructions
------------
In general, all that is needed to upgrade your existing COAL installation is to deploy the new code from the `MC COAL code repository <https://github.com/mc-coal/mc-coal>`_ taking care to keep your existing changes to `app.yaml <app.yaml>`_ and `appengine_config.py <appengine_config.py>`_.

---------------------------------
Upgrading To Golden Carrot (v1.1)
---------------------------------
This version adds new database indexes. As a result, your COAL installation may return errors until the new indexes are built. This usually only takes a few minutes.

-----------------------
Upgrading To Steak (v1)
-----------------------
This version adds new database indexes. As a result, your COAL installation may return errors until the new indexes are built. This usually only takes a few minutes.
