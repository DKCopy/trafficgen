local moongen	= require "moongen"
local dpdk	= require "dpdk"
local memory	= require "memory"
local ts	= require "timestamping"
local device	= require "device"
local filter	= require "filter"
local timer	= require "timer"
local stats	= require "stats"
local hist	= require "histogram"
local log	= require "log"
local proto     = require "proto.proto"
local libmoon   = require "libmoon"

-- required here because this script creates *a lot* of mempools
-- memory.enableCache()

local PCI_ID_X710 = 0x80861572
local PCI_ID_XL710 = 0x80861583
local LATENCY_TRIM = 2
local vxlanStack = packetCreate("eth", "ip4", "udp", "vxlan", { "eth", "innerEth" }, {"ip4", "innerIp4"}, {"udp", "innerUdp"})

function intToBoolean(instr)
	if tonumber(instr) > 0 then
		return true
	else
		return false
	end
end

function intsToTable(instr)
	local t = {}
	sep = ","
	for str in string.gmatch(instr, "([^"..sep.."]+)") do
               	table.insert(t, tonumber(str))
	end
	return t
end

function stringsToTable(instr)
	local t = {}
	sep = ","
	for str in string.gmatch(instr, "([^"..sep.."]+)") do
               	table.insert(t, str)
	end
	return t
end

function convertIps(t)
	local u = {}
	for i, v in ipairs(t) do
		local ipU32 = parseIPAddress(v)
		log:info("converting %s to %x", v, ipU32)
		table.insert(u, ipU32)
	end
	return u
end

function convertMacs(t)
	local u = {}
	for i, v in ipairs(t) do
		local macU48 = macToU48(v)
		log:info("converting %s to %x", v, macU48)
		table.insert(u, macU48)
	end
	return u
end

function configure(parser)
	parser:option("--devices", "A comma separated list (no spaces) of one or more Tx/Rx device pairs, for example: 0,1,2,3"):default({0,1}):convert(intsToTable)
	parser:option("--vlanIds", "A comma separated list of one or more VLAN IDs, corresponding to each entry in deviceList.. Using this option enables VLAN tagged packets"):default({}):convert(intsToTable)
	parser:option("--vxlanIds", "A comma separated list of one or more VxLAN IDs, corresponding to each entry in deviceList.  Using this option enables VxLAN encapsulated packets"):default({}):convert(intsToTable)
	parser:option("--size", "Frame size."):default(64):convert(tonumber)
	parser:option("--rate", "Transmit rate in Mpps"):default(1):convert(tonumber)
	parser:option("--measureLatency", "0 or 1"):default(false):convert(intToBoolean)
	parser:option("--calibrateTxRate", "Ensure Tx rate is calibrated before starting test.  Disable only for debugging (and usuually in combination with --nrPackets)."):default(true):convert(intToBoolean)
	parser:option("--bidirectional", "0 or 1"):default(false):convert(intToBoolean)
	parser:option("--nrFlows", "Number of unique network flows"):default(1024):convert(tonumber)
	parser:option("--nrPackets", "Number of packets to send.  Actual number of packets sent can be up to 64 + nrPackets.  The runTime option will be ignored if this is used"):default(0):convert(tonumber)
	parser:option("--runTime", "Number of seconds to run"):default(30):convert(tonumber)
	parser:option("--flowMods", "Comma separated list (no spaces), one or more of:  srcIp,dstIp,srcMac,dstMac,srcPort,dstPort"):default({""}):convert(stringsToTable)
	parser:option("--srcIps", "A comma separated list (no spaces) of source IP address used"):default("10.0.100.2,10.0.101.2"):convert(stringsToTable)
	parser:option("--dstIps", "A comma separated list (no spaces) of destination IP address used"):default("10.0.100.1,10.0.101.1"):convert(stringsToTable)
	parser:option("--gatewayIps", "A comma separated list (no spaces) of gateway (router) IP address used.  For router testing, either this option or dstIps is required"):default(""):convert(stringsToTable)
	parser:option("--srcMacs", "A comma separated list (no spaces) of source MAC address used"):default({}):convert(stringsToTable)
	parser:option("--dstMacs", "A comma separated list (no spaces) of destination MAC address used"):default({}):convert(stringsToTable)
	parser:option("--srcPort", "Source port used"):default(1234):convert(tonumber)
	parser:option("--dstPort", "Destination port used"):default(1234):convert(tonumber)
	parser:option("--encapSrcIps", "A comma separated list (no spaces) of source IP addresses used for inner header (the encapsulated packet)"):default("192.168.100.2,192.168.101.2"):convert(stringsToTable)
	parser:option("--encapDstIps", "A comma separated list (no spaces) of destination IP addresses used for inner header (the excapsulated packet)"):default("192.168.100.1,192.168.101.1"):convert(stringsToTable)
	parser:option("--encapSrcMacs", "A comma separated list (no spaces) of source MAC addresses used for inner header (the encapsulated packet).  If you are using testpmd in a VM, the options --forward-mode=mac --eth-peer=0,A --eth-peer=1,B will need to be used, when A and B are the MACs listed in --encapSrcMacs=A.B"):default({"9e:e9:96:e4:76:01,9e:e9:96:e4:76:02"}):convert(stringsToTable)
	parser:option("--encapDstMacs", "A comma separated list (no spaces) of destination MAC addresses used for inner header (the encapsulated packet).  If you are using testpmd in a VM, these MACs must match the 2 MACs for the two devices used by testpmd"):default({"90:e2:ba:2c:cb:04", "90:e2:ba:01:02:05"}):convert(stringsToTable)
	parser:option("--mppsPerTxQueue", "The maximum transmit rate in Mpps for each device queue"):default(8):convert(tonumber)
	parser:option("--mppsPerRxQueue", "The maximum receive rate in Mpps for each device queue"):default(8):convert(tonumber)
	parser:option("--queuesPerTxTask", "The maximum transmit number of queues to use per task"):default(1):convert(tonumber)
	parser:option("--linkSpeed", "The speed in Gbps of the device(s)"):default(10):convert(tonumber)
	parser:option("--maxLossPct", "The maximum frame loss percentage tolerated"):default(0.002):convert(tonumber)
	parser:option("--rateTolerance", "Stop the test if the specified transmit rate drops by this amount, in Mpps"):default(0.25):convert(tonumber)
	parser:option("--packetDumpInterval", "Print the contents of every nth packet received.  This will affect Rx performance and can drop packets.  Use only for debugging."):default(0):convert(tonumber)
