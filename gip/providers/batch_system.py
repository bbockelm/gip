#!/usr/bin/env python

import os
import sys

sys.path.append(os.path.expandvars("$GIP_LOCATION/lib/python"))
from gip_common import config, cp_get
from gip.providers.generic_batch_system import main as generic_main
from gip_logging import getLogger
log = getLogger("GIP.BatchSystem")

def main():
    cp = config()
    job_manager = cp_get(cp, "ce", "job_manager", None)
    if job_manager:
        log.info("Using job manager %s" % job_manager)
    else:
        log.error("Job manager not specified!")
        sys.exit(2)
    generic_main()

if __name__ == '__main__':
    main()

