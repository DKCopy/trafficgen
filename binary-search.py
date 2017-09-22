#!/bin/python -u

from __future__ import print_function

import sys, getopt
import argparse
import subprocess
import re
# import stl_path
import time
import json
import string
import threading
import thread
import select
import signal
import copy
# from decimal import *
# from trex_stl_lib.api import *

class t_global(object):
     args=None;

def sigint_handler(signal, frame):
     print('binary-search.py: CTRL+C detected and ignored')

def process_options ():
    parser = argparse.ArgumentParser(usage=""" 
    Conduct a binary search to find the maximum packet rate within acceptable loss percent
    """);

    parser.add_argument('--output-dir',
                        dest='output_dir',
                        help='Directory where the output should be stored',
                        default="./"
                        )
    parser.add_argument('--frame-size', 
                        dest='frame_size',
                        help='L2 frame size in bytes or IMIX',
                        default="64"
                        )
    parser.add_argument('--num-flows', 
                        dest='num_flows',
                        help='number of unique network flows',
                        default=1024,
                        type = int,
                        )
    parser.add_argument('--use-src-ip-flows', 
                        dest='use_src_ip_flows',
                        help='implement flows by source IP',
                        default=1,
                        type = int,
                        )
    parser.add_argument('--use-dst-ip-flows', 
                        dest='use_dst_ip_flows',
                        help='implement flows by destination IP',
                        default=1,
                        type = int,
                        )
    parser.add_argument('--use-src-mac-flows', 
                        dest='use_src_mac_flows',
                        help='implement flows by source MAC',
                        default=1,
                        type = int,
                        )
    parser.add_argument('--use-dst-mac-flows', 
                        dest='use_dst_mac_flows',
                        help='implement flows by destination MAC',
                        default=1,
                        type = int,
                        )
    parser.add_argument('--use-src-port-flows',
                        dest='use_src_port_flows',
                        help='implement flows by source port',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--use-dst-port-flows',
                        dest='use_dst_port_flows',
                        help='implement flows by destination port',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--use-protocol-flows',
                        dest='use_protocol_flows',
                        help='implement flows by IP protocol',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--use-encap-src-ip-flows', 
                        dest='use_encap_src_ip_flows',
                        help='implement flows by source IP in the encapsulated packet',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--use-encap-dst-ip-flows', 
                        dest='use_encap_dst_ip_flows',
                        help='implement flows by destination IP in the encapsulated packet',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--use-encap-src-mac-flows', 
                        dest="use_encap_src_mac_flows",
                        help='implement flows by source MAC in the encapsulated packet',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--use-encap-dst-mac-flows', 
                        dest="use_encap_dst_mac_flows",
                        help='implement flows by destination MAC in the encapsulated packet',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--one-shot', 
                        dest='one_shot',
                        help='0 = run regular binary seach, 1 = run single trial',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--run-bidirec', 
                        dest='run_bidirec',
                        help='0 = Tx on first device, 1 = Tx on both devices',
                        default=1,
                        type = int,
                        )
    parser.add_argument('--run-revunidirec',
                        dest='run_revunidirec',
                        help='0 = Tx on first device, 1 = Tx on second devices',
                        default=0,
                        type = int,
                        )
    parser.add_argument('--validation-runtime', 
                        dest='validation_runtime',
                        help='tiral period in seconds during final validation',
                        default=30,
                        type = int,
                        )
    parser.add_argument('--search-runtime', 
                        dest='search_runtime',
                        help='tiral period in seconds during binary search',
                        default=30,
                        type = int,
                        )
    parser.add_argument('--sniff-runtime',
                        dest='sniff_runtime',
                        help='trial period in seconds during sniff search',
                        default = 0,
                        type = int,
                        )
    parser.add_argument('--rate', 
                        dest='rate',
                        help='rate per device',
                        default = 0.0,
                        type = float
                        )
    parser.add_argument('--min-rate',
                        dest='min_rate',
                        help='minimum rate per device',
                        default = 0.0,
                        type = float
                        )
    parser.add_argument('--rate-unit',
                        dest='rate_unit',
                        help='rate unit per device',
                        default = "mpps",
                        choices = [ '%', 'mpps' ]
                        )
    parser.add_argument('--packet-protocol',
                        dest='packet_protocol',
                        help='IP protocol to use when constructing packets',
                        default = "UDP",
                        choices = [ 'UDP', 'TCP' ]
                        )
    parser.add_argument('--rate-tolerance',
                        dest='rate_tolerance',
                        help='percentage that TX rate is allowed to vary from requested rate and still be considered valid',
                        default = 5,
                        type = float
                        )
    parser.add_argument('--runtime-tolerance',
                        dest='runtime_tolerance',
                        help='percentage that runtime is allowed to vary from requested runtime and still be considered valid',
                        default = 5,
                        type = float
                        )
    parser.add_argument('--search-granularity',
                        dest='search_granularity',
                        help='the binary search will stop once the percent throughput difference between the most recent passing and failing trial is lower than this',
                        default = 0.1,
                        type = float
                        )
    parser.add_argument('--max-loss-pct', 
                        dest='max_loss_pct',
                        help='maximum percentage of packet loss',
                        default=0.002,
			type = float
                        )
    parser.add_argument('--src-ports',
                        dest='src_ports',
                        help='comma separated list of source ports, 1 per device',
                        default=""
                        )
    parser.add_argument('--dst-ports',
                        dest='dst_ports',
                        help='comma separated list of destination ports, 1 per device',
                        default=""
                        )
    parser.add_argument('--dst-macs', 
                        dest='dst_macs',
                        help='comma separated list of destination MACs, 1 per device',
                        default=""
                        )
    parser.add_argument('--src-macs', 
                        dest='src_macs',
                        help='comma separated list of src MACs, 1 per device',
                        default=""
                        )
    parser.add_argument('--encap-dst-macs', 
                        dest='encap_dst_macs',
                        help='comma separated list of destination MACs for encapulsated network, 1 per device',
                        default=""
                        )
    parser.add_argument('--encap-src-macs', 
                        dest='encap_src_macs',
                        help='comma separated list of src MACs for encapulsated network, 1 per device',
                        default=""
                        )
    parser.add_argument('--dst-ips', 
                        dest='dst_ips',
                        help='comma separated list of destination IPs 1 per device',
                        default=""
                        )
    parser.add_argument('--src-ips', 
                        dest='src_ips',
                        help='comma separated list of src IPs, 1 per device',
                        default=""
                        )
    parser.add_argument('--vxlan-ids', 
                        dest='vxlan_ids',
                        help='comma separated list of VxLAN IDs, 1 per device',
                        default=""
                        )
    parser.add_argument('--vlan-ids', 
                        dest='vlan_ids',
                        help='comma separated list of VLAN IDs, 1 per device',
                        default=""
                        )
    parser.add_argument('--encap-dst-ips', 
                        dest='encap_dst_ips',
                        help='comma separated list of destination IPs for excapsulated network, 1 per device',
                        default=""
                        )
    parser.add_argument('--encap-src-ips', 
                        dest='encap_src_ips',
                        help='comma separated list of src IPs for excapsulated network,, 1 per device',
                        default=""
                        )
    parser.add_argument('--traffic-generator', 
                        dest='traffic_generator',
                        help='name of traffic generator: trex-txrx or moongen-txrx',
                        default="moongen-txrx"
                        )
    parser.add_argument('--measure-latency',
                        dest='measure_latency',
                        help='Collect latency statistics or not',
                        default = 1,
                        type = int
                        )
    parser.add_argument('--latency-rate',
                        dest='latency_rate',
                        help='Rate to send latency packets per second',
                        default = 1000,
                        type = int
                   )
    parser.add_argument('--trial-gap',
                        dest='trial_gap',
                        help='Time to sleep between trial attempts',
                        default = 0,
                        type = int
                        )
    parser.add_argument('--max-retries',
                        dest='max_retries',
                        help='Maximum number of trial retries before aborting',
                        default = 3,
                        type = int
                        )
    parser.add_argument('--stream-mode',
                        dest='stream_mode',
                        help='How the packet streams are constructed',
                        default = "continuous",
                        choices = [ 'continuous', 'segmented' ]
                        )
    parser.add_argument('--use-device-stats',
                        dest='use_device_stats',
                        help='Should device stats be used instead of stream stats',
                        action = 'store_true',
                        )

    t_global.args = parser.parse_args();
    if t_global.args.frame_size == "IMIX":
         t_global.args.frame_size = "imix"
    print(t_global.args)