end

function master(args)
	args.txMethod = "hardware"
	--the number of transmit queues -not- including queues for measuring latency
	local numTxQueues = 1 + math.floor(args.rate / args.mppsPerTxQueue)
	--the number of receive queues -not- including queues for measuring latency or listening to ARP requests
	--when using RSS, the number of queues needs to be a power of 2
	x = args.rate
	local numRxQueues = 1
	x = x / args.mppsPerRxQueue
	while x > 1 do
		x = x / args.mppsPerRxQueue
		numRxQueues = numRxQueues * 2
	end
	log:info("number rx queues: %d", numRxQueues)
	local devs = {}

	--parseIPAddresses(args.srcIps)
	--parseIPAddresses(args.dstIps)
	
	-- The connections[] table defines a relationship between te device which transmits and a device which receives the same packets.
	-- This relationship is derived via the devices[] table, where if devices contained {a, b, c, d}, device a transmits to device b,
	-- and device c transmits to device d.  
	-- If bidirectional traffic is enabled, the reverse is also true, and device b transmits to device a and d to c.
	connections = {}
	for i, deviceNum in ipairs(args.devices) do -- devices = {a, b, c, d} a sends packets to b, c sends packets to d
		-- initialize the devices
		log:info("configuring device %d with %d tx queues and %d rx queues", deviceNum, numTxQueues, numRxQueues)
		if args.measureLatency == true then 
			devs[i] = device.config{
						port = args.devices[i],
			 			txQueues = numTxQueues + 2,
			 			rxQueues = numRxQueues + 2,
						rxDescs = 2048,
						rssQueues = numRxQueues
						}
		else
			devs[i] = device.config{
						port = args.devices[i],
			 			txQueues = numTxQueues + 1,
			 			rxQueues = numRxQueues + 1,
						rxDescs = 2048,
						rssQueues = numRxQueues
						}
		end
		--devs[i]:setPromisc(false)

		-- configure the connections
		if ( i % 2 == 1) then -- for devices a, c
			connections[i] = i + 1  -- device a transmits to device b, device c transmits to device d 
			log:info("device %d transmits to device %d", args.devices[i], args.devices[connections[i]]);
			if args.bidirectional == true then
				connections[i + 1] = i  -- device b transmits to device a, device d transmits to device c
				log:info("device %d transmits to device %d", args.devices[connections[i]], args.devices[i]);
			end
		end
	end
	for i, deviceNum in ipairs(args.devices) do 
		-- assign vlan IDs
		if args.vlanIds[i] then
			log:info("device %d will use vlan ID: [%d]", deviceNum, args.vlanIds[i])
			--devs[i]:filterVlan(args.vlanIds[i])
		end
		-- assign device's native HW MAC if user does not provide one
		if not args.srcMacs[i] then
			args.srcMacs[i] = devs[i]:getMacString()
		end
	end

	-- start a task for each dev to listen/respond to ARP
	local arpQueuePairs = {}
	for txDevId, txDev in ipairs(devs) do
		if connections[txDevId] then
			table.insert(arpQueuePairs, { rxQueue = txDev:getRxQueue(numRxQueues), txQueue = txDev:getTxQueue(numTxQueues), ips = { args.srcIps[txDevId] }} )
		end
	end
	moongen.startTask(proto.arp.arpTask, arpQueuePairs)

	-- assign the dst MAC addresses
	for i, deviceNum in ipairs(args.devices) do
		if connections[i] then
			-- in a L2 test, the dst MAC is just assigned the src MAC from the corresponding Rx device.
			-- However, if an L3 test (router), we want the MAC of the router.  So, before using 
			-- the src MAC, try to ARP request the MAC for gatewayIp.  If there is no reply, then
			-- just use the src MAC.  In order for a ARP request to happen, you must not use the
			-- --dstMacs option and use must use the --gatewayIps option.
			if not args.dstMacs[i] and args.gatewayIps[i] then
				log:info("looking up MAC for IP %s", args.gatewayIps[i])
				args.dstMacs[i] = proto.arp.blockingLookup(args.gatewayIps[i], 5)
				log:info("got MAC %s for IP %s", args.dstMacs[i], args.gatewayIps[i])
			end
			if not args.dstMacs[i] then
				log:info("no ARP reponse, assigning device %d src MAC", args.devices[connections[i]])
				args.dstMacs[i] = args.srcMacs[connections[i]]
			end
			log:info("device %d when transmitting packets will use src MAC: [%s] src IP [%s] dst MAC: [%s] dst IP [%s]", deviceNum, args.srcMacs[i], args.srcIps[i], args.dstMacs[i], args.dstIps[i])
			-- if VxLAN is used, this is for the inner packet
			if args.vxlanIds[i] then
				if not args.encapDstMacs[i] and connections[i] then
					args.encapDstMacs[i] = args.encapSrcMacs[connections[i]]
				end
				log:info("device %d when transmitting encapsulated packets over VxLAN ID %d, the inner packet will use src MAC: [%s] src IP [%s] dst MAC: [%s] dst IP [%s]", deviceNum, args.vxlanIds[i], args.encapSrcMacs[i], args.encapSrcIps[i], args.encapDstMacs[i], args.encapDstIps[i])
			else
			end
		end
	end
	args.srcMacsU48 = convertMacs(args.srcMacs)
	args.dstMacsU48 = convertMacs(args.dstMacs)
	args.encapSrcMacsU48 = convertMacs(args.encapSrcMacs)
	args.encapDstMacsU48 = convertMacs(args.encapDstMacs)
	args.srcIpsU32 = convertIps(args.srcIps)
	args.dstIpsU32 = convertIps(args.dstIps)
	args.encapSrcIpsU32 = convertIps(args.encapSrcIps)
	args.encapDstIpsU32 = convertIps(args.encapDstIps)
	device.waitForLinks()
	
	filterEther = false
	filterTs = false
	filterTuple = false
	for i, deviceNum in ipairs(args.devices) do 
		-- add a filter for the IP address of the receiving device
		if connections[i] then -- if this device transmits
			rxDevId = connections[i]  -- this is the receicing device
			if filterEther == true then
				devs[rxDevId]:l2Filter(0x0800, devs[rxDevId]:getRxQueue(1))
			end
			if filterTs == true then
				devs[rxDevId]:filterUdpTimestamps(devs[rxDevId]:getRxQueue(1))
			end
			if filterTuple == true then
				log:info("filter srcIp: %s", args.srcIps[i])
				log:info("filter dstIp: %s", args.dstIps[i])
				devs[rxDevId]:fiveTupleFilter({
								dstIp = args.dstIps[i],
								srcIp = args.srcIps[i],
								srcPort = 1234, dstPort = 1234,
								proto = 0x11}, devs[rxDevId]:getRxQueue(1))
			end
		end
	end
	local txTasksPerDev = math.ceil(numTxQueues / args.queuesPerTxTask)
	local taskId
	local devStatsTask
	local txTasks = {}
	local rxTasks = {}
	local timerTasks = {}

	-- start single task to output all device level Tx/Rx stats
	devStatsTask = moongen.startTask("devStats", devs, connections)

	-- a little time to ensure rx threads are ready
	moongen.sleepMillis(1000)

	-- default the calibratedRate to args.rate
	taskId = 1
	local calibratedRate = {}
	for txDevId, v in ipairs(devs) do
		if connections[txDevId] then
			calibratedRate[txDevId] = {}
			for perDevTaskId = 0, txTasksPerDev - 1 do
					calibratedRate[txDevId][perDevTaskId] = args.rate
				taskId = taskId + 1
			end
		end
	end

	--calibrate the Tx rate
	if args.calibrateTxRate == true then
		taskId = 1
		for txDevId, v in ipairs(devs) do
			if connections[txDevId] then
				rxDevId = connections[txDevId]
				printf("calibrating %.2f Mfps", args.rate)
				for perDevTaskId = 0, txTasksPerDev - 1 do
					local txQueues = getTxQueues(args.queuesPerTxTask, numTxQueues, perDevTaskId, devs[txDevId])
					txTasks[taskId] = moongen.startTask("calibrateTx", args, perDevTaskId, txQueues, txDevId, txTasksPerDev, numTxQueues)
					taskId = taskId + 1
				end
			end
		end
		-- wait for tx devices to finish
		taskId = 1
		--local calibratedRate = {}
		for txDevId, v in ipairs(devs) do
			if connections[txDevId] then
				--calibratedRate[txDevId] = {}
				for perDevTaskId = 0, txTasksPerDev - 1 do
						calibratedRate[txDevId][perDevTaskId] = txTasks[taskId]:wait()
					taskId = taskId + 1
				end
			end
		end

		-- drain the rx queues
		taskId = 1
		for txDevId, v in ipairs(devs) do
			if connections[txDevId] then
				rxDevId = connections[txDevId]
				for perDevTaskId = 0, numRxQueues - 1 do -- always 1 rx queue per rx task
					rxTasks[taskId] = moongen.startTask("drainRx", args, perDevTaskId, devs[rxDevId]:getRxQueue(perDevTaskId), rxDevId)
					taskId = taskId + 1
				end
			end
		end
		taskId = 1
		for txDevId, v in ipairs(devs) do
			if connections[txDevId] then
				for perDevTaskId = 0, numRxQueues - 1 do
					rxTasks[taskId]:wait()
					taskId = taskId + 1
				end
			end
		end

		log:info("Tx calibration finished")
	end

	-- start the rx tasks
	taskId = 1
	for txDevId, v in ipairs(devs) do
		if connections[txDevId] then
			rxDevId = connections[txDevId]
			for perDevTaskId = 0, numRxQueues - 1 do
				rxTasks[taskId] = moongen.startTask("rx", args, perDevTaskId, devs[rxDevId]:getRxQueue(perDevTaskId), rxDevId)
				taskId = taskId + 1
			end
		end
	end
	-- a little time to ensure rx threads are ready
	moongen.sleepMillis(2000)

	-- start the tx tasks
	taskId = 1
	for txDevId, v in ipairs(devs) do
		if connections[txDevId] then
			rxDevId = connections[txDevId]
			printf("Testing %.2f Mfps", args.rate)
			for perDevTaskId = 0, txTasksPerDev - 1 do
				local txQueues = getTxQueues(args.queuesPerTxTask, numTxQueues, perDevTaskId, devs[txDevId])
				txTasks[taskId] = moongen.startTask("tx", args, perDevTaskId, txQueues, txDevId, calibratedRate[txDevId][perDevTaskId], txTasksPerDev, numTxQueues)
				taskId = taskId + 1
			end
			if args.measureLatency == true then
				-- latency measurements do not involve a dedicated task for each direction of traffic
				if not timerTasks[connections[txDevId]] then
					local latencyQueues = getTimerQueues(devs, txDevId, args, numTxQueues, numRxQueues, connections)
					log:info("timer queues: %s", dumpQueues(latencyQueues))
					timerTasks[txDevId] = moongen.startTask("timerSlave", args, latencyQueueIds)
				end
			end
		end
	end
	-- wait for tx devices to finish
	taskId = 1
	totalTxPackets = 0
	local perDevTxStats = {}
	for txDevId, v in ipairs(devs) do
		if connections[txDevId] then
			perDevTxStats[txDevId] = {}
			perDevTxStats[txDevId].txCount = 0
			perDevTxStats[txDevId].txRate = 0
			for perDevTaskId = 0, txTasksPerDev - 1 do
					local txStats = txTasks[taskId]:wait()
					perDevTxStats[txDevId].txCount = perDevTxStats[txDevId].txCount + txStats.txCount
					perDevTxStats[txDevId].txRate = perDevTxStats[txDevId].txRate + txStats.txRate
					totalTxPackets = totalTxPackets + txStats.txCount
				taskId = taskId + 1
			end
		end
	end

	-- give time for the packet to come back
	moongen.sleepMillis(1000)
	moongen.stop()
	local perDevRxStats = {}
	taskId = 1
	totalRxPackets = 0
	for txDevId, v in ipairs(devs) do
		perDevTotalRxPackets = 0
		if connections[txDevId] then
			rxDevId = connections[txDevId]
			for perDevTaskId = 0, numRxQueues - 1 do
				perDevTotalRxPackets = perDevTotalRxPackets + rxTasks[taskId]:wait()
				taskId = taskId + 1
			end
			local rxPacketRate = perDevTxStats[txDevId].txRate * perDevTotalRxPackets / perDevTxStats[txDevId].txCount
			local rxPacketLoss = perDevTxStats[txDevId].txCount - perDevTotalRxPackets
			local rxPacketLossPct = 100 * rxPacketLoss / perDevTxStats[txDevId].txCount
			log:info("[%d]->[%d] txPackets: %d rxPackets: %d packetLoss: %d txRate: %f rxRate: %f packetLossPct: %f",
				args.devices[txDevId], args.devices[rxDevId],
				perDevTxStats[txDevId].txCount, perDevTotalRxPackets, rxPacketLoss,
				perDevTxStats[txDevId].txRate, rxPacketRate, rxPacketLossPct)
		end
		totalRxPackets = totalRxPackets + perDevTotalRxPackets
	end
	log:info("totalRxPackets: %d", totalRxPackets)
	log:info("totalDroppedPackets: %d (%.6f%%)", totalTxPackets - totalRxPackets, 100*(totalTxPackets - totalRxPackets)/totalTxPackets)

	for txDevId, v in ipairs(devs) do
		if connections[txDevId] then
			rxTasks[txDevId]:wait()
			if args.measureLatency == true then
				if not timerTasks[connections[txDevId]] then
					timerTasks[txDevId]:wait()
				end
			end
		end
	end
	devStatsTask:wait()
