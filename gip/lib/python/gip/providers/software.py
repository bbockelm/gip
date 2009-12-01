#!/usr/bin/env python

import os
import sys

sys.path.append(os.path.expandvars("$GIP_LOCATION/lib/python"))
from gip_common import config, getTemplate, printTemplate
from gip_cluster import getApplications, getSubClusterIDs, getClusterID
from gip_logging import getLogger

log = getLogger("GIP.Software")

def print_Locations(cp):
    template = getTemplate("GlueCluster", "GlueLocationLocalID")
    cluster_id = getClusterID(cp)
    for subClusterId in getSubClusterIDs(cp):
        for entry in getApplications(cp):
            entry['subClusterId'] = subClusterId
            entry['clusterId'] = cluster_id
            printTemplate(template, entry)

def main():
    try:
        cp = config()
        print_Locations(cp)
    except Exception, e:
        sys.stdout = sys.stderr
        log.exception(e)
        raise

if __name__ == '__main__':
    main()

