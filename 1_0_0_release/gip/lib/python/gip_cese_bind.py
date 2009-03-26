
import sys

from gip_common import voList, cp_get, cp_getBoolean
from pbs_common import getQueueList
from gip_sections import ce, cesebind, se

def getCEList(cp):
    """
    Return a list of all the CE names at this site.

    If WS-GRAM is installed, this might additionally return some WS-GRAM
    entries (this feature is not yet implemented).

    @param cp: Site configuration
    @returns: List of strings containing all the local CE names.
    """
    jobman = cp.get(ce, "job_manager").strip().lower()
    hostname = cp.get(ce, 'name')
    ce_name = '%s:2119/jobmanager-%s-%%s' % (hostname, jobman)
    ce_list = []
    if jobman == 'pbs':
        queue_entries = getQueueList(cp)
        for queue in queue_entries:
            ce_list.append(ce_name % queue)
    else:
        for vo in voList(cp):
             ce_list.append(ce_name % vo)
    return ce_list

def getClassicSEList(cp):
    """
    Return a list of all the ClassicSE's at this site

    @param cp: Site configuration
    @returns: List of all the ClassicSE's unique_ids
    """
    if not cp_getBoolean(cp, "classic_se", "advertise_se", False):
        return []
    classicSE = cp_get(cp, "classic_se", "host", None)
    if not classicSE: # len(classicSE) == 0 or classicSE == None
        return []
    return [classicSE]

def getSEList(cp, classicSEs=True):
    """
    Return a list of all the SE's at this site.

    @param cp: Site configuration.
    @keyword classicSEs: Return list should contain classicSEs; default is True.
    @returns: List of strings containing all the local SE unique_ids.
    """
    simple = cp.getboolean(cesebind, 'simple')
    se_list = []
    if simple:
        se_list = [cp.get(se, 'unique_name')]
    else:
        se_list = eval(cp.get(cesebind, 'se_list'), {})
    if classicSEs:
        se_list.extend(getClassicSEList(cp))
    return se_list

def getCESEBindInfo(cp):
    """
    Generates a list of information for the CESE bind groups.

    Each list entry is a dictionary containing the necessary information for
    filling out a CESE bind entry.

    @param cp: Site configuration
    @returns: List of dictionaries; each dictionary is a CESE bind entry.
    """
    binds = []
    ce_list = getCEList(cp)
    se_list = getSEList(cp, classicSEs = False)
    classicse_list = getClassicSEList(cp)
    se_list.extend(classicse_list)
    access_point = cp_get(cp, "vo", "default", "/")
    if not access_point:
        access_point = "/"
    classic_access_point = cp_get(cp, "osg_dirs", "data", "/")
    for ce in ce_list:
        for se in se_list:
            if se in classicse_list:
                ap = classic_access_point
            else:
                ap = access_point
            info = {'ceUniqueID' : ce,
                    'seUniqueID' : se,
                    'access_point' : ap,
                   }
            binds.append(info)
    return binds