end

function getRxQueues(queuesPerTask, numQueues, taskId, dev)
	local queues = {}
	local firstQueueId = taskId * queuesPerTask
	local lastQueueId = firstQueueId + queuesPerTask - 1
	if lastQueueId > (numQueues - 1) then
		lastQueueId = numQueues - 1
	end
	for queueId = firstQueueId, lastQueueId do
		table.insert(queues, dev:getRxQueue(queueId))
	end
	return queues
end

function getTxQueues(txQueuesPerTask, numTxQueues, taskId, dev)
	local queues = {}
	local firstQueueId = taskId * txQueuesPerTask
	local lastQueueId = firstQueueId + txQueuesPerTask - 1
	if lastQueueId > (numTxQueues - 1) then
		lastQueueId = numTxQueues - 1
	end
	for queueId = firstQueueId, lastQueueId do
		table.insert(queues, dev:getTxQueue(queueId))
	end
	return queues
end

function getTimerQueues(devs, devId, args, txQueueId, rxQueueId, connections)
	-- build a table of one or more pairs of queues
	log:info("txQueueId: %d rxQueueId: %d", txQueueId, rxQueueId)
	local queueIds = { devs[devId]:getTxQueue(txQueueId), devs[connections[devId]]:getRxQueue(rxQueueId) }
	-- If this is a bidirectional test, add another queue-pair for the other direction:
	if connections[connections[devId]] then
		table.insert(queueIds, devs[connections[devId]]:getTxQueue(txQueueId))
		table.insert(queueIds, devs[devId]:getRxQueue(rxQueueId))
	end
	return queueIds
