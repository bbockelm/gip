
"""
Common function which provide information about the Condor batch system.

This module interacts with condor through the following commands:
   * condor_q
   * condor_status

It takes advantage of the XML format of the ClassAds in order to make parsing
easier.
"""

import sys
import gip_sets as sets
import time
import types

from gip_logging import getLogger
from gip_common import voList, cp_getBoolean, cp_get, voList, VoMapper, cp_getInt
from gip.batch_systems.condor_handlers import *

condor_version = "condor_version"
condor_group = "condor_config_val -negotiator GROUP_NAMES"
condor_quota = "condor_config_val -negotiator GROUP_QUOTA_%(group)s"
condor_prio = "condor_config_val -negotiator GROUP_PRIO_FACTOR_%(group)s"
condor_status = "condor_status -xml -constraint '%(constraint)s'"
condor_status_submitter = "condor_status -submitter -xml"
condor_job_status = "condor_q -xml -constraint '%(constraint)s'"

log = getLogger("GIP.Condor")

def getLrmsInfo(cp): #pylint: disable-msg=C0103
    """
    Get information from the LRMS (batch system).

    Returns the version of the condor client on your system.

    @returns: The condor version
    @rtype: string
    """
    for line in condorCommand(condor_version, cp):
        if line.startswith("$CondorVersion:"):
            version = line[15:].strip()
            log.info("Running condor version %s." % version)
            return version
    ve = ValueError("Bad output from condor_version.")
    log.exception(ve)
    raise ve

def getGroupInfo(vo_map, cp): #pylint: disable-msg=C0103,W0613
    """
    Get the group info from condor

    The return value is a dictionary; the key is the vo name, the values are
    another dictionary of the form {'quota': integer, 'prio': integer}

    @param vo_map: VoMapper object
    @param cp: A ConfigParse object with the GIP config information
    @returns: A dictionary whose keys are VO groups and values are the quota
        and priority of the group.
    """
    fp = condorCommand(condor_group, cp)
    output = fp.read().split(',')
    if fp.close():
        log.info("No condor groups found.")
        return {}
    retval = {}
    if (not (output[0].strip().startswith('Not defined'))) and \
            (len(output[0].strip()) > 0):
        for group in output:
            group = group.strip()
            quota = condorCommand(condor_quota, cp, \
                {'group': group}).read().strip()
            prio = condorCommand(condor_prio, cp, \
                {'group': group}).read().strip()
            vos = guessVO(cp, group)
            if not vos:
                continue
            curInfo = {'quota': 0, 'prio': 0, 'vos': vos}
            try:
                curInfo['quota'] += int(quota)
            except:
                pass
            try:
                curInfo['prio'] += int(prio)
            except:
                pass
            retval[group] = curInfo
    log.debug("The condor groups are %s." % ', '.join(retval.keys()))
    return retval

def getQueueList(cp): #pylint: disable-msg=C0103
    """
    Returns a list of all the queue names that are supported.

    @param cp: Site configuration
    @returns: List of strings containing the queue names.
    """
    vo_map = VoMapper(cp)
    # Determine the group information, if there are any Condor groups
    try:
        groupInfo = getGroupInfo(vo_map, cp)
    except Exception, e:
        log.exception(e)
        # Default to no groups.
        groupInfo = {}

    # Set up the "default" group with all the VOs which aren't already in a 
    # group
    groupInfo['default'] = {'prio': 999999, 'quota': 999999, 'vos': sets.Set()}
    all_group_vos = []
    for val in groupInfo.values():
        all_group_vos.extend(val['vos'])
    defaultVoList = voList(cp, vo_map=vo_map)
    defaultVoList = [i for i in defaultVoList if i not in all_group_vos]
    groupInfo['default']['vos'] = defaultVoList
    if not groupInfo['default']['vos']:
        del groupInfo['default']

    return groupInfo.keys()