def get_trex_port_info(trial_params, test_dev_pairs):
     devices = dict()
     device_string = ""

     for dev_pair in test_dev_pairs:
          for direction in [ 'tx', 'tx' ]:
               if not dev_pair[direction] in devices:
                    devices[dev_pair[direction]] = 1
                    device_string = device_string + ' --device ' + str(dev_pair[direction])
               else:
                    devices[dev_pair[direction]] += 1

     cmd = 'python trex-query.py'
     cmd = cmd + ' --mirrored-log'
     cmd = cmd + device_string

     previous_sig_handler = signal.signal(signal.SIGINT, sigint_handler)

     port_info = { 'json': None }

     print('querying TRex...')
     print('cmd:', cmd)
     query_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
     stdout_exit_event = threading.Event()
     stderr_exit_event = threading.Event()

     stdout_thread = threading.Thread(target = handle_query_process_stdout, args = (query_process, stdout_exit_event))
     stderr_thread = threading.Thread(target = handle_query_process_stderr, args = (query_process, trial_params, port_info, stderr_exit_event))

     stdout_thread.start()
     stderr_thread.start()

     stdout_exit_event.wait()
     stderr_exit_event.wait()
     retval = query_process.wait()

     stdout_thread.join()
     stderr_thread.join()

     signal.signal(signal.SIGINT, previous_sig_handler)

     print('return code', retval)
     return port_info['json']

def handle_query_process_stdout(process, exit_event):
     capture_output = True
     do_loop = True
     while do_loop:
          stdout_lines = handle_process_output(process, process.stdout, capture_output)

          for line in stdout_lines:
               if line == "--END--":
                    exit_event.set()
                    do_loop = False
                    continue

def handle_query_process_stderr(process, trial_params, port_info, exit_event):
     output_file = None
     close_file = False
     trial_params['port_info_file'] = "binary-search.port-info.txt"
     filename = "%s/%s" % (trial_params['output_dir'], trial_params['port_info_file'])
     try:
          output_file = open(filename, 'w')
          close_file = True
     except IOError:
          print("ERROR: Could not open %s for writing" % filename)
          output_file = sys.stdout

     capture_output = True
     do_loop = True
     while do_loop:
          stderr_lines = handle_process_output(process, process.stderr, capture_output)

          for line in stderr_lines:
               if line == "--END--":
                    exit_event.set()
                    do_loop = False
                    continue

               m = re.search(r"PARSABLE PORT INFO:\s+(.*)$", line)
               if m:
                    port_info['json'] = json.loads(m.group(1))

               if close_file:
                    print(line.rstrip('\n'))
               print(line.rstrip('\n'), file=output_file)

               if line.rstrip('\n') == "Connection severed":
                    capture_output = False
                    exit_event.set()

     if close_file:
          output_file.close()

def calculate_tx_pps_target(trial_params, streams, tmp_stats):
     rate_target = 0.0

     # packet overhead is (7 byte preamable + 1 byte SFD -- Start of Frame Delimiter -- + 12 byte IFG -- Inter Frame Gap)
     packet_overhead_bytes = 20
     bits_per_byte = 8

     default_packet_avg_bytes = 0.0
     latency_packet_avg_bytes = 0.0

     target_latency_bytes = 0.0
     target_default_bytes = 0.0
     target_default_rate = 0.0
     if trial_params['rate_unit'] == "%":
          total_target_bytes = (tmp_stats['tx_available_bandwidth'] / bits_per_byte) * (trial_params['rate'] / 100)
     else:
          if trial_params['frame_size'] < 64:
               frame_size = 64
          else:
               frame_size = trial_params['frame_size']
          total_target_bytes = (frame_size + packet_overhead_bytes) * trial_params['rate'] * 1000000

     for frame_size, traffic_shares in zip(streams['default']['frame_sizes'], streams['default']['traffic_shares']):
          default_packet_avg_bytes += (frame_size * traffic_shares)

     if trial_params['measure_latency']:
          for frame_size, traffic_shares in zip(streams['latency']['frame_sizes'], streams['latency']['traffic_shares']):
               latency_packet_avg_bytes += (frame_size * traffic_shares)

          target_latency_bytes = (latency_packet_avg_bytes + packet_overhead_bytes) * trial_params['latency_rate']

     target_default_bytes = total_target_bytes - target_latency_bytes

     target_default_rate = target_default_bytes / (default_packet_avg_bytes + packet_overhead_bytes)

     rate_target = target_default_rate
     if trial_params['measure_latency']:
          rate_target += trial_params['latency_rate']

     tmp_stats['packet_overhead_bytes'] = packet_overhead_bytes
     tmp_stats['bits_per_byte'] = bits_per_byte

     return rate_target

def stats_error_append_pg_id(stats, action, pg_id):
     action += "_error"
     if action in stats:
          stats[action] += "," + str(pg_id)
     else:
          stats[action] = str(pg_id)
     return