end

function adjustHeaders(devId, bufs, packetCount, args)
	for _, buf in ipairs(bufs) do
		local pkt = buf:getUdpPacket()
		local ethernetPacket = buf:getEthernetPacket()
		local flowId = packetCount % args.nrFlows

		for _,v in ipairs(args.flowMods) do

			if ( v == "srcPort" ) then
				pkt.udp:setSrcPort((args.srcPort + flowId) % 65536)
			end
	
			if ( v == "dstPort" ) then
				pkt.udp:setDstPort((args.srcPort + flowId) % 65536)
			end
	
			if ( v == "srcIp" ) then
				pkt.ip4.src:set(args.srcIpsU32[devId] + flowId)
			end
	
			if ( v == "dstIp" ) then
				pkt.ip4.dst:set(args.dstIpsU32[devId] + flowId)
			end
	
			if ( v == "srcMac" ) then
				local addr = args.srcMacsU48[devId] + flowId * 256
				ethernetPacket.eth.src.uint8[4] = bit.band(bit.rshift(addr, 8), 0xFF) 
				ethernetPacket.eth.src.uint8[3] = bit.band(bit.rshift(addr, 16), 0xFF) 
				ethernetPacket.eth.src.uint8[2] = bit.band(bit.rshift(addr, 24), 0xFF)
			end
	
			if ( v == "dstMac" ) then
				local addr = args.dstMacsU48[devId] + flowId * 256
				--ethernetPacket.eth.dst.uint8[5] = bit.band(addr, 0xFF)
				ethernetPacket.eth.dst.uint8[4] = bit.band(bit.rshift(addr, 8), 0xFF) 
				ethernetPacket.eth.dst.uint8[3] = bit.band(bit.rshift(addr, 16), 0xFF) 
				ethernetPacket.eth.dst.uint8[2] = bit.band(bit.rshift(addr, 24), 0xFF)
				--ethernetPacket.eth.dst.uint8[1] = bit.band(bit.rshift(addr + 0ULL, 32ULL), 0xFF)
				--ethernetPacket.eth.dst.uint8[0] = bit.band(bit.rshift(addr + 0ULL, 40ULL), 0xFF)
			end
		end

		packetCount = packetCount + 1
	end
	return packetCount
