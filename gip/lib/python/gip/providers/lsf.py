#!/usr/bin/python

import re
import sys
import os

sys.path.append(os.path.expandvars("$GIP_LOCATION/lib/python"))
from gip_common import config, VoMapper, getLogger, addToPath, getTemplate, \
    printTemplate, cp_get, ldap_boolean
from gip_cluster import getClusterID
from lsf_common import parseNodes, getQueueInfo, getJobsInfo, getLrmsInfo, \
    getVoQueues
from gip_sections import ce

log = getLogger("GIP.LSF")

def print_CE(cp):
    try:
        lsfVersion = getLrmsInfo(cp)
    except:
        lsfVersion = 'Unknown'
    queueInfo = getQueueInfo(cp)
    try:
        totalCpu, freeCpu, queueCpus = parseNodes(queueInfo, cp)
    except:
        raise
        totalCpu, freeCpu, queueCpus = 0, 0, {}
    ce_name = cp.get(ce, "name")
    CE = getTemplate("GlueCE", "GlueCEUniqueID")
    try:
        excludeQueues = [i.strip() for i in cp.get("lsf", \
            "queue_exclude").split(',')]
    except:
        excludeQueues = []
    vo_queues = getVoQueues(queueInfo, cp)
    for queue, info in queueInfo.items():
        if queue in excludeQueues:
            continue
        if 'running' not in info:
            info['running'] = 0
        if 'status' not in info:
            # There really should be an unknown status...
            info['status'] = 'Closed'
        if 'total' not in info:
            info['total'] = 0
        info["lrmsVersion"] = lsfVersion
        info["job_manager"] = "lsf"
        if info.get("wait", 0) > 0:
            info["free_slots"] = 0
        else:
            if queue in queueCpus:
                info["free_slots"] = queueCpus[queue]
            else:
                info["free_slots"] = freeCpu
        info["queue"] = queue
        info["ceName"] = ce_name
        unique_id = '%s:2119/jobmanager-lsf-%s' % (ce_name, queue)
        info['ceUniqueID'] = unique_id
        if "job_slots" not in info:
            if queue in queueCpus and 'max' in queueCpus[queue]:
                info['job_slots'] = queueCpus[queue]['max']
            else:
                info["job_slots"] = totalCpu
        if "priority" not in info:
            info["priority"] = 0
        if "max_running" not in info:
            info["max_running"] = info["job_slots"]
        elif not info['max_running'] or info['max_running'] == '-':
            info['max_running'] = 999999
        if "max_wall" not in info:
            info["max_wall"] = 0
        info["job_slots"] = min(totalCpu, info["job_slots"])
        info['ert'] = 3600
        info['wrt'] = 3600
        info['hostingCluster'] = cp_get(cp, ce, 'hosting_cluster', ce_name)
        info['hostName'] = cp_get(cp, ce, 'host_name', ce_name)
        info['ceImpl'] = 'Globus'
        info['ceImplVersion'] = cp_get(cp, ce, 'globus_version', '4.0.6')
        info['contact_string'] = unique_id
        info['app_dir'] = cp.get('osg_dirs', 'app')
        info['data_dir'] = cp.get('osg_dirs', 'data')
        info['default_se'] = cp.get('se', 'name')
        info['max_waiting'] = 999999
        info['max_slots'] = 1
        #info['max_total'] = info['max_running']
        info['max_total'] = info['max_waiting'] + info['max_running']
        info['assigned'] = info['job_slots']
        info['lrmsType'] = 'lsf'
        info['preemption'] = ldap_boolean(cp_get(cp, 'lsf', 'preemption', '0'))
        acbr = ''
        for vo, queue2 in vo_queues:
            if queue == queue2:
                acbr += 'GlueCEAccessControlBaseRule: VO:%s\n' % vo.lower()
        if not acbr:
            continue
        #print info
        info['acbr'] = acbr[:-1]
        info['bdii'] = cp.get('bdii', 'endpoint')
        info['gramVersion'] = '2.0'
        info['port'] = 2119
        info['waiting'] = info.get('wait', 0)
        info['clusterUniqueID'] = getClusterID(cp)
        printTemplate(CE, info)
    return queueInfo, totalCpu, freeCpu, queueCpus

def print_VOViewLocal(queue_info, cp):
    ce_name = cp.get(ce, "name")
    vo_map = VoMapper(cp)
    queue_jobs = getJobsInfo(vo_map, cp)
    VOView = getTemplate("GlueCE", "GlueVOViewLocalID")
    vo_queues = getVoQueues(queue_info, cp)
    for vo, queue in vo_queues:
        vo = vo.lower()
        vo_info = queue_jobs.get(queue, {})
        info2 = vo_info.get(vo, {})
        ce_unique_id = '%s:2119/jobmanager-lsf-%s' % (ce_name, queue)
        info = {
            'ceUniqueID'  : ce_unique_id,
            'job_slots'   : queue_info.get(queue, {}).get('job_slots', 0),
            'free_slots'  : queue_info.get(queue, {}).get('free_slots', 0),
            'ce_name'     : ce_name,
            'queue'       : queue,
            'vo'          : vo,
            'voLocalID'   : vo,
            'job_manager' : 'lsf',
            'running'     : info2.get('running', 0),
            'max_running' : info2.get('max_running', 0),
            'priority'    : queue_info.get(queue, {}).get('priority', 0),
            'waiting'     : info2.get('waiting', 0),
            'data'        : cp.get("osg_dirs", "data"),
            'app'         : cp.get("osg_dirs", "app"),
            'default_se'  : cp.get("se", "name"),
            'ert'         : 3600,
            'wrt'         : 3600,
            'acbr'        : 'VO:%s' % vo
        }
        info['total'] = info['waiting'] + info['running']
        printTemplate(VOView, info)

def main():
    try:
        cp = config()
        lsf_path = cp_get(cp, "lsf", "lsf_path", None)
        if lsf_path:
            addToPath(lsf_path)
        vo_map = VoMapper(cp)
        queueInfo, totalCpu, freeCpu, queueCpus = print_CE(cp)
        print_VOViewLocal(queueInfo, cp)
    except Exception, e:
        sys.stdout = sys.stderr
        log.error(e)
        raise

if __name__ == '__main__':
    main()

