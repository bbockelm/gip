
"""
Testing framework for the GIP.

This allows one to replace output from command-line invocations with saved
outputs from the test/command_output directory.
"""

import os
import re
import sys
import types
import unittest
import datetime
import urlparse
import GipUnittest

from gip_common import cp_get, cp_getBoolean, pathFormatter, parseOpts, config
from gip_ldap import getSiteList, prettyDN

replace_command = False

commands = {}

def lookupCommand(cmd):
    cmd = cmd.strip()
    env = os.environ['GIP_TESTING']
    m = re.match("suffix=(.*)", env)
    suffix = None
    if m:
        suffix = m.groups()[0]
    if cmd not in commands:
        fd = open(os.path.expandvars("$VDT_LOCATION/test/command_output/" \
            "commands"))
        for line in fd:
            if line.startswith("#") or len(line.strip()) == 0:
                continue
            command, val = line.split(':', 1)
            val = val.strip()
            command = command.strip()
            if suffix:
                command = '%s_%s' % (command, suffix)
            commands[val.strip()] = command
    return commands[cmd]

def runCommand(cmd, force_command=False):
    if replace_command and not force_command:
        try:
            filename = lookupCommand(cmd)
        except Exception, e:
            print >> sys.stderr, e
            return runCommand(cmd, force_command=True)
        return open(os.path.expandvars("$VDT_LOCATION/test/command_output/%s" \
            % filename))
    else:
        return os.popen(cmd)

def generateTests(cp, cls, args=[]):
    """
    Given a class and args, generate a test case for every site in the BDII.

    @param cp: Site configuration
    @type cp: ConfigParser
    @param cls: Test class to use to generate a test suite.  It is assumed
        that the constructor for this class has signature cls(cp, site_name)
    @type cls: class
    @keyword args: List of sites; if it is not empty, then tests will only be
        generated for the given sites.
    """
    try:
        sites = cp_get(cp, "gip_tests", "site_names", "")
        sites = [i.strip() for i in sites.split(',')]
    except:
        sites = getSiteList(cp)

    kw, passed, args = parseOpts(sys.argv[1:])
    tests = []
    for site in sites:
        if len(args) > 0 and site not in args:
            continue
        if site == 'local' or site == 'grid':
            continue
        case = cls(site, cp)
        tests.append(case)
    return unittest.TestSuite(tests)

def streamHandler(cp):
    """
    Given the ConfigParser, find the preferred stream for test output

    @param cp: Site configuration
    @type cp: ConfigParser
    """

    streamName = cp_get(cp, "TestRunner", "StreamName", "")
    if (streamName is None) or (streamName == ""):
        return sys.stderr
    elif (streamName.lower() == "stdout") or (streamName.lower() == "sys.stdout"):
        return sys.stdout
    elif (streamName.lower() == "file"):
        logDir = pathFormatter(cp_get(cp, "TestRunner", "LogDir", "/tmp"))
        logPrefix = cp_get(cp, "TestRunner", "LogPrefix", "")
        logFile = logDir + "/" + logPrefix \
            + datetime.datetime.now().strftime("%A_%b_%d_%Y_%H_%M_%S")
        return open(logFile, 'w')

def runTest(cp, cls, out=None, per_site=True):
    """
    Given a test class, generate and run a test suite

    @param cp: Site configuration
    @type cp: ConfigParser
    @param cls: Test class to use to generate a test suite.  It is assumed
        that the constructor for this class has signature cls(cp, site_name).
        If per_site=False, then the signature is assumed to be cls().
    @type cls: class
    @keyword per_site: Set to true if there is one instance of the test class
        per site.
    @param out: A stream where the output from the test suite is logged
    @type out: stream
    """
    usexml = cp_getBoolean(cp, "gip_tests", "use_xml")
    if per_site:
        testSuite = generateTests(cp, cls, sys.argv[1:])
    else:
        testSuite = suite = unittest.TestLoader().loadTestsFromTestCase(cls)
        try:
            for test in testSuite:
                try:
                    test.__init__(cp)
                except:
                    continue
        except:
            pass

    if usexml:
        testRunner = GipUnittest.GipXmlTestRunner()
    else:
        if out is None:
            #testRunner = unittest.TextTestRunner(verbosity=2)
            testRunner = GipUnittest.GipTextTestRunner(verbosity=2)
        else:
            #testRunner = unittest.TextTestRunner(stream=out, verbosity=2)
            testRunner = GipUnittest.GipTextTestRunner(stream=out, verbosity=2)
    result = testRunner.run(testSuite)
    sys.exit(not result.wasSuccessful())