end

function getBuffers(devId, args, sizeWithoutCrc)
	local mem = memory.createMemPool(function(buf)
		if args.vxlanIds[devId] then
			local pkt = vxlanStack(buf)
			pkt:fill{
				pktLength = sizeWithoutCrc,
				-- outer header for VxLAN
				vxlanVNI = args.vxlanIds[devId],
				ethSrc = args.srcMacs[devId],
				ethDst = args.dstMacs[devId],
				ip4Src = args.srcIps[devId],
				ip4Dst = args.dstIps[devId],
				udpSrc = proto.udp.PORT_VXLAN,
				udpDst = proto.udp.PORT_VXLAN,
				-- inner header for VxLAN
				innerEthSrc = args.encapSrcMacs[devId],
				innerEthDst = args.encapDstMacs[devId],
				innerIp4Src = args.encapSrcIps[devId],
				innerIp4Dst = args.encapDstIps[devId],
				innerUdpSrc = args.srcPort,
				innerUdpDst = args.dstPort,
			}
			pkt.innerIp4:calculateChecksum()
		else
			buf:getUdpPacket():fill{
				pktLength = sizeWithoutCrc,
				ethSrc = args.srcMacs[devId],
				ethDst = args.dstMacs[devId],
				ip4Src = args.srcIps[devId],
				ip4Dst = args.dstIps[devId],
				udpSrc = args.srcPort,
				udpDst = args.dstPort
			}
		end
	end)
	local bufs = mem:bufArray()
	return bufs
end

function dumpQueues(queues)
	local queuesStr = ""
	local queue
	for _, queue in ipairs(queues)  do
		queuesStr = queuesStr..queue:__tostring()
	end
	return queuesStr
end

function dumpTable(table, indent)
	local indentString = ""

	for i=1,indent,1 do
		indentString = indentString.."\t"
	end

	for key,value in pairs(table) do
		if type(value) == "table" then
			log:info("%s%s => {", indentString, key)
			dumpTable(value, indent+1)
			log:info("%s}", indentString)
		else
			log:info("%s%s: %s", indentString, key, value)
		end
	end
end

function dumpTestParams(args)
	log:info("args => {")
	dumpTable(args, 1)
	log:info("}")
end

function devStats(devs, connections)
	local rxStats = {}
	local txStats = {}

	for txDevId, v in ipairs(devs) do
		if connections[txDevId] then
			rxDevId = connections[txDevId]
			txStats[txDevId] = stats:newDevTxCounter(devs[txDevId], "plain")
			rxStats[rxDevId] = stats:newDevRxCounter(devs[rxDevId], "plain")
		end
	end

	while moongen.running() do
		for txDevId, v in ipairs(devs) do
			if connections[txDevId] then
				rxDevId = connections[txDevId]
				txStats[txDevId]:update()
				rxStats[rxDevId]:update()
			end
		end
	end

	for txDevId, v in ipairs(devs) do
		if connections[txDevId] then
			rxDevId = connections[txDevId]
			txStats[txDevId]:finalize()
			rxStats[rxDevId]:finalize()
		end
	end
end

function setTxRate(txDev, txQueues, rate, txMethod, size, numTxQueues, numTxTasks)
	local pci_id = txDev:getPciId()
	if ( txMethod == "hardware" ) then
        	if pci_id == PCI_ID_X710 or pci_id == PCI_ID_XL710 then
			log:warn("[setTxRate]setting rate for whole device to %f instead of per-queue since this device does not support per-queue rates", rate)
                	txDev:setRate(rate * (size + 4) * 8)
		else
			local queue
			for _ , queue in pairs(txQueues)  do
				queue:setRateMpps(rate / numTxQueues / numTxTasks, size)
			end
		end
	end
