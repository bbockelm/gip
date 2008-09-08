
"""
Ping the BeStMan SRM server for information.
"""

import os
import re
import tempfile

import gip_testing
from gip_common import cp_get, getLogger
from gip_testing import runCommand

log = getLogger('GIP.Storage.Bestman.srm_ping')

def which(executable):
    """
    Helper function to determine the location of an executable.

    @param executable: Name of the program.
    @returns: Full path to executable, or None if it can't be found.
    """
    for dirname in os.environ.get('PATH', '/bin:/usr/bin'):
        fullname = os.path.join(dirname, executable)
        if os.path.exists(fullname):
            return fullname
    return None

def create_proxy(cp, proxy_filename):
    """
    Attempt to create a very shortlived proxy at a given location.
    """
    #if not which('grid-proxy-init'):
    #    raise ValueError("Could not find grid-proxy-init; perhaps you forgot"\
    #        " to source $VDT_LOCATION/setup.sh in the environment beforehand?")
    usercert = cp_get(cp, "bestman", "usercert", "/etc/grid-security/http/" \
        "httpcert.pem")
    userkey = cp_get(cp, "bestman", "userkey", "/etc/grid-security/http/" \
        "httpkey.pem")
    cmd = 'grid-proxy-init -valid 00:05 -cert %s -key %s -out %s' % \
        (usercert, userkey, proxy_filename)
    fd = runCommand(cmd)
    fd.read()
    if fd.close():
        raise Exception("Unable to create a valid proxy.")

def validate_proxy(cp, proxy_filename):
    """
    Determine that there is a valid proxy at a given location

    @param proxy_filename: The file to check
    @returns: True if the proxy is valid in proxy_filename; False otherwise.
    """
    #if not which('grid-proxy-info'):
    #    raise ValueError("Could not find grid-proxy-info; perhaps you forgot"\
    #        " to source $VDT_LOCATION/setup.sh?")
    cmd = 'grid-proxy-info -f %s' % proxy_filename
    fd = runCommand(cmd)
    fd.read()
    if fd.close():
        return False
    return True

key_re = re.compile('\s*Key=(.+)')
value_re = re.compile('\s*Value=(.+)')
def parse_srm_ping(output):
    """
    Return a dictionary of key-value pairs returned by the SRM backend.
    """
    results = {}
    cur_key = None
    for line in output.splitlines():
        if not cur_key:
            m = key_re.match(line)
            if m:
                cur_key = m.groups()[0]
        else:
            m = value_re.match(line)
            if m:
                val = m.groups()[0]
                results[cur_key] = val
                cur_key = None
    return results

def bestman_srm_ping(cp, endpoint):
    """
    Perform a srm-ping operation against a BeStMan endpoint and return the
    resulting key-value pairs.

    @param cp: Site's Config object
    @param endpoint: Endpoint to query (full service URL).
    """
    endpoint = endpoint.replace('httpg', 'srm')

    # Hardcode the proxy filename in order to play nicely with our testing fmwk.
    if gip_testing.replace_command:
        proxy_filename = '/tmp/http_proxy'
    else:
        fd, proxy_filename = tempfile.mkstemp()
    results = {}
    try:
        create_proxy(cp, proxy_filename)
        validate_proxy(cp, proxy_filename)
        cmd = 'srm-ping %s -proxyfile %s' % (endpoint, proxy_filename)
        fp = runCommand(cmd)
        output = fp.read()
        if fp.close():
            raise ValueError("srm-ping failed.")
        results = parse_srm_ping(output)
    finally:
        try:
            os.unlink(proxy_filename)
        except:
            pass
    return results