def run_trial (trial_params, port_info, stream_info, detailed_stats):
    stats = dict()
    stats[0] = dict()
    stats[0]['tx_packets'] = 0
    stats[0]['rx_packets'] = 0
    stats[1] = dict()
    stats[1]['tx_packets'] = 0
    stats[1]['rx_packets'] = 0

    tmp_stats = dict()
    tmp_stats[0] = dict()
    tmp_stats[0]['tx_available_bandwidth'] = 0.0
    tmp_stats[1] = dict()
    tmp_stats[1]['tx_available_bandwidth'] = 0.0

    cmd = ""
    streams = dict()
    streams[0] = 0
    streams[1] = 0

    if trial_params['traffic_generator'] == 'moongen-txrx':
        cmd = './MoonGen/build/MoonGen txrx.lua'
        cmd = cmd + ' --devices=0,1' # fix to allow different devices
        cmd = cmd + ' --measureLatency=0' # fix to allow latency measurment (whern txrx supports)
        cmd = cmd + ' --rate=' + str(trial_params['rate'])
	cmd = cmd + ' --size=' + str(trial_params['frame_size'])
	cmd = cmd + ' --runTime=' + str(trial_params['runtime'])
	cmd = cmd + ' --bidirectional=' + str(trial_params['run_bidirec'])
        if trial_params['vlan_ids'] != '':
            cmd = cmd + ' --vlanIds=' + str(trial_params['vlan_ids'])
        if trial_params['vxlan_ids'] != '':
            cmd = cmd + ' --vxlanIds=' + str(trial_params['vxlan_ids'])
        if trial_params['src_ips'] != '':
            cmd = cmd + ' --srcIps=' + str(trial_params['src_ips'])
        if trial_params['dst_ips'] != '':
            cmd = cmd + ' --dstIps=' + str(trial_params['dst_ips'])
        if trial_params['src_macs'] != '':
            cmd = cmd + ' --srcMacs=' + str(trial_params['src_macs'])
        if trial_params['dst_macs'] != '':
            cmd = cmd + ' --dstMacs=' + str(trial_params['dst_macs'])
        if trial_params['encap_src_ips'] != '':
            cmd = cmd + ' --encapSrcIps=' + str(trial_params['encap_src_ips'])
        if trial_params['encap_dst_ips'] != '':
            cmd = cmd + ' --encapDstIps=' + str(trial_params['encap_dst_ips'])
        if trial_params['encap_src_macs'] != '':
            cmd = cmd + ' --encapSrcMacs=' + str(trial_params['encap_src_macs'])
        if trial_params['encap_dst_macs'] != '':
            cmd = cmd + ' --encapDstMacs=' + str(trial_params['encap_dst_macs'])
        flow_mods_opt = ''
        if trial_params['use_src_ip_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',srcIp'
        if trial_params['use_dst_ip_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',dstIp'
        if trial_params['use_encap_src_ip_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',encapSrcIp'
        if trial_params['use_encap_dst_ip_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',encapDstIp'
        if trial_params['use_src_mac_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',srcMac'
        if trial_params['use_dst_mac_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',dstMac'
        if trial_params['use_encap_src_mac_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',encapSrcMac'
        if trial_params['use_encap_dst_mac_flows'] == 1:
	    flow_mods_opt = flow_mods_opt + ',encapDstMac'
        flow_mods_opt = ' --flowMods="' + re.sub('^,', '', flow_mods_opt) + '"'
        cmd = cmd + flow_mods_opt
    elif trial_params['traffic_generator'] == 'trex-txrx':
        stats[0]['tx_bandwidth'] = 0
        stats[0]['rx_bandwidth'] = 0
        stats[0]['tx_pps_target'] = 0
        stats[1]['tx_bandwidth'] = 0
        stats[1]['rx_bandwidth'] = 0
        stats[1]['tx_pps_target'] = 0

        if not trial_params['run_revunidirec']:
             tmp_stats[0]['tx_available_bandwidth'] = port_info[0]['speed'] * 1000 * 1000 * 1000

        if trial_params['run_bidirec'] or trial_params['run_revunidirec']:
             tmp_stats[1]['tx_available_bandwidth'] = port_info[1]['speed'] * 1000 * 1000 * 1000

        cmd = 'python trex-txrx.py'
        #cmd = cmd + ' --devices=0,1' # fix to allow different devices
        cmd = cmd + ' --mirrored-log'
        cmd = cmd + ' --measure-latency=' + str(trial_params['measure_latency'])
        cmd = cmd + ' --latency-rate=' + str(trial_params['latency_rate'])
        cmd = cmd + ' --rate=' + str(trial_params['rate'])
        cmd = cmd + ' --rate-unit=' + str(trial_params['rate_unit'])
        cmd = cmd + ' --size=' + str(trial_params['frame_size'])
        cmd = cmd + ' --runtime=' + str(trial_params['runtime'])
        cmd = cmd + ' --runtime-tolerance=' + str(trial_params['runtime_tolerance'])
        cmd = cmd + ' --run-bidirec=' + str(trial_params['run_bidirec'])
        cmd = cmd + ' --run-revunidirec=' + str(trial_params['run_revunidirec'])
        cmd = cmd + ' --num-flows=' + str(trial_params['num_flows'])
        if trial_params['src_ports'] != '':
             cmd = cmd + ' --src-ports=' + str(trial_params['src_ports'])
        if trial_params['dst_ports'] != '':
             cmd = cmd + ' --dst-ports=' + str(trial_params['dst_ports'])
        if trial_params['src_ips'] != '':
             cmd = cmd + ' --src-ips=' + str(trial_params['src_ips'])
        if trial_params['dst_ips'] != '':
             cmd = cmd + ' --dst-ips=' + str(trial_params['dst_ips'])
        if trial_params['src_macs'] != '':
             cmd = cmd + ' --src-macs=' + str(trial_params['src_macs'])
        if trial_params['dst_macs'] != '':
             cmd = cmd + ' --dst-macs=' + str(trial_params['dst_macs'])
        if trial_params['vlan_ids'] != '':
             cmd = cmd + ' --vlan-ids=' + str(trial_params['vlan_ids'])
        cmd = cmd + ' --use-src-ip-flows=' + str(trial_params['use_src_ip_flows'])
        cmd = cmd + ' --use-dst-ip-flows=' + str(trial_params['use_dst_ip_flows'])
        cmd = cmd + ' --use-src-mac-flows=' + str(trial_params['use_src_mac_flows'])
        cmd = cmd + ' --use-dst-mac-flows=' + str(trial_params['use_dst_mac_flows'])
        cmd = cmd + ' --use-src-port-flows=' + str(trial_params['use_src_port_flows'])
        cmd = cmd + ' --use-dst-port-flows=' + str(trial_params['use_dst_port_flows'])
        cmd = cmd + ' --use-protocol-flows=' + str(trial_params['use_protocol_flows'])
        cmd = cmd + ' --packet-protocol=' + str(trial_params['packet_protocol'])
        cmd = cmd + ' --stream-mode=' + trial_params['stream_mode']
        if trial_params['use_device_stats']:
             cmd = cmd + ' --skip-hw-flow-stats'

    previous_sig_handler = signal.signal(signal.SIGINT, sigint_handler)

    print('running trial %03d, rate %f' % (trial_params['trial'], trial_params['rate']))
    print('cmd:', cmd)
    tg_process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout_exit_event = threading.Event()
    stderr_exit_event = threading.Event()

    stdout_thread = threading.Thread(target = handle_trial_process_stdout, args = (tg_process, trial_params, stats, stdout_exit_event))
    stderr_thread = threading.Thread(target = handle_trial_process_stderr, args = (tg_process, trial_params, stats, tmp_stats, streams, detailed_stats, stderr_exit_event))

    stdout_thread.start()
    stderr_thread.start()

    stdout_exit_event.wait()
    stderr_exit_event.wait()
    retval = tg_process.wait()

    stdout_thread.join()
    stderr_thread.join()

    signal.signal(signal.SIGINT, previous_sig_handler)

    print('return code', retval)
    stream_info['streams'] = streams
    return stats

def handle_process_output(process, process_stream, capture):
     lines = []
     if process.poll() is None:
          process_stream.flush()
          ready_streams = select.select([process_stream], [], [], 1)
          if process_stream in ready_streams[0]:
               line = process_stream.readline()
               if capture:
                    lines.append(line)
     if process.poll() is not None:
          for line in process_stream:
               if capture:
                    lines.append(line)
          lines.append("--END--")
     return lines

def handle_trial_process_stdout(process, trial_params, stats, exit_event):
    prefix = "%03d" % trial_params['trial']

    capture_output = True
    do_loop = True
    while do_loop:
        stdout_lines = handle_process_output(process, process.stdout, capture_output)

        for line in stdout_lines:
             if line == "--END--":
                  exit_event.set()
                  do_loop = False
                  continue

             print("%s:%s" % (prefix, line.rstrip('\n')))

             if trial_params['traffic_generator'] == 'moongen-txrx':
                  #[INFO]  [0]->[1] txPackets: 10128951 rxPackets: 10128951 packetLoss: 0 txRate: 2.026199 rxRate: 2.026199 packetLossPct: 0.000000
                  #[INFO]  [0]->[1] txPackets: 10130148 rxPackets: 10130148 packetLoss: 0 txRate: 2.026430 rxRate: 2.026430 packetLossPct: 0.000000
                  m = re.search(r"\[INFO\]\s+\[(\d+)\]\-\>\[(\d+)\]\s+txPackets:\s+(\d+)\s+rxPackets:\s+(\d+)\s+packetLoss:\s+(\-*\d+)\s+txRate:\s+(\d+\.\d+)\s+rxRate:\s+(\d+\.\d+)\s+packetLossPct:\s+(\-*\d+\.\d+)", line)
                  if m:
                       print('tx_packets, tx_rate, device', m.group(3), m.group(6), int(m.group(1)))
                       print('rx_packets, rx_rate, device', m.group(4), m.group(7), int(m.group(2)))
                       #stats[0] = {'rx_packets':int(m.group(4)), 'tx_packets':int(m.group(3)), 'tx_rate':float(m.group(6)), 'rx_rate':float(m.group(7))}
                       #stats[1] = {'rx_packets':0, 'tx_packets':0, 'tx_rate':0, 'rx_rate':0}
                       stats[int(m.group(1))]['tx_packets'] = int(m.group(3))
                       stats[int(m.group(1))]['tx_pps'] = float(m.group(3)) / float(trial_params['runtime'])
                       stats[int(m.group(2))]['rx_packets'] = int(m.group(4))
                       stats[int(m.group(2))]['rx_pps'] = float(m.group(4)) / float(trial_params['runtime'])
             elif trial_params['traffic_generator'] == 'trex-txrx':
                  if line.rstrip('\n') == "Connection severed":
                       capture_output = False
                       exit_event.set()

def handle_trial_process_stderr(process, trial_params, stats, tmp_stats, streams, detailed_stats, exit_event):
    output_file = None
    close_file = False
    trial_params['trial_output_file'] = "binary-search.trial-%03d.txt" % (trial_params['trial'])
    filename = "%s/%s" % (trial_params['output_dir'], trial_params['trial_output_file'])
    try:
         output_file = open(filename, 'w')
         close_file = True
    except IOError:
         print("ERROR: Could not open %s for writing" % filename)
         output_file = sys.stdout

    capture_output = True
    do_loop = True
    while do_loop:
        stderr_lines = handle_process_output(process, process.stderr, capture_output)

        for line in stderr_lines:
             if line == "--END--":
                  exit_event.set()
                  do_loop = False
                  continue

             print(line.rstrip('\n'), file=output_file)

             if trial_params['traffic_generator'] == 'moongen-txrx':
                  print(line.rstrip('\n'))
             elif trial_params['traffic_generator'] == 'trex-txrx':
                  #PARSABLE STREAMS FOR DIRECTION 'a': {"default": {"traffic_shares": [0.5833333333333334,0.3333333333333333,0.08333333333333333],"names": ["small_stream_a","medium_stream_a","large_stream_a"],"pg_ids": [128,129,130],"frame_sizes": [40,576,1500]},"latency": {"traffic_shares": [0.5833333333333334,0.3333333333333333,0.08333333333333333],"names": ["small_latency_stream_a","medium_latency_stream_a","large_latency_stream_a"],"pg_ids": [0,1,2],"frame_sizes": [40,576,1500]}}
                  m = re.search(r"PARSABLE STREAMS FOR DIRECTION '([ab])':\s+(.*)$", line)
                  if m:
                       if m.group(1) == "a":
                            streams[0] = json.loads(m.group(2))

                            stats[0]['tx_pps_target'] = calculate_tx_pps_target(trial_params, streams[0], tmp_stats[0])
                       elif m.group(1) == "b":
                            streams[1] = json.loads(m.group(2))

                            stats[1]['tx_pps_target'] = calculate_tx_pps_target(trial_params, streams[1], tmp_stats[1])
                  #PARSABLE RESULT: {"0":{"tx_util":37.68943472,"rx_bps":11472348160.0,"obytes":43064997504,"rx_pps":22406932.0,"ipackets":672312848,"oerrors":0,"rx_util":37.6436432,"opackets":672890586,"tx_pps":22434198.0,"tx_bps":11486302208.0,"ierrors":0,"rx_bps_L1":15057457280.0,"tx_bps_L1":15075773888.0,"ibytes":43028022272},"1":{"tx_util":37.6893712,"rx_bps":11486310400.0,"obytes":43063561984,"rx_pps":22434204.0,"ipackets":672890586,"oerrors":0,"rx_util":37.6894576,"opackets":672868156,"tx_pps":22434148.0,"tx_bps":11486284800.0,"ierrors":0,"rx_bps_L1":15075783040.0,"tx_bps_L1":15075748480.0,"ibytes":43064997504},"latency":{"global":{"bad_hdr":0,"old_flow":0}},"global":{"rx_bps":22958659584.0,"bw_per_core":7.34,"rx_cpu_util":0.0,"rx_pps":44841136.0,"queue_full":0,"cpu_util":62.6,"tx_pps":44868344.0,"tx_bps":22972585984.0,"rx_drop_bps":0.0},"total":{"tx_util":75.37880591999999,"rx_bps":22958658560.0,"obytes":86128559488,"ipackets":1345203434,"rx_pps":44841136.0,"rx_util":75.3331008,"oerrors":0,"opackets":1345758742,"tx_pps":44868346.0,"tx_bps":22972587008.0,"ierrors":0,"rx_bps_L1":30133240320.0,"tx_bps_L1":30151522368.0,"ibytes":86093019776},"flow_stats":{"1":{"rx_bps":{"0":"N/A","1":"N/A","total":"N/A"},"rx_pps":{"0":"N/A","1":20884464.286073223,"total":20884464.286073223},"rx_pkts":{"0":0,"1":672890586,"total":672890586},"rx_bytes":{"total":"N/A"},"tx_bytes":{"0":43064997504,"1":0,"total":43064997504},"tx_pps":{"0":20898314.26218906,"1":"N/A","total":20898314.26218906},"tx_bps":{"0":10699936902.240799,"1":"N/A","total":10699936902.240799},"tx_pkts":{"0":672890586,"1":0,"total":672890586},"rx_bps_L1":{"0":"N/A","1":"N/A","total":"N/A"},"tx_bps_L1":{"0":14043667184.191048,"1":"N/A","total":14043667184.191048}},"2":{"rx_bps":{"0":"N/A","1":"N/A","total":"N/A"},"rx_pps":{"0":20884967.481241994,"1":"N/A","total":20884967.481241994},"rx_pkts":{"0":672312848,"1":0,"total":672312848},"rx_bytes":{"total":"N/A"},"tx_bytes":{"0":0,"1":43063561984,"total":43063561984},"tx_pps":{"0":"N/A","1":20898728.6582104,"total":20898728.6582104},"tx_bps":{"0":"N/A","1":10700149073.003725,"total":10700149073.003725},"tx_pkts":{"0":0,"1":672868156,"total":672868156},"rx_bps_L1":{"0":"N/A","1":"N/A","total":"N/A"},"tx_bps_L1":{"0":"N/A","1":14043945658.317389,"total":14043945658.317389}},"global":{"rx_err":{},"tx_err":{}}}}
                  m = re.search(r"PARSABLE RESULT:\s+(.*)$", line)
                  if m:
                       results = json.loads(m.group(1))
                       detailed_stats['stats'] = copy.deepcopy(results)

                       stats['global'] = dict()

                       stats['global']['runtime'] = results['global']['runtime']
                       stats['global']['timeout'] = results['global']['timeout']

                       if trial_params['use_device_stats']:
                            if not trial_params['run_revunidirec']:
                                 stats[0]['tx_packets'] += int(results['0']['opackets'])
                                 stats[1]['rx_packets'] += int(results['1']['ipackets'])

                                 stats[0]['tx_bandwidth'] += (int(results['0']['opackets']) * tmp_stats[0]['packet_overhead_bytes']) + int(results['0']['obytes'])
                                 stats[1]['rx_bandwidth'] += (int(results['1']['ipackets']) * tmp_stats[0]['packet_overhead_bytes']) + int(results['1']['ibytes'])

                            if trial_params['run_bidirec'] or trial_params['run_revunidirec']:
                                 stats[1]['tx_packets'] += int(results['1']['opackets'])
                                 stats[0]['rx_packets'] += int(results['0']['ipackets'])

                                 stats[1]['tx_bandwidth'] += (int(results['1']['opackets']) * tmp_stats[0]['packet_overhead_bytes']) + int(results['1']['obytes'])
                                 stats[0]['rx_bandwidth'] += (int(results['0']['ipackets']) * tmp_stats[0]['packet_overhead_bytes']) + int(results['0']['ibytes'])
                       else:
                            if not trial_params['run_revunidirec']:
                                 for pg_id, frame_size in zip(streams[0]['default']['pg_ids'], streams[0]['default']['frame_sizes']):
                                      if "0" in results["flow_stats"][str(pg_id)]["rx_pkts"] and int(results["flow_stats"][str(pg_id)]["rx_pkts"]["0"]):
                                           stats_error_append_pg_id(stats[0], "rx_invalid", pg_id)

                                      if "1" in results["flow_stats"][str(pg_id)]["tx_pkts"] and int(results["flow_stats"][str(pg_id)]["tx_pkts"]["1"]):
                                           stats_error_append_pg_id(stats[1], "tx_invalid", pg_id)

                                      if "0" in results["flow_stats"][str(pg_id)]["tx_pkts"]:
                                           stats[0]['tx_packets'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["0"])
                                      else:
                                           stats_error_append_pg_id(stats[0], "tx_missing", pg_id)

                                      if "1" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                           stats[1]['rx_packets'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["1"])
                                      else:
                                           stats_error_append_pg_id(stats[1], "rx_missing", pg_id)

                                      if "0" in results["flow_stats"][str(pg_id)]["tx_pkts"] and "1" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                           stats[0]['tx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["0"]) * (frame_size + tmp_stats[0]['packet_overhead_bytes'])
                                           stats[1]['rx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["1"]) * (frame_size + tmp_stats[0]['packet_overhead_bytes'])

                                      if results["flow_stats"][str(pg_id)]["loss"]["pct"]["0->1"] != "N/A":
                                           if float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["0->1"]) < 0:
                                                stats_error_append_pg_id(stats[1], "rx_negative_loss", pg_id)
                                           elif float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["0->1"]) > trial_params["max_loss_pct"]:
                                                stats_error_append_pg_id(stats[1], "rx_loss", pg_id)

                                 if trial_params['measure_latency']:
                                      for pg_id, frame_size in zip(streams[0]['latency']['pg_ids'], streams[0]['latency']['frame_sizes']):
                                           if "0" in results["flow_stats"][str(pg_id)]["rx_pkts"] and int(results["flow_stats"][str(pg_id)]["rx_pkts"]["0"]):
                                                stats_error_append_pg_id(stats[0], "rx_invalid", pg_id)

                                           if "1" in results["flow_stats"][str(pg_id)]["tx_pkts"] and int(results["flow_stats"][str(pg_id)]["tx_pkts"]["1"]):
                                                stats_error_append_pg_id(stats[1], "tx_invalid", pg_id)

                                           if "0" in results["flow_stats"][str(pg_id)]["tx_pkts"]:
                                                stats[0]['tx_packets'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["0"])
                                           else:
                                                stats_error_append_pg_id(stats[0], "tx_missing", pg_id)

                                           if "1" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                                stats[1]['rx_packets'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["1"])
                                           else:
                                                stats_error_append_pg_id(stats[1], "rx_missing", pg_id)

                                           if "0" in results["flow_stats"][str(pg_id)]["tx_pkts"] and "1" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                                stats[0]['tx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["0"]) * (frame_size + tmp_stats[0]['packet_overhead_bytes'])
                                                stats[1]['rx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["1"]) * (frame_size + tmp_stats[0]['packet_overhead_bytes'])

                                           if results["flow_stats"][str(pg_id)]["loss"]["pct"]["0->1"] != "N/A":
                                                if float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["0->1"]) < 0:
                                                     stats_error_append_pg_id(stats[1], "rx_negative_loss", pg_id)
                                                elif float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["0->1"]) > trial_params["max_loss_pct"]:
                                                     stats_error_append_pg_id(stats[1], "rx_loss", pg_id)

                            if trial_params['run_bidirec'] or trial_params['run_revunidirec']:
                                 for pg_id, frame_size in zip(streams[1]['default']['pg_ids'], streams[1]['default']['frame_sizes']):
                                      if "1" in results["flow_stats"][str(pg_id)]["rx_pkts"] and int(results["flow_stats"][str(pg_id)]["rx_pkts"]["1"]):
                                           stats_error_append_pg_id(stats[1], "rx_invalid", pg_id)

                                      if "0" in results["flow_stats"][str(pg_id)]["tx_pkts"] and int(results["flow_stats"][str(pg_id)]["tx_pkts"]["0"]):
                                           stats_error_append_pg_id(stats[0], "tx_invalid", pg_id)

                                      if "1" in results["flow_stats"][str(pg_id)]["tx_pkts"]:
                                           stats[1]['tx_packets'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["1"])
                                      else:
                                           stats_error_append_pg_id(stats[1], "tx_missing", pg_id)

                                      if "0" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                           stats[0]['rx_packets'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["0"])
                                      else:
                                           stats_error_append_pg_id(stats[0], "rx_missing", pg_id)

                                      if "1" in results["flow_stats"][str(pg_id)]["tx_pkts"] and "0" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                           stats[1]['tx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["1"]) * (frame_size + tmp_stats[1]['packet_overhead_bytes'])
                                           stats[0]['rx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["0"]) * (frame_size + tmp_stats[1]['packet_overhead_bytes'])

                                      if results["flow_stats"][str(pg_id)]["loss"]["pct"]["1->0"] != "N/A":
                                           if float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["1->0"]) < 0:
                                                stats_error_append_pg_id(stats[0], "rx_negative_loss", pg_id)
                                           elif float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["1->0"]) > trial_params["max_loss_pct"]:
                                                stats_error_append_pg_id(stats[0], "rx_loss", pg_id)

                                 if trial_params['measure_latency']:
                                      for pg_id, frame_size in zip(streams[1]['latency']['pg_ids'], streams[1]['latency']['frame_sizes']):
                                           if "1" in results["flow_stats"][str(pg_id)]["rx_pkts"] and int(results["flow_stats"][str(pg_id)]["rx_pkts"]["1"]):
                                                stats_error_append_pg_id(stats[1], "rx_invalid", pg_id)

                                           if "0" in results["flow_stats"][str(pg_id)]["tx_pkts"] and int(results["flow_stats"][str(pg_id)]["tx_pkts"]["0"]):
                                                stats_error_append_pg_id(stats[0], "tx_invalid", pg_id)

                                           if "1" in results["flow_stats"][str(pg_id)]["tx_pkts"]:
                                                stats[1]['tx_packets'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["1"])
                                           else:
                                                stats_error_append_pg_id(stats[1], "tx_missing", pg_id)

                                           if "0" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                                stats[0]['rx_packets'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["0"])
                                           else:
                                                stats_error_append_pg_id(stats[0], "rx_missing", pg_id)

                                           if "1" in results["flow_stats"][str(pg_id)]["tx_pkts"] and "0" in results["flow_stats"][str(pg_id)]["rx_pkts"]:
                                                stats[1]['tx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["tx_pkts"]["1"]) * (frame_size + tmp_stats[1]['packet_overhead_bytes'])
                                                stats[0]['rx_bandwidth'] += int(results["flow_stats"][str(pg_id)]["rx_pkts"]["0"]) * (frame_size + tmp_stats[1]['packet_overhead_bytes'])

                                           if results["flow_stats"][str(pg_id)]["loss"]["pct"]["1->0"] != "N/A":
                                                if float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["1->0"]) < 0:
                                                     stats_error_append_pg_id(stats[0], "rx_negative_loss", pg_id)
                                                elif float(results["flow_stats"][str(pg_id)]["loss"]["pct"]["1->0"]) > trial_params["max_loss_pct"]:
                                                     stats_error_append_pg_id(stats[0], "rx_loss", pg_id)

                       if not trial_params['run_revunidirec']:
                            stats[0]['tx_pps'] = float(stats[0]['tx_packets']) / float(results["global"]["runtime"])
                            stats[1]['rx_pps'] = float(stats[1]['rx_packets']) / float(results["global"]["runtime"])

                            stats[0]['tx_bandwidth'] = float(stats[0]['tx_bandwidth']) / float(results["global"]["runtime"]) * tmp_stats[0]['bits_per_byte']
                            stats[1]['rx_bandwidth'] = float(stats[1]['rx_bandwidth']) / float(results["global"]["runtime"]) * tmp_stats[0]['bits_per_byte']

                            print('tx_packets, tx_rate, tx_bandwidth, device', stats[0]['tx_packets'], stats[0]['tx_pps'], stats[0]['tx_bandwidth'], 0)
                            print('rx_packets, rx_rate, rx_bandwidth, device', stats[1]['rx_packets'], stats[1]['rx_pps'], stats[1]['rx_bandwidth'], 1)

                       if trial_params['run_bidirec'] or trial_params['run_revunidirec']:
                            stats[1]['tx_pps'] = float(stats[1]['tx_packets']) / float(results["global"]["runtime"])
                            stats[0]['rx_pps'] = float(stats[0]['rx_packets']) / float(results["global"]["runtime"])

                            stats[1]['tx_bandwidth'] = float(stats[1]['tx_bandwidth']) / float(results["global"]["runtime"]) * tmp_stats[1]['bits_per_byte']
                            stats[0]['rx_bandwidth'] = float(stats[0]['rx_bandwidth']) / float(results["global"]["runtime"]) * tmp_stats[1]['bits_per_byte']

                            print('tx_packets, tx_rate, tx_bandwidth, device', stats[1]['tx_packets'], stats[1]['tx_pps'], stats[1]['tx_bandwidth'], 1)
                            print('rx_packets, rx_rate, rx_bandwidth, device', stats[0]['rx_packets'], stats[0]['rx_pps'], stats[0]['rx_bandwidth'], 0)

    if close_file:
         output_file.close()

def main():
    process_options()
    final_validation = t_global.args.one_shot == 1
    rate = t_global.args.rate

    trial_results = { 'trials': [] }

    if t_global.args.traffic_generator == 'moongen-txrx' and t_global.args.rate_unit == "%":
         print("The moongen-txrx traffic generator does not support --rate-unit=%")
         quit(1)

    if t_global.args.frame_size == "imix":
         if t_global.args.traffic_generator == 'moongen-txrx':
              print("The moongen-txrx traffic generator does not support --frame-size=imix")
              quit(1)
         if t_global.args.rate_unit == "mpps":
              print("When --frame-size=imix then --rate-unit must be set to %")
              quit(1)
    else:
         t_global.args.frame_size = int(t_global.args.frame_size)

    # the packet rate in millions/sec is based on 10Gbps, update for other Ethernet speeds
    if rate == 0:
        if t_global.args.traffic_generator == "trex-txrx" and t_global.args.rate_unit == "%":
             rate = 100
        else:
             rate = 9999 / ((t_global.args.frame_size) * 8 + 64 + 96.0)
    initial_rate = rate
    prev_rate = 0
    prev_pass_rate = [0]
    prev_fail_rate = rate

    # be verbose, dump all options to binary-search
    print("output_dir", t_global.args.output_dir)
    print("traffic_generator", t_global.args.traffic_generator)
    print("rate", rate)
    print("min_rate", t_global.args.min_rate)
    print("rate_unit", t_global.args.rate_unit)
    print("rate_tolerance", t_global.args.rate_tolerance)
    print("runtime_tolerance", t_global.args.runtime_tolerance)
    print("frame_size", t_global.args.frame_size)
    print("measure_latency", t_global.args.measure_latency)
    print("latency_rate", t_global.args.latency_rate)
    print("max_loss_pct", t_global.args.max_loss_pct)
    print("one_shot", t_global.args.one_shot)
    print("trial_gap", t_global.args.trial_gap)
    print("search-runtime", t_global.args.search_runtime)
    print("validation-runtime", t_global.args.validation_runtime)
    print("sniff-runtime", t_global.args.sniff_runtime)
    print("run-bidirec", t_global.args.run_bidirec)
    print("run-revunidirec", t_global.args.run_revunidirec)
    print("use-num-flows", t_global.args.num_flows)
    print("use-src-mac-flows", t_global.args.use_src_mac_flows)
    print("use-dst-mac-flows", t_global.args.use_dst_mac_flows)
    print("use-src-ip-flows", t_global.args.use_src_ip_flows)
    print("use-dst-ip-flows", t_global.args.use_dst_ip_flows)
    print("use-src-port-flows", t_global.args.use_src_port_flows)
    print("use-dst-port-flows", t_global.args.use_dst_port_flows)
    print("use-protocol-flows", t_global.args.use_protocol_flows)
    print("use-encap-src-mac-flows", t_global.args.use_encap_src_mac_flows)
    print("use-encap-dst-mac-flows", t_global.args.use_encap_dst_mac_flows)
    print("use-encap-src-ip-flows", t_global.args.use_encap_src_ip_flows)
    print("use-encap-dst-ip-flows", t_global.args.use_encap_dst_ip_flows)
    print("src-macs", t_global.args.src_macs)
    print("dest-macs", t_global.args.dst_macs)
    print("encap-src-macs", t_global.args.encap_src_macs)
    print("encap-dest-macs", t_global.args.encap_dst_macs)
    print("src-ips", t_global.args.src_ips)
    print("dest-ips", t_global.args.dst_ips)
    print("encap-src-ips", t_global.args.encap_src_ips)
    print("encap-dest-ips", t_global.args.encap_dst_ips)
    print("src-ports", t_global.args.src_ports)
    print("dst-ports", t_global.args.dst_ports)
    print("packet-protocol", t_global.args.packet_protocol)
    print("stream-mode", t_global.args.stream_mode)
    print("use-device-stats", t_global.args.use_device_stats)
    print("search-granularity", t_global.args.search_granularity)

    trial_params = {} 
    # trial parameters which do not change during binary search
    trial_params['output_dir'] = t_global.args.output_dir
    trial_params['measure_latency'] = t_global.args.measure_latency
    trial_params['latency_rate'] = t_global.args.latency_rate
    trial_params['max_loss_pct'] = t_global.args.max_loss_pct
    trial_params['min_rate'] = t_global.args.min_rate
    trial_params['rate_unit'] = t_global.args.rate_unit
    trial_params['rate_tolerance'] = t_global.args.rate_tolerance
    trial_params['runtime_tolerance'] = t_global.args.runtime_tolerance
    trial_params['frame_size'] = t_global.args.frame_size
    trial_params['run_bidirec'] = t_global.args.run_bidirec
    trial_params['run_revunidirec'] = t_global.args.run_revunidirec
    trial_params['num_flows'] = t_global.args.num_flows
    trial_params['use_src_mac_flows']= t_global.args.use_src_mac_flows
    trial_params['use_dst_mac_flows']= t_global.args.use_dst_mac_flows
    trial_params['use_src_port_flows'] = t_global.args.use_src_port_flows
    trial_params['use_dst_port_flows'] = t_global.args.use_dst_port_flows
    trial_params['use_encap_src_mac_flows'] = t_global.args.use_encap_src_mac_flows
    trial_params['use_encap_dst_mac_flows'] = t_global.args.use_encap_dst_mac_flows
    trial_params['use_src_ip_flows'] = t_global.args.use_src_ip_flows
    trial_params['use_dst_ip_flows'] = t_global.args.use_dst_ip_flows
    trial_params['use_protocol_flows'] = t_global.args.use_protocol_flows
    trial_params['use_encap_src_ip_flows'] = t_global.args.use_encap_src_ip_flows
    trial_params['use_encap_dst_ip_flows'] = t_global.args.use_encap_dst_ip_flows
    trial_params['src_macs'] = t_global.args.src_macs
    trial_params['dst_macs'] = t_global.args.dst_macs
    trial_params['encap_src_macs'] = t_global.args.encap_src_macs
    trial_params['encap_dst_macs'] = t_global.args.encap_dst_macs
    trial_params['src_ips'] = t_global.args.src_ips
    trial_params['dst_ips'] = t_global.args.dst_ips
    trial_params['encap_src_ips'] = t_global.args.encap_src_ips
    trial_params['encap_dst_ips'] = t_global.args.encap_dst_ips
    trial_params['vlan_ids'] = t_global.args.vlan_ids
    trial_params['vxlan_ids'] = t_global.args.vxlan_ids
    trial_params['traffic_generator'] = t_global.args.traffic_generator
    trial_params['max_retries'] = t_global.args.max_retries
    trial_params['search_granularity'] = t_global.args.search_granularity
    trial_params['src_ports'] = t_global.args.src_ports
    trial_params['dst_ports'] = t_global.args.dst_ports
    trial_params['packet_protocol'] = t_global.args.packet_protocol
    trial_params['stream_mode'] = t_global.args.stream_mode
    trial_params['use_device_stats'] = t_global.args.use_device_stats

    if trial_params['run_revunidirec']:
         test_dev_pairs = [ { 'tx': 1, 'rx': 0 } ]
    else:
         test_dev_pairs = [ { 'tx': 0, 'rx': 1 } ]

         if trial_params['run_bidirec']:
              test_dev_pairs.append({ 'tx': 1, 'rx': 0 })

    port_info = None
    if t_global.args.traffic_generator == "trex-txrx":
         port_info = get_trex_port_info(trial_params, test_dev_pairs)
         trial_results['port_info'] = port_info

         for port in port_info:
              if port['driver'] == "net_ixgbe" and not trial_params['use_device_stats']:
                   print("WARNING: Forcing use of device stats instead of stream stats due to issue with Intel 82599/Niantic flow programming")
                   trial_params['use_device_stats'] = True

    perform_sniffs = False
    do_sniff = False
    do_search = True
    if t_global.args.sniff_runtime:
         perform_sniffs = True
         do_sniff = True
         do_search = False

    trial_params['trial'] = 0

    minimum_rate = initial_rate * trial_params['search_granularity'] / 100
    if trial_params['min_rate'] != 0:
         minimum_rate = trial_params['min_rate']

    try:
         retries = 0
         # the actual binary search to find the maximum packet rate
         while final_validation or do_sniff or do_search:
              # support a longer measurement for the last trial, AKA "final validation"
              if final_validation:
                   trial_params['runtime'] = t_global.args.validation_runtime
                   print('\nTrial Mode: Final Validation')
              elif do_search:
                   trial_params['runtime'] = t_global.args.search_runtime
                   print('\nTrial Mode: Search')
              else:
                   trial_params['runtime'] = t_global.args.sniff_runtime
                   print('\nTrial Mode: Sniff')

              trial_params['rate'] = rate
              # run the actual trial
              trial_params['trial'] += 1
              stream_info = { 'streams': None }
              detailed_stats = { 'stats': None }
              stats = run_trial(trial_params, port_info, stream_info, detailed_stats)
              trial_stats = copy.deepcopy(stats)

              trial_result = 'pass'
              test_abort = False
              total_tx_packets = 0
              total_rx_packets = 0
              for dev_pair in test_dev_pairs:
                   pair_abort = False
                   if stats[dev_pair['tx']]['tx_packets'] == 0:
                        pair_abort = True
                        print("binary search failed because no packets were transmitted between device pair: %d -> %d" % (dev_pair['tx'], dev_pair['rx']))

                   if stats[dev_pair['rx']]['rx_packets'] == 0:
                        pair_abort = True
                        print("binary search failed because no packets were received between device pair: %d -> %d" % (dev_pair['tx'], dev_pair['rx']))

                   if 'rx_invalid_error' in stats[dev_pair['tx']]:
                        pair_abort = True
                        print("binary search failed because packets were received on an incorrect port between device pair: %d -> %d (pg_ids: %s)" % (dev_pair['tx'], dev_pair['rx'], stats[dev_pair['tx']]['rx_invalid_error']))

                   if 'tx_invalid_error' in stats[dev_pair['rx']]:
                        pair_abort = True
                        print("binary search failed because packets were transmitted on an incorrect port between device pair: %d -> %d (pg_ids: %s)" % (dev_pair['tx'], dev_pair['rx'], stats[dev_pair['rx']]['tx_invalid_error']))

                   if pair_abort:
                        test_abort = True
                        continue

                   if 'tx_missing_error' in stats[dev_pair['tx']]:
                        trial_result = 'fail'
                        print("(trial failed requirement, missing TX results, device pair: %d -> %d, pg_ids: %s)" % (dev_pair['tx'], dev_pair['rx'], stats[dev_pair['tx']]['tx_missing_error']))

                   if 'rx_missing_error' in stats[dev_pair['rx']]:
                        trial_result = 'fail'
                        print("(trial failed requirement, missing RX results, device pair: %d -> %d, pg_ids: %s)" % (dev_pair['tx'], dev_pair['rx'], stats[dev_pair['rx']]['rx_missing_error']))

                   if 'rx_loss_error' in stats[dev_pair['rx']]:
                        trial_result = 'fail'
                        print("(trial failed requirement, individual stream RX packet loss, device pair: %d -> %d, pg_ids: %s)" % (dev_pair['tx'], dev_pair['rx'], stats[dev_pair['rx']]['rx_loss_error']))

                   if 'rx_negative_loss_error' in stats[dev_pair['rx']]:
                        trial_result = 'fail'
                        print("(trial failed requirement, negative individual stream RX packet loss, device pair: %d -> %d, pg_ids: %s)" % (dev_pair['tx'], dev_pair['rx'], stats[dev_pair['rx']]['rx_negative_loss_error']))

                   lost_packets = stats[dev_pair['tx']]['tx_packets'] - stats[dev_pair['rx']]['rx_packets']
                   trial_stats[dev_pair['rx']]['rx_lost_packets'] = lost_packets
                   pct_lost_packets = 100.0 * lost_packets / stats[dev_pair['tx']]['tx_packets']
                   trial_stats[dev_pair['rx']]['rx_lost_packets_pct'] = pct_lost_packets
                   requirement_msg = "passed"
                   if pct_lost_packets > t_global.args.max_loss_pct:
                        requirement_msg = "failed"
                        trial_result = 'fail'
                   print("(trial %s requirement, percent loss, device pair: %d -> %d, requested: %f%%, achieved: %f%%, lost packets: %d)" % (requirement_msg, dev_pair['tx'], dev_pair['rx'], t_global.args.max_loss_pct, pct_lost_packets, lost_packets))

                   requirement_msg = "passed"
                   tx_rate = stats[dev_pair['tx']]['tx_pps'] / 1000000.0
                   tolerance_min = 0.0
                   tolerance_max = 0.0
                   if t_global.args.traffic_generator == 'trex-txrx':
                        tolerance_min = (stats[dev_pair['tx']]['tx_pps_target'] / 1000000) * ((100.0 - trial_params['rate_tolerance']) / 100)
                        tolerance_max = (stats[dev_pair['tx']]['tx_pps_target'] / 1000000) * ((100.0 + trial_params['rate_tolerance']) / 100)
                        if tx_rate > tolerance_max or tx_rate < tolerance_min:
                             requirement_msg = "retry"
                             if trial_result == "pass":
                                  trial_result = "retry-to-quit"
                        tolerance_min *= 1000000
                        tolerance_max *= 1000000
                   elif t_global.args.traffic_generator == 'moongen-txrx':
                        tolerance_min = trial_params['rate'] * (100 - trial_params['rate_tolerance']) / 100
                        tolerance_max = trial_params['rate'] * (100 + trial_params['rate_tolerance']) / 100
                        if tx_rate > tolerance_max or tx_rate < tolerance_min:
                             requirement_msg = "retry"
                             if trial_result == "pass":
                                  trial_result = "retry-to-quit"
                   trial_stats[dev_pair['tx']]['tx_tolerance_min'] = tolerance_min
                   trial_stats[dev_pair['tx']]['tx_tolerance_max'] = tolerance_max
                   print("(trial %s requirement, TX rate tolerance, device pair: %d -> %d, unit: mpps, tolerance: %f - %f, achieved: %f)" % (requirement_msg, dev_pair['tx'], dev_pair['rx'], (tolerance_min/1000000), (tolerance_max/1000000), tx_rate))

              if test_abort:
                   print('Binary search aborting due to critical error')
                   quit(1)

              if 'global' in stats:
                   tolerance_min = float(trial_params['runtime']) * (1 - (float(trial_params['runtime_tolerance']) / 100))
                   tolerance_max = float(trial_params['runtime']) * (1 + (float(trial_params['runtime_tolerance']) / 100))
                   trial_stats['global']['runtime_tolerance_min'] = tolerance_min
                   trial_stats['global']['runtime_tolerance_max'] = tolerance_max

                   if stats['global']['timeout']:
                        print("(trial timeout, forcing a retry, timeouts can cause inconclusive trial results)")
                        trial_result = "retry-to-fail"
                   else:
                        if stats['global']['runtime'] < tolerance_min or stats['global']['runtime'] > tolerance_max:
                             print("(trial failed requirement, runtime tolerance test, forcing retry, tolerance: %f - %f, achieved: %f)" % (tolerance_min, tolerance_max, stats['global']['runtime']))
                             if trial_result == "pass":
                                  trial_result = "retry-to-fail"

              trial_results['trials'].append({ 'trial': trial_params['trial'], 'rate': trial_params['rate'], 'rate_unit': trial_params['rate_unit'], 'result': trial_result, 'logfile': trial_params['trial_output_file'], 'stats': trial_stats, 'trial_params': copy.deepcopy(trial_params), 'stream_info': copy.deepcopy(stream_info['streams']), 'detailed_stats': copy.deepcopy(detailed_stats['stats']) })

              if trial_result == "pass":
                   print('(trial passed all requirements)')
              elif trial_result == "retry-to-fail" or trial_result == "retry-to-quit":
                   print('(trial must be repeated because one or more requirements did not pass, but allow a retry)')

                   if retries >= trial_params['max_retries']:
                        if trial_result == "retry-to-quit":
                             print('---> The retry limit for a trial has been reached.  This is probably due to a rate tolerance failure.  <---')
                             print('---> You must adjust the --rate-tolerance to a higher value, or use --rate to start with a lower rate. <---')
                             quit(1)
                        elif trial_result == "retry-to-fail":
                             print('---> The retry limit has been reached.  Failing and continuing. <---')
                             retries = 0
                             trial_result = "fail"
                   else:
                        # if trial_result is retry, then don't adjust anything and repeat
                        retries = retries + 1
              else:
                   print('(trial failed one or more requirements)')

              if t_global.args.one_shot == 1:
                   break
              if trial_result == "fail":
                   if final_validation:
                        final_validation = False
                        next_rate = rate - (trial_params['search_granularity'] * rate / 100) # subtracting by at least search_granularity percent avoids very small reductions in rate
                   else:
                        if len(prev_pass_rate) > 1 and rate < prev_pass_rate[len(prev_pass_rate)-1]:
                             # if the attempted rate drops below the most recent passing rate then that
                             # passing rate is considered a false positive and should be removed; ensure
                             # that at least the original passing rate (which is a special rate of 0) is never
                             # removed from the stack
                             print("Removing false positive passing result: %f" % (prev_pass_rate.pop()))
                        next_rate = (prev_pass_rate[len(prev_pass_rate)-1] + rate) / 2 # use the most recently added passing rate present in stack to calculate the next rate
                        if abs(rate - next_rate) < (trial_params['search_granularity'] * rate / 100):
                             next_rate = rate - (trial_params['search_granularity'] * rate / 100) # subtracting by at least search_granularity percent avoids very small reductions in rate
                   if perform_sniffs:
                        do_sniff = True
                        do_search = False
                   else:
                        do_search = True
                        do_sniff = False
                   prev_fail_rate = rate
                   prev_rate = rate
                   rate = next_rate
                   retries = 0
              elif trial_result == "pass":
                   passed_stats = stats
                   if final_validation: # no longer necessary to continue searching
                        break
                   if do_sniff:
                        do_sniff = False
                        do_search = True
                        next_rate = rate # since this was only the sniff test, keep the current rate
                   else:
                        prev_pass_rate.append(rate) # add the newly passed rate to the stack of passed rates; this will become the new reference for passed rates
                        next_rate = (prev_fail_rate + rate) / 2
                        if abs(rate - next_rate)/rate * 100 < trial_params['search_granularity']: # trigger final validation
                             final_validation = True
                             do_search = False
                        else:
                             if perform_sniffs:
                                  do_sniff = True
                                  do_search = False
                   prev_rate = rate
                   rate = next_rate
                   retries = 0

              if rate < minimum_rate and prev_rate > minimum_rate:
                   print("Setting the rate to the minimum allowed by the search granularity as a last attempt at passing.")
                   prev_rate = rate
                   rate = minimum_rate
              elif (rate == minimum_rate or prev_rate <= minimum_rate) and trial_result == 'fail':
                   print("Binary search ended up at rate which is below minimum allowed")
                   quit(1)

              if t_global.args.trial_gap:
                   print("Sleeping for %d seconds between trial attempts" % t_global.args.trial_gap)
                   time.sleep(t_global.args.trial_gap)

         print("RESULT:")
         if prev_pass_rate[len(prev_pass_rate)-1] != 0: # show the stats for the most recent passing trial
              print('[')
              print(json.dumps(passed_stats[0], indent = 4, separators=(',', ': '), sort_keys = True))
              print(',')
              print(json.dumps(passed_stats[1], indent = 4, separators=(',', ': '), sort_keys = True))
              print(']')
         else:
              if t_global.args.one_shot == 1:
                   print('[')
                   print(json.dumps(stats[0], indent = 4, separators=(',', ': '), sort_keys = True))
                   print(',')
                   print(json.dumps(stats[1], indent = 4, separators=(',', ': '), sort_keys = True))
                   print(']')
              else:
                   print("There is no trial which passed")

    finally:
         trial_json_filename = "%s/binary-search.json" % (trial_params['output_dir'])
         try:
              trial_json_file = open(trial_json_filename, 'w')
              print(json.dumps(trial_results, indent = 4, separators=(',', ': '), sort_keys = True), file=trial_json_file)
              trial_json_file.close()
         except IOError:
              print("ERROR: Could not open %s for writing" % trial_json_filename)
              print("TRIALS:")
              print(json.dumps(trial_results, indent = 4, separators=(',', ': '), sort_keys = True))

if __name__ == "__main__":
    exit(main())