end

function calibrateTx(args, taskId, txQueues, txDevId, txTasksPerDev, numTxQueues)
	local txDev = txQueues[1].dev
	local desiredRate = args.rate
	local sizeWithoutCrc
	local rate = desiredRate / 2 -- start at half the rate and let it ramp up
	if args.vxlanIds[txDevId] then
		sizeWithoutCrc = args.size - 4 + 50
	else
		sizeWithoutCrc = args.size - 4
	end
	local bufs = getBuffers(txDevId, args, sizeWithoutCrc)
	log:info("[calibrateTx] %s taskId: %d rate: %.4f txQueues: %s", txDev, taskId, desiredRate, dumpQueues(txQueues))
	local packetId = 0
	local measuredRate = 0
	setTxRate(txDev, txQueues, rate, args.txMethod, args.size, numTxQueues, txTasksPerDev)
	local txCount = 0
	local calibrateRatio = 1
	local rateDiffRatio = 0.995
	local rateDiffDelta = 0.05
	local start = libmoon.getTime()
	local count = 0
	-- just like The-Price-Is-Right, measuredRate needs to get very very close to arge.rate, but not go over
	while moongen.running() and (measuredRate/desiredRate < rateDiffRatio) and (desiredRate - measuredRate > rateDiffDelta) or (measuredRate > desiredRate) do
		bufs:alloc(sizeWithoutCrc)
		if args.flowMods then
			packetId = adjustHeaders(txDevId, bufs, packetId, args, srcMacs, dstMacs)
			
		end
		if (args.vlanIds[txDevId]) then
			bufs:setVlans(args.vlanIds[txDevId])
		end
                bufs:offloadUdpChecksums()
		if ( args.txMethod == "hardware" ) then
			local queue
			for _, queue in ipairs(txQueues)  do
				txCount = txCount + queue:send(bufs)
			end
		else
			for _, buf in ipairs(bufs) do
				buf:setRate(rate)
			end
			local queue
			for _ , queue in pairs(txQueues)  do
				txCount = txCount + queue:sendWithDelay(bufs)
			end
		end
		stop = libmoon.getTime()
		elapsedTime = stop - start
		if stop - start > .1 then
			measuredRate = txCount / elapsedTime / 1000000
			txCount = 0
			rate = rate * desiredRate / measuredRate
			calibrateRatio = rate / desiredRate
			log:info("[calibrateTx] %s taskId: %d measuredrate: %f, new calbrateRatio: %f new adjusted rate: %f", txDev, taskId, measuredRate, calibrateRatio, rate)
			setTxRate(txDev, txQueues, rate, args.txMethod, args.size, numTxQueues, txTasksPerDev)
			start = libmoon.getTime()
			count = count + 1
			-- over time lower the threshold for an acceptable calibrated rate
			if count % 20 == 0 then
				log:warn("[calibrateTx] %s taskId: %d, rateDiff adjusted due to many calibration attempts", txDev, taskId)
				rateDiffRatio = rateDiffRatio - 0.001
				rateDiffDelta = rateDiffDelta + 0.01
			end
		end
	end
	log:info("[calibrateTx] %s calibrateRatio: %f", txDev, calibrateRatio)

	log:info("[calibrateTx] warming up for another 30 seconds")
	start = libmoon.getTime()
	while moongen.running() and elapsedTime < 30 do
		bufs:alloc(sizeWithoutCrc)
		if args.flowMods then
			packetId = adjustHeaders(txDevId, bufs, packetId, args, srcMacs, dstMacs)
			
		end
		if (args.vlanIds[txDevId]) then
			bufs:setVlans(args.vlanIds[txDevId])
		end
                bufs:offloadUdpChecksums()
		if ( args.txMethod == "hardware" ) then
			local queue
			for _, queue in ipairs(txQueues)  do
				txCount = txCount + queue:send(bufs)
			end
		else
			for _, buf in ipairs(bufs) do
				buf:setRate(rate)
			end
			local queue
			for _ , queue in pairs(txQueues)  do
				txCount = txCount + queue:sendWithDelay(bufs)
			end
		end
		stop = libmoon.getTime()
		elapsedTime = stop - start
	end

        return rate
end

function tx(args, taskId, txQueues, txDevId, calibratedRate, txTasksPerDev, numTxQueues)
	local txDev = txQueues[1].dev
	local sizeWithoutCrc
	if args.vxlanIds[txDevId] then
		sizeWithoutCrc = args.size - 4 + 50
	else
		sizeWithoutCrc = args.size - 4
	end
	local bufs = getBuffers(txDevId, args, sizeWithoutCrc)
	log:info("[tx] txDev: %s  taskId: %d  rate: %.4f calibratedRate: %.4f txQueues: %s", txDev, taskId, args.rate, calibratedRate, dumpQueues(txQueues))

	if args.runTime > 0 then
		runtime = timer:new(args.runTime)
	end
	
	setTxRate(txDev, txQueues, calibratedRate, args.txMethod, args.size, numTxQueues, txTasksPerDev)
	local packetId = 0
	local txCount = 0
	local start = libmoon.getTime()
	while (args.runTime == 0 or runtime:running()) and moongen.running() do
		bufs:alloc(sizeWithoutCrc)
		if args.flowMods then
			packetId = adjustHeaders(txDevId, bufs, packetId, args, srcMacs, dstMacs)
		end
		if (args.vlanIds[txDevId]) then
			bufs:setVlans(args.vlanIds[txDevId])
		end
                bufs:offloadUdpChecksums()
		if txCount == 0 then
					bufs[1]:dump()
		end
		if ( args.txMethod == "hardware" ) then
			local queue
			for _, queue in ipairs(txQueues)  do
				txCount = txCount + queue:send(bufs)
			end
		else
			for _, buf in ipairs(bufs) do
				buf:setRate(calibratedRate)
			end
			local queue
			for _ , queue in pairs(txQueues)  do
				txCount = txCount + queue:sendWithDelay(bufs)
			end
		end
		if args.nrPackets > 0 and txCount > args.nrPackets then
			break
		end
	end
	local stop = libmoon.getTime()
	local elapsedTime = stop - start
	local txRate = txCount / elapsedTime / 1000000
	for _ , queue in pairs(txQueues)  do
		log:info("[tx] %s packets: %d rate: %f", queue, txCount, txRate)
	end
        return {txCount = txCount, txRate = txRate}