def runlcginfo(opt, bdii="is.grid.iu.edu", port="2170", VO="ops"):
    cmd = "lcg-info " + opt + " --vo " + VO + " --bdii " + bdii + ":" + port
    print >> sys.stderr, cmd
    return runCommand(cmd)

def runlcginfosites(bdii="is.grid.iu.edu", VO="ops", opts_list=[]):
    cmd = "lcg-infosites --is " + bdii + " --vo " + VO + " "
    for opt in opts_list:
        cmd += opt + " "
    return runCommand(cmd)

def interpolateConfig(cp):
    if cp_get(cp, "gip_tests", "site_names", "") == "":
        cp.set("gip_tests", "site_names", cp_get(cp, "site", "name", ""))

    if cp_get(cp, "gip_tests", "site_dns", "") == "":
        host_parts = cp_get(cp, "ce", "name", "").split('.')
        site_dns = "%s.%s" % (host_parts[:-2], host_parts[:-1])
        cp.set("gip_tests", "site_dns", site_dns)

    if cp_get(cp, "gip_tests", "required_site", "") == "":
        cp.set("gip_tests", "required_sites", cp_get(cp, "gip_tests", "site_names", ""))

    grid = cp_get(cp, "site", "group", "")
    cp.set("gip_tests", "bdii_port", "2170")
    cp.set("gip_tests", "egee_port", "2170")
    cp.set("gip_tests", "interop_url", "http://oim.grid.iu.edu/publisher/get_osg_interop_bdii_ldap_list.php?grid=%s&format=html" % grid)
    if "ITB" in grid:
        cp.set("gip_tests", "bdii_addr", "is-itb2.grid.iu.edu")
        cp.set("gip_tests", "egee_bdii", "pps-bdii.cern.ch")
        cp.set("gip_tests", "egee_bdii_conf_url", "http://egee-pre-production-service.web.cern.ch/egee-pre-production-service/bdii/pps-all-sites.conf")
        web_server = "http://is-itb2.grid.iu.edu/cgi-bin/"
    else:
        cp.set("gip_tests", "bdii_addr", "is.grid.iu.edu")
        cp.set("gip_tests", "egee_bdii", "lcg-bdii.cern.ch")
        cp.set("gip_tests", "egee_bdii_conf_url", "http://lcg-bdii-conf.cern.ch/bdii-conf/bdii.conf")
        web_server = "http://is.grid.iu.edu/cgi-bin/"

    cp.set("gip_tests", "update_url", web_server + "status.cgi")
    cp.set("gip_tests", "schema_check_url", web_server + "show_source_data?which=%s&source=cemon")
    cp.set("gip_tests", "validator_url", web_server + "show_source_data?which=%s&source=served")


def getTestConfig(args):
    cp = config()
    try:
        cp.readfp(open(os.path.expandvars('$GIP_LOCATION/etc/gip_tests.conf')))
    except:
        pass

    interpolateConfig(cp)

    section = "gip_tests"
    if not cp.has_section(section):
        cp.add_section(section)

    try:
        xml = args[1]
        if xml == "xml":
            args.pop(1)
            cp.set(section, "use_xml", "True")
        else:
            cp.set(section, "use_xml", "False")
    except:
        cp.set(section, "use_xml", "False")

    return cp
