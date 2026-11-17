"""OCT Alveo U280 (UMass) + the 100G ConnectX-5 of pc160-pc163.

Copy of the OCT 'oct-u280' profile (Ubuntu 22.04, tools 2023.2, same post-boot script) with one
change: on pc160-pc163 the ConnectX-5 (eth3) is added to the experiment LAN, so it can reach the
U280s of the other nodes (TRex / hexgen on the host NIC). One LAN holds every port:
U280 eth0/eth1, host eth2 and, on pc160-163, host eth3.

Addresses, node i in the 'nodes' list (i = 0, 1, ...):
  U280 eth0 192.168.40.(10+i)   U280 eth1 192.168.40.(20+i)
  host eth2 192.168.40.(30+i)   host eth3 (ConnectX-5) 192.168.40.(40+i)
"""

import geni.portal as portal
import geni.rspec.pg as pg
import geni.rspec.emulab  # noqa: F401  (Emulab extensions)

HOSTS_WITH_100G = ['pc160', 'pc161', 'pc162', 'pc163']

pc = portal.Context()
request = pc.makeRequestRSpec()

imageList = [('urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU22-64-STD', 'UBUNTU 22.04'),
             ('urn:publicid:IDN+emulab.net+image+emulab-ops//UBUNTU20-64-STD', 'UBUNTU 20.04')]
workflow = ['Vitis', 'Vivado']          # same default as oct-u280
toolVersion = ['2023.2', '2023.1']

pc.defineParameter("nodes", "List of nodes",
                   portal.ParameterType.STRING, "pc162,pc163",
                   longDescription="Comma-separated list of nodes. pc160-pc163 also get their "
                   "100G ConnectX-5 in the LAN.")
pc.defineParameter("workflow", "Workflow",
                   portal.ParameterType.STRING, workflow[0], workflow)
pc.defineParameter("toolVersion", "Tool Version",
                   portal.ParameterType.STRING, toolVersion[0], toolVersion)
pc.defineParameter("osImage", "Select Image",
                   portal.ParameterType.IMAGE, imageList[0], imageList)
pc.defineParameter("remoteDesktop", "Remote Desktop Access",
                   portal.ParameterType.BOOLEAN, False)
pc.defineParameter("tempFileSystemSize", "Temporary Filesystem Size",
                   portal.ParameterType.INTEGER, 0, advanced=True,
                   longDescription="Size in GB of a temporary file system on each node (0 = none).")
pc.defineParameter("tempFileSystemMax", "Temp Filesystem Max Space",
                   portal.ParameterType.BOOLEAN, False, advanced=True,
                   longDescription="Use all free disk space instead of the size above.")
pc.defineParameter("tempFileSystemMount", "Temporary Filesystem Mount Point",
                   portal.ParameterType.STRING, "/mydata", advanced=True)

params = pc.bindParameters()
nodeList = [n.strip() for n in params.nodes.split(',') if n.strip()]
if not nodeList:
    pc.reportError(portal.ParameterError("Give at least one node", ["nodes"]))
pc.verifyParameters()

lan = request.LAN()
lan.best_effort = True

for i, nodeName in enumerate(nodeList):
    host = request.RawPC(nodeName)
    host.component_manager_id = "urn:publicid:IDN+cloudlab.umass.edu+authority+cm"
    host.component_id = nodeName
    host.disk_image = params.osImage

    if params.tempFileSystemSize > 0 or params.tempFileSystemMax:
        bs = host.Blockstore(nodeName + "-bs", params.tempFileSystemMount)
        bs.size = "0GB" if params.tempFileSystemMax else str(params.tempFileSystemSize) + "GB"
        bs.placement = "any"

    cmd = "sudo /local/repository/post-boot.sh {} {} {} >> /local/logs/output_log.txt 2>&1".format(
        params.workflow, params.toolVersion, params.remoteDesktop)
    host.addService(pg.Execute(shell="bash", command=cmd))

    # the FPGA has its own node identity so its ports can be put in the LAN
    fpga = request.RawPC("fpga-" + nodeName)
    fpga.component_manager_id = "urn:publicid:IDN+cloudlab.umass.edu+authority+cm"
    fpga.component_id = "fpga-" + nodeName
    fpga.setUseTypeDefaultImage()
    fpga.SubNodeOf(host)

    host_eth2 = host.addInterface()
    host_eth2.component_id = "eth2"
    host_eth2.addAddress(pg.IPv4Address("192.168.40." + str(i + 30), "255.255.255.0"))
    lan.addInterface(host_eth2)

    if nodeName in HOSTS_WITH_100G:            # the ConnectX-5
        host_eth3 = host.addInterface()
        host_eth3.component_id = "eth3"
        host_eth3.addAddress(pg.IPv4Address("192.168.40." + str(i + 40), "255.255.255.0"))
        lan.addInterface(host_eth3)

    fpga_eth0 = fpga.addInterface()
    fpga_eth0.component_id = "eth0"
    fpga_eth0.addAddress(pg.IPv4Address("192.168.40." + str(i + 10), "255.255.255.0"))
    lan.addInterface(fpga_eth0)
    fpga_eth1 = fpga.addInterface()
    fpga_eth1.component_id = "eth1"
    fpga_eth1.addAddress(pg.IPv4Address("192.168.40." + str(i + 20), "255.255.255.0"))
    lan.addInterface(fpga_eth1)

pc.printRequestRSpec(request)