end

function drainRx(args, perDevTaskId, queue, rxDevId)
	log:info("[drainRx] rxDev: %s  taskId: %d  rate: %.4f queue: %s", queue.dev, perDevTaskId, args.rate, queue)
	local rxDev = queue.dev
	local totalPkts = 0
	local bufs = memory.bufArray(64)

	for j = 1, 1024 do
		--log:info("drainRx: queue: %s calling recv", queue)
		numPkts = queue:tryRecv(bufs,250)
		bufs:free(numPkts)
		--log:info("drainRx: queue: %s finished recv with %d packets", queue, numPkts)
		if numPkts == 0 then
			log:info("[drainRx] queue %s total rx packets: %d", queue, totalPkts)
			return totalPkts
		end
		totalPkts = totalPkts + numPkts
		--log:info("drainRx: queue: %s loop count: %d num packets: %d", queue, j, numPkts)
	end
	log:info("[drainRx] %s packets: %d", queue, totalPkts)
	return totalPkts
end

function rx(args, perDevTaskId, queue, rxDevId)
	local rxDev = queue.dev
	local totalPkts = 0
	local totalTestPkts = 0
	local bufs = memory.bufArray(128)
	if args.vxlanIds[rxDevId] then
		log:info("[rx] vxlan: rxDev: %s  taskId: %d  rate: %.4f queue: %s", queue.dev, perDevTaskId, args.rate, queue)
		while moongen.running() do
			numPkts = queue:recv(bufs)
			for i = 1, numPkts do
				local buf = bufs[i]
                        	local pkt = buf:getVxlanPacket()
				if pkt.eth:getType() == proto.eth.TYPE_IP
			   	and pkt.ip4:getProtocol() == proto.ip4.PROTO_UDP
			   	and pkt.udp:getDstPort() == proto.udp.PORT_VXLAN then
					totalTestPkts = totalTestPkts + 1
				end
				totalPkts = totalPkts + 1
				if args.packetDumpInterval > 0 and totalPkts % args.packetDumpInterval == 1 then
					log:info("[rx] queue: %s packet number %d", queue, totalPkts)
					buf:dump()
				end
			end
			bufs:free(numPkts)
		end
	else
		log:info("[rx] non-vxlan: rxDev: %s  taskId: %d  rate: %.4f queue: %s", queue.dev, perDevTaskId, args.rate, queue)
		while moongen.running() do
			numPkts = queue:recv(bufs)
			for i = 1, numPkts do
				local buf = bufs[i]
                        	local pkt = buf:getUdpPacket()
				if buf:getSize() == args.size - 4
				and pkt.eth:getType() == proto.eth.TYPE_IP
			   	and pkt.ip4:getProtocol() == proto.ip4.PROTO_UDP
			   	and pkt.udp:getDstPort() == args.dstPort then
					totalTestPkts = totalTestPkts + 1
				--else
					--log:info("[rx] queue: %s non-test packet:", queue)
					--buf:dump()
				end
				totalPkts = totalPkts + 1
				if args.packetDumpInterval > 0 and totalPkts % args.packetDumpInterval == 1 then
					log:info("[rx] queue: %s packet number %d", queue, totalPkts)
					buf:dump()
				end
			end
			bufs:free(numPkts)
		end
	end
        if args.vxlanIds[rxDevId] then
		log:info("[rx] %s VxLAN test packets: %d, non-test packets: %d", queue, totalTestPkts, totalPkts - totalTestPkts)
		return totalTestPkts
	else
		log:info("[rx] %s test packets: %d, non-test packets: %d", queue, totalTestPkts, totalPkts - totalTestPkts)
		return totalTestPkts
	end
end


function saveSampleLog(file, samples, label)
	log:info("Saving sample log to '%s'", file)
	file = io.open(file, "w+")
	file:write("samples,", label, "\n")
	for i,v in ipairs(samples) do
		file:write(i, ",", v, "\n")
	end
	file:close()
end

function saveHistogram(file, hist, label)
	output = io.open(file, "w")
	output:write("bucket,", label, "\n")
	hist:save(output)
	output:close()
end

