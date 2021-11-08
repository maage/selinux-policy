#!/usr/bin/python

# Author: Chris PeBenito <cpebenito@tresys.com>
#
# Copyright (C) 2006 Tresys Technology, LLC
#      This program is free software; you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, version 2.

from dataclasses import (
    dataclass,
    field,
)
import getopt
import re
import sys
from typing import (
    Sequence,
)

re_network_port = r'^network_port'
re_netport_parameters = r'\s*,\s*(\w+)\s*,\s*([\w-]+)\s*,\s*(\w+)'
re_netport = (
    re_network_port
    + r'\(\s*(?P<name>\w+)\s*(?P<parameters>(?:'
    + re_netport_parameters
    + r')+)?\s*\)\s*(?:#|$)'
)
NETWORK_PORT = re.compile(re_network_port)
NETPORT_PARAMETERS = re.compile(re_netport_parameters)
NETPORT = re.compile(re_netport)

DEFAULT_INPUT_PACKET = "server_packet_t"
DEFAULT_OUTPUT_PACKET = "client_packet_t"
DEFAULT_MCS = "s0"
DEFAULT_MLS = "s0"

PACKET_INPUT = "_server_packet_t"
PACKET_OUTPUT = "_client_packet_t"


@dataclass(frozen=True)
class Port:
    proto: str
    num: str
    mls_sens: str
    mcs_cats: str = ''


@dataclass(frozen=True)
class Packet:
    prefix: str
    ports: Sequence[Port] = field(default_factory=list)


def print_input_rules(packets, mls, mcs):
    line = (
        "base -A selinux_new_input -j SECMARK --selctx system_u:object_r:"
        + DEFAULT_INPUT_PACKET
    )
    if mls:
        line += ":" + DEFAULT_MLS
    elif mcs:
        line += ":" + DEFAULT_MCS

    print(line)

    for i in packets:
        for j in i.ports:
            line = f"base -A selinux_new_input -p {j.proto} --dport {j.num} -j SECMARK --selctx system_u:object_r:{i.prefix}{PACKET_INPUT}"
            if mls:
                line += ":" + j.mls_sens
            elif mcs:
                line += ":" + j.mcs_cats
            print(line)

    print("post -A selinux_new_input -j CONNSECMARK --save")
    print("post -A selinux_new_input -j RETURN")


def print_output_rules(packets, mls, mcs):
    line = (
        "base -A selinux_new_output -j SECMARK --selctx system_u:object_r:"
        + DEFAULT_OUTPUT_PACKET
    )
    if mls:
        line += ":" + DEFAULT_MLS
    elif mcs:
        line += ":" + DEFAULT_MCS
    print(line)

    for i in packets:
        for j in i.ports:
            line = f"base -A selinux_new_output -p {j.proto} --dport {j.num} -j SECMARK --selctx system_u:object_r:{i.prefix}{PACKET_OUTPUT}"
            if mls:
                line += ":" + j.mls_sens
            elif mcs:
                line += ":" + j.mcs_cats
            print(line)

    print("post -A selinux_new_output -j CONNSECMARK --save")
    print("post -A selinux_new_output -j RETURN")


def parse_corenet(file_name):
    packets = []

    with open(file_name, "r") as corenet_te_in:

        for lineno, corenet_line in enumerate(corenet_te_in, start=1):
            corenet_line = corenet_line.strip()
            if not corenet_line:
                continue

            if NETWORK_PORT.match(corenet_line) is None:
                continue

            match = NETPORT.match(corenet_line)
            if match is None:
                sys.stderr.write(
                    f"{file_name}:{lineno}: Parse error: '{corenet_line}'\n"
                )
                sys.exit(1)

            if match.lastgroup == 'name':
                # No parameters, so not possible to add port here
                continue

            parms = re.findall(NETPORT_PARAMETERS, match.group('parameters'))
            ports = []
            for p in parms:
                proto, num, mls_sens = p[0:3]
                # Ports can be either single or range, fix range char
                num = num.replace("-", ":")
                ports.append(Port(proto, num, mls_sens))

            packets.append(Packet(match.group('name'), ports))

    return packets


def print_netfilter_config(packets, mls, mcs):
    print("pre *mangle")
    print("pre :PREROUTING ACCEPT [0:0]")
    print("pre :INPUT ACCEPT [0:0]")
    print("pre :FORWARD ACCEPT [0:0]")
    print("pre :OUTPUT ACCEPT [0:0]")
    print("pre :POSTROUTING ACCEPT [0:0]")
    print("pre :selinux_input - [0:0]")
    print("pre :selinux_output - [0:0]")
    print("pre :selinux_new_input - [0:0]")
    print("pre :selinux_new_output - [0:0]")
    print("pre -A INPUT -j selinux_input")
    print("pre -A OUTPUT -j selinux_output")
    print("pre -A selinux_input -m state --state NEW -j selinux_new_input")
    print(
        "pre -A selinux_input -m state --state RELATED,ESTABLISHED -j CONNSECMARK --restore"
    )
    print("pre -A selinux_output -m state --state NEW -j selinux_new_output")
    print(
        "pre -A selinux_output -m state --state RELATED,ESTABLISHED -j CONNSECMARK --restore"
    )
    print_input_rules(packets, mls, mcs)
    print_output_rules(packets, mls, mcs)
    print("post COMMIT")


def main():
    mls = False
    mcs = False

    try:
        opts, paths = getopt.getopt(sys.argv[1:], 'mc', ['mls', 'mcs'])
    except getopt.GetoptError:
        print("Invalid options.")
        sys.exit(1)

    for o, _ in opts:
        if o in ("-c", "--mcs"):
            mcs = True
        if o in ("-m", "--mls"):
            mls = True

    if len(paths) == 0:
        sys.stderr.write("Need a path for corenetwork.te.in!\n")
        sys.exit(1)
    elif len(paths) > 1:
        sys.stderr.write("Ignoring extra specified paths\n")

    packets = parse_corenet(paths[0])
    print_netfilter_config(packets, mls, mcs)


if __name__ == '__main__':
    main()