def determineGroupVOsFromConfig(cp, group, voMap):
    """
    Given a group name and the config object, determine the VOs which are
    allowed in that group; this is based solely on the config files.
    """

    # This is the old behavior.  Base everything on (groupname)_vos
    bycp = cp_get(cp, "condor", "%s_vos" % group, None)
    if bycp:
        return [i.strip() for i in bycp.split(',')]

    # This is the new behavior.  Base everything on (groupname)_blacklist and
    # (groupname)_whitelist.  Done to mimic the PBS configuration.
    volist = sets.Set(voList(cp, voMap))
    try:
        whitelist = [i.strip() for i in cp.get("condor", "%s_whitelist" % \
            group).split(',')]
    except:
        whitelist = []
    whitelist = sets.Set(whitelist)
    try:
        blacklist = [i.strip() for i in cp.get("condor", "%s_blacklist" % \
            group).split(',')]
    except:
        blacklist = []
    blacklist = sets.Set(blacklist)

    # Return None if there's no explicit white/black list setting.
    if len(whitelist) == 0 and len(blacklist) == 0:
        return None

    # Force any VO in the whitelist to show up in the volist, even if it
    # isn't in the acl_users / acl_groups
    for vo in whitelist:
        if vo not in volist:
            volist.add(vo)
    # Apply white and black lists
    results = sets.Set()
    for vo in volist:
        if (vo in blacklist or "*" in blacklist) and ((len(whitelist) == 0)\
                or vo not in whitelist):
            continue
        results.add(vo)
    return list(results)

def guessVO(cp, group):
    """
    From the group name, guess my VO name
    """
    mapper = VoMapper(cp)
    bycp = determineGroupVOsFromConfig(cp, group, mapper)
    vos = voList(cp, vo_map=mapper)
    byname = sets.Set()
    for vo in vos:
        if group.find(vo) >= 0:
            byname.add(vo)
    altname = group.replace('group', '')
    altname = altname.replace('-', '')
    altname = altname.replace('_', '')
    altname = altname.strip()
    try:
        bymapper = mapper[altname]
    except:
        bymapper = None
    if bycp != None:
        return bycp
    elif bymapper:
        return [bymapper]
    elif byname:
        return byname
    else:
        return [altname]

_results_cache = {}
def _getJobsInfoInternal(cp):
    """
    The "alternate" way of building the jobs info; this allows for sites to
    filter jobs based upon an arbitrary condor_q constraint.

    This is not the default as large sites can have particularly bad performance
    for condor_q.
    """
    global _results_cache
    if _results_cache:
        return dict(_results_cache)
    constraint = cp_get(cp, "condor", "jobs_constraint", "TRUE")
    fp = condorCommand(condor_job_status, cp, {'constraint': constraint})
    handler = ClassAdParser('GlobalJobId', ['JobStatus', 'Owner',
        'AccountingGroup', 'FlockFrom']);
    fp2 = condorCommand(condor_status_submitter, cp)
    handler2 = ClassAdParser('Name', ['MaxJobsRunning'])
    try:
        for i in range(cp_getInt(cp, "condor", "condor_q_header_lines", 3)):
            fp.readline()
        parseCondorXml(fp, handler)
    except Exception, e:
        log.error("Unable to parse condor output!")
        log.exception(e)
        return {}
    try:
        parseCondorXml(fp2, handler2)
    except Exception, e:
        log.error("Unable to parse condor output!")
        log.exception(e)
        return {}
    info = handler2.getClassAds()
    for item, values in handler.getClassAds().items():
        if 'AccountingGroup' in values and 'Owner' in values and values['AccountingGroup'].find('.') < 0:
            owner = '%s.%s' % (values['AccountingGroup'], values['Owner'])
        else:
            owner = values.get('AccountingGroup', values.get('Owner', None))
        if not owner:
            continue
        owner_info = info.setdefault(owner, {})
        status = values.get('JobStatus', -1)
        try:
            status = int(status)
        except:
            continue
        is_flocked = values.get('FlockFrom', False) != False
        # We ignore states Unexpanded (U, 0), Removed (R, 2), Completed (C, 4),
        # Held (H, 5), and Submission_err (E, 6)
        if status == 1: # Idle
            owner_info.setdefault('IdleJobs', 0)
            owner_info['IdleJobs'] += 1
        elif status == 2: # Running
            if is_flocked:
                owner_info.setdefault('FlockedJobs', 0)
                owner_info['FlockedJobs'] += 1
            else:
                owner_info.setdefault('RunningJobs', 0)
                owner_info['RunningJobs'] += 1
        elif status == 5: # Held
            owner_info.setdefault('HeldJobs', 0)
            owner_info['HeldJobs'] += 1
    _results_cache = dict(info)
    return info