function timerSlave(args, queueIds)
	local hist1, hist2, haveHisto1, haveHisto2, timestamper1, timestamper2
	local transactionsPerDirection = 1 -- the number of transactions before switching direction
	local frameSizeWithoutCrc = args.size - 4
	local rateLimit = timer:new(0.001) -- less than 1000 samples per second
	local sampleLog1 = {}
	local sampleLog2 = {}

	-- TODO: adjust headers for flows

	if args.bidirectional == true then
		log:info("timerSlave: bidirectional testing from %d->%d and %d->%d", queueIds[1].id, queueIds[2].id, queueIds[3].id, queueIds[4].id)
	else
		log:info("timerSlave: unidirectional testing from %d->%d", queueIds[1].id, queueIds[2].id)
	end
	
	hist1 = hist()
	if args.size < 76 then
		log:warn("Latency packets are not UDP due to requested size (%d) less than minimum UDP size (76)", args.size)
		timestamper1 = ts:newTimestamper(queueIds[1], queueIds[2])
	else
		timestamper1 = ts:newUdpTimestamper(queueIds[1], queueIds[2])
	end
	if args.bidirectional == true then
		if args.size < 76 then
			timestamper2 = ts:newTimestamper(queueIds[3], queueIds[4])
		else
			timestamper2 = ts:newUdpTimestamper(queueIds[3], queueIds[4])
		end
		hist2 = hist()
	end
	-- timestamping starts after and finishes before the main packet load starts/finishes
	moongen.sleepMillis(LATENCY_TRIM)
	if args.runTime > 0 then
		local actualRunTime = args.runTime - LATENCY_TRIM/1000*2
		runTimer = timer:new(actualRunTime)
		log:info("Latency test to run for %d seconds", actualRunTime)
	else
		log:warn("Latency args.runTime is 0")
	end
	local timestamper = timestamper1
	local hist = hist1
	local sampleLog = sampleLog1
	local haveHisto = false
	local haveHisto1 = false
	local haveHisto2 = false
	local counter = 0
	local counter1 = 0
	local counter2 = 0
	while (args.runTime == 0 or runTimer:running()) and moongen.running() do
		for count = 0, transactionsPerDirection - 1 do -- inner loop tests in one direction
			rateLimit:wait()
			counter = counter + 1
			local lat = timestamper:measureLatency(args.size);
			if (lat) then
				haveHisto = true;
                		hist:update(lat)
				sampleLog[counter] = lat
			else
				sampleLog[counter] = -1
			end
			rateLimit:reset()
		end
		if args.bidirectional == true then
			if timestamper == timestamper2 then
				timestamper = timestamper1
				hist = hist1
				sampleLog = sampleLog1
				haveHisto2 = haveHisto
				haveHisto = haveHisto1
				counter2 = counter
				counter = counter1
			else
				timestamper = timestamper2
				hist = hist2
				sampleLog = sampleLog2
				haveHisto1 = haveHisto
				haveHisto = haveHisto2
				counter1 = counter
				counter = counter2
			end
		else
			haveHisto1 = haveHisto
			counter1 = counter
		end
	end
	moongen.sleepMillis(LATENCY_TRIM + 1000) -- the extra 1000 ms ensures the stats are output after the throughput stats
	local histDesc = "Histogram port " .. ("%d"):format(queueIds[1].id) .. " to port " .. ("%d"):format(queueIds[2].id) .. " at rate " .. args.rate .. " Mpps"
	local histFile = "dev:" .. ("%d"):format(queueIds[1].id) .. "-" .. ("%d"):format(queueIds[2].id) .. "_rate:" .. args.rate .. ".csv"
	local headerLabel = "Dev:" .. ("%d"):format(queueIds[1].id) .. "->" .. ("%d"):format(queueIds[2].id) .. " @ " .. args.rate .. " Mpps"
	if haveHisto1 then
		hist1:print(histDesc)
		saveHistogram("latency:histogram_" .. histFile, hist1, headerLabel)
		local hist_size = hist1:totals()
		if hist_size ~= counter1 then
		   log:warn("[%s] Lost %d samples (%.2f%%)!", histDesc, counter1 - hist_size, (counter1 - hist_size)/counter1*100)
		end
		saveSampleLog("latency:samples_" .. histFile, sampleLog1, headerLabel)
	else
		log:warn("no latency samples found for %s", histDesc)
	end
	if args.bidirectional == true then
		local histDesc = "Histogram port " .. ("%d"):format(queueIds[3].id) .. " to port " .. ("%d"):format(queueIds[4].id) .. " at rate " .. args.rate .. " Mpps"
		local histFile = "dev:" .. ("%d"):format(queueIds[3].id) .. "-" .. ("%d"):format(queueIds[4].id) .. "_rate:" .. args.rate .. ".csv"
		local headerLabel = "Dev:" .. ("%d"):format(queueIds[3].id) .. "->" .. ("%d"):format(queueIds[4].id) .. " @ " .. args.rate .. " Mpps"
		if haveHisto2 then
			hist2:print(histDesc)
			saveHistogram("latency:histogram_" .. histFile, hist2, headerLabel)
			local hist_size = hist2:totals()
			if hist_size ~= counter2 then
			   log:warn("[%s] Lost %d samples (%.2f%%)!", histDesc, counter2 - hist_size, (counter2 - hist_size)/counter2*100) 
			end
			saveSampleLog("latency:samples_" .. histFile, sampleLog2, headerLabel)
		else
			log:warn("no latency samples found for %s", histDesc)
		end
	end
end

function macToU48(mac)
	-- this is similar to parseMac, but maintains ordering as represented in the input string
	local bytes = {string.match(mac, '(%x+)[-:](%x+)[-:](%x+)[-:](%x+)[-:](%x+)[-:](%x+)')}
	if bytes == nil then
	return
	end
	for i = 1, 6 do
	if bytes[i] == nil then
			return
		end
		bytes[i] = tonumber(bytes[i], 16)
		if  bytes[i] < 0 or bytes[i] > 0xFF then
			return
		end
	end

	local acc = 0
	for i = 1, 6 do
		acc = acc + bytes[i] * 256 ^ (6 - i)
	end
	return acc
end
