#!/usr/bin/env python

import os, sys, re, socket

sys.path.append(os.path.expandvars("$GIP_LOCATION/lib/python"))
from gip_common import config, getTemplate, getLogger
from gip_storage import connect_admin, getSESpace, getSEVersion, getSETape, \
    seHasTape

def print_se(cp):
    try:
        admin = connect_admin(cp)
        used, available, total = getSESpace(cp, admin, total=True, gb=True)
        version = getSEVersion
        status = "Production"
    except:
        used = 0
        available = 0
        total = 0
        version = "1.8.0"
        status = "Closed"
    seTemplate = getTemplate("GlueSE", "GlueSEUniqueID")
    if seHasTape(cp):
        arch = "tape"
    else:
        arch = "multi-disk"
    nu, nf, nt = getSETape(cp) 
    siteUniqueID = cp.get("site", "unique_name")
    bdiiEndpoint = cp.get("bdii", "endpoint") + ("/mds-vo-name=%s," \
        "mds-vo-name=local,o=grid" % siteUniqueID)
    info = { 'seName'         : cp.get("se", "name"),
             'seUniqueID'     : cp.get("se", "unique_name"),
             'implementation' : 'dcache',
             "version"        : version,
             "status"         : status,
             "port"           : 8443,
             "onlineTotal"    : total,
             "nearlineTotal"  : nt,
             "onlineUsed"     : used,
             "nearlineUsed"   : nu,
             "architecture"   : arch,
             "free"           : available,
             "total"          : total,
             "bdiiEndpoint"   : bdiiEndpoint,
             "siteUniqueID"   : siteUniqueID,
             "arch"           : arch,
           }
    print seTemplate % info

def print_access_protocols(cp, admin):
    sename = cp.get("se", "unique_name")
    results = admin.execute("LoginBroker", "ls")
    accessTemplate = getTemplate("GlueSE", "GlueSEAccessProtocolLocalID")
    for line in results.split('\n'):
        if len(line.strip()) == 0:
            continue
        doorname, kind, versions, host, logins, dummy = line.split(';')
        protocol, version = versions[1:-1].split(',')
        hostname, port = host[1:-1].split(':')
        hostname = hostname.split(',')[0]
        try:
            hostname = socket.getfqdn(hostname)
        except:
            pass
        endpoint = "%s://%s:%i" % (protocol, hostname, int(port))
        securityinfo = ''
        if protocol == 'gsiftp':
            securityinfo = "gsiftp"
        elif protocol == 'dcap':
            securityinfo = "none"
        else:
            securityinfo = "none"
        info = {'accessProtocolId': doorname,
                'seUniqueID'      : sename,
                'protocol'        : protocol,
                'endpoint'        : endpoint,
                'capability'      : 'file transfer',
                'maxStreams'      : 10,
                'security'        : securityinfo,
                'port'            : port
               }
        print accessTemplate % info

def print_srm(cp, admin):
    sename = cp.get("se", "unique_name")
    sitename = cp.get("dcache_config", "site_name")
    vos = [i.strip() for i in cp.get("vo", "vos").split(',')]
    serviceTemplate = getTemplate("GlueService", "GlueServiceUniqueID")
    acbr_tmpl = '\nGlueServiceAccessControlRule: %s'
    acbr = ''
    for vo in vos:
        acbr += acbr_tmpl % vo
    results = admin.execute("srm-LoginBroker", "ls")
    for line in results.split("\n"):
        if len(line.strip()) == 0:
            continue
        doorname, kind, versions, host, logins, dummy = line.split(';')
        protocol, version = versions[1:-1].split(',')
        hostname, port = host[1:-1].split(':')
        hostname = hostname.split(',')[0]
        try:
            hostname = socket.getfqdn(hostname)
        except:
            pass
        info = {"serviceID"   : endpoint,
                "serviceName" : endpoint,
                "serviceType" : "SRM",
                "uri"         : endpoint,
                "url"         : endpoint,
                "acbr"        : acbr,
                "siteID"      : sitename,
                "cpLocalID" : doorname,
                "seUniqueID" : sename,
                "protocolType" : "SRM",
                "capability" : "control",
               }

        info['version'] = "1.1.0"
        info['endpoint'] = "httpg://%s:%i/srm/managerv1" % (hostname, int(port))
        print ControlTemplate % info
        print ServiceTemplate % info

        info['version'] = "2.0.0"
        info['endpoint'] = "httpg://%s:%i/srm/managerv2" % (hostname, int(port))
        print ControlTemplate % info
        print ServiceTemplate % info

def main():
    try:
        cp = config("$GIP_LOCATION/etc/dcache_storage.conf", \
            "$GIP_LOCATION/etc/dcache_password.conf", \
            "$GIP_LOCATION/etc/tape_info.conf")
        print_se(cp)
        admin = connect_admin(cp)
        print_access_protocols(cp, admin)
        print_srm(cp, admin)
    except:
        # Make sure we don't feed the error to the BDII stream;
        # fail silently, hopefully someone logs the stderr.
        sys.stdout = sys.stderr
        raise

if __name__ == '__main__':
    main()