def getJobsInfo(vo_map, cp):
    """
    Retrieve information about the jobs in the Condor system.

    Query condor about the submitter status.  The returned job information is
    a dictionary whose keys are the VO name of the submitting user and values
    the aggregate information about that VO's activities.  The information is
    another dictionary showing the running, idle, held, and max_running jobs
    for that VO.

    @param vo_map: A vo_map object mapping users to VOs
    @param cp: A ConfigParser object with the GIP config information.
    @returns: A dictionary containing job information.
    """
    group_jobs = {}
    queue_constraint = cp_get(cp, "condor", "jobs_constraint", "TRUE")
    if queue_constraint == 'TRUE':
        fp = condorCommand(condor_status_submitter, cp)
        handler = ClassAdParser(('Name', 'ScheddName'), ['RunningJobs',
            'IdleJobs', 'HeldJobs', 'MaxJobsRunning', 'FlockedJobs'])
        try:
            parseCondorXml(fp, handler)
        except Exception, e:
            log.error("Unable to parse condor output!")
            log.exception(e)
        results = handler.getClassAds()
    else:
        results = _getJobsInfoInternal(cp)
    def addIntInfo(my_info_dict, classad_dict, my_key, classad_key):
        """
        Add some integer info contained in classad_dict[classad_key] to 
        my_info_dict[my_key]; protect against any thrown exceptions.
        If classad_dict[classad_key] cannot be converted to a number,
        default to 0.
        """
        if my_key not in my_info_dict or classad_key not in classad_dict:
            return
        try:
            new_info = int(classad_dict[classad_key])
        except:
            new_info = 0
        my_info_dict[my_key] += new_info

    all_group_info = getGroupInfo(vo_map, cp)

    unknown_users = sets.Set()
    for user, info in results.items():
        # Determine the VO, or skip the entry
        if isinstance(user, types.TupleType):
            user = user[0]
        name = user.split("@")[0]
        name_info = name.split('.', 1)
        if len(name_info) == 2:
            group, name = name_info
        else:
            group = 'default'
        log.debug("Examining jobs for group %s, user %s." % (group, name))
        try:
            vo = vo_map[name].lower()
        except Exception, e:
            if name in all_group_info:
                group = name
                if len(all_group_info[name].get('vo', [])) == 1:
                    vo = all_group_info[name]['vo']
                else:
                    vo = 'unknown'
            else:
                unknown_users.add(name)
            continue

        vo_jobs = group_jobs.setdefault(group, {})

        # Add the information to the current dictionary.
        my_info = vo_jobs.get(vo, {"running":0, "idle":0, "held":0, \
            'max_running':0})
        addIntInfo(my_info, info, "running", "RunningJobs")
        if cp_getBoolean(cp, "condor", "count_flocked", False):
            addIntInfo(my_info, info, "running", "FlockedJobs")
        addIntInfo(my_info, info, "idle", "IdleJobs")
        addIntInfo(my_info, info, "held", "HeldJobs")
        addIntInfo(my_info, info, "max_running", "MaxJobsRunning")
        vo_jobs[vo] = my_info

    log.warning("The following users are non-grid users: %s" % \
        ", ".join(unknown_users))

    log.info("Job information: %s." % group_jobs)

    return group_jobs

_nodes_cache = []
def parseNodes(cp):
    """
    Parse the condor nodes.

    @param cp: ConfigParser object for the GIP
    @returns: A tuple consisting of the total, claimed, and unclaimed nodes.
    """
    global _nodes_cache #pylint: disable-msg=W0603
    if _nodes_cache:
        return _nodes_cache
    subtract = cp_getBoolean(cp, "condor", "subtract_owner", True)
    log.debug("Parsing condor nodes.")
    constraint = cp_get(cp, "condor", "status_constraint", "TRUE")
    fp = condorCommand(condor_status, cp, {'constraint': constraint})
    handler = ClassAdParser('Name', ['State'])
    parseCondorXml(fp, handler)
    total = 0
    claimed = 0
    unclaimed = 0
    for info in handler.getClassAds().values():
        total += 1
        if 'State' not in info:
            continue
        if info['State'] == 'Claimed':
            claimed += 1
        elif info['State'] == 'Unclaimed':
            unclaimed += 1
        elif subtract and info['State'] == 'Owner':
            total -= 1
    log.info("There are %i total; %i claimed and %i unclaimed." % \
             (total, claimed, unclaimed))
    _nodes_cache = total, claimed, unclaimed
    return total, claimed, unclaimed

