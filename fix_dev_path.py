#!/usr/bin/env python
import fix_path  # noqa
import os
import sys

for d in os.environ["PATH"].split(":"):
    dev_appserver_path = os.path.join(d, "dev_appserver.py")
    if os.path.isfile(dev_appserver_path):
        sdk_path = os.path.abspath(os.path.dirname(os.path.realpath(dev_appserver_path)))
        sys.path.append(sdk_path)
        import dev_appserver
        dev_appserver.fix_sys_path()
