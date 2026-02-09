#!/usr/bin/env python3

"""
dns_server.py

DNS server component for rouge access point
"""

import os
import sys
import signal
import threading
import configparser
import logging
from dnslib import DNSRecord, QTYPE, RR, A, ZoneParser
from dnslib.server import DNSServer, DNSHandler, BaseResolver
        
class RougeDNSServer(BaseResolver):
    def __init__(self, dns_zone_records, dns_override_records, primary_upstream, backup_upstream, logger=None):
        """ Initialize the object
        """
        self.dns_zone_records = dns_zone_records
        self.dns_override_records = dns_override_records
        self.primary_upstream = primary_upstream
        self.backup_upstream = backup_upstream
        self.logger = logger
        self.query = 0
        
    def resolve(self, request, handler):
        """ Resolves DNS queries received by the server and returns a response
        """

        def normalize(name):
            """ Domain name normalization
            """
            return name.lower().rstrip(".") + "."

        def wildcard_match(qname, rname):
            """ Wildcard record matching
            """
            if not rname.startswith("*."):
                return False
            suffix = rname[2:]
            if not qname.endswith(suffix):
                return False
            qlabels = qname.rstrip(".").split(".")
            slabels = suffix.rstrip(".").split(".")
            if len(qlabels) == len(slabels) + 1:
                return True
            else:
                return False

        # Get query name and type, along with client IP, then initialize an empty reply we will send back
        # once the appropriate response is determined
        qname = normalize(str(request.q.qname).rstrip("."))
        qtype = QTYPE[request.q.qtype]
        client_ip = handler.client_address[0]
        reply = request.reply()
        self.logger.info(f"[DNS Query (No. {self.query})] Got DNS query from {client_ip} of type {qtype} for {qname}!")


        ################################################
        # ATTEMPT RESOLUTION FROM DNS OVERRIDE RECORDS #
        ################################################
        if self.dns_override_records:
            exact_matches = []
            wildcard_matches = []
            for rr in self.dns_override_records:
                if qtype not in (QTYPE[rr.rtype], "ANY"):
                    continue
                if qname == normalize(str(rr.rname)):
                    exact_matches.append(rr)
                elif wildcard_match(qname, normalize(str(rr.rname))):
                    wildcard_matches.append(rr)
            matches = exact_matches or wildcard_matches
            if matches:
                for rr in matches:
                    reply.add_answer(rr)
                self.logger.info(f"[DNS Query (No. {self.query})] Override record exists for this domain and query type, resolving from override records")
                self.query = self.query + 1
                return reply

        #########################################
        # ATTEMPT RESOLUTION FROM DNS ZONE FILE #
        #########################################
        if self.dns_zone_records:
            for rr in self.dns_zone_records:
                if qtype in (QTYPE[rr.rtype], "ANY") and qname == normalize(str(rr.rname)):
                    reply.add_answer(rr)
                    reply.header.aa = 1
                    self.logger.info(f"[DNS Query (No. {self.query})] Queried domain present in zones file, resolved locally")
                    self.query = self.query + 1
                    return reply

        ##############################################################
        # NO LOCAL RECORDS EXIST, RESOLVE THROUGH UPSTREAM RESOLVERS #
        ##############################################################
        for upstream in (self.primary_upstream, self.backup_upstream):
            try:
                upstream_response = request.send(upstream, 53, tcp=False)
                self.logger.info(f"[DNS Query (No. {self.query})] Queried domain not present in zones file, forwarding to upstream DNS server at {upstream}")
                self.query = self.query + 1
                return DNSRecord.parse(upstream_response)
            except Exception:
                self.logger.warning(f"[DNS Query (No. {self.query})] Failed to get response from upstream DNS server at {upstream}")
                continue
        self.query = self.query + 1
            
# Begin execution
if __name__ == "__main__":
    # Read the config file
    config = configparser.ConfigParser()
    config.read(sys.argv[1])

    # Set up the logger
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger()
    logger.info(f"[DNS Server] Initializing DNS server component...")

    # Load the DNS zones file
    zone_file_path = config["DNS"]["zone_file"]
    if "~" in zone_file_path:
        zone_file_path = os.path.expanduser(zone_file_path)
    logger.info(f"[DNS Server] ...Reading DNS zones file located at '{zone_file_path}'...")
    with open(zone_file_path, "r") as zone_file:
        zone_parser = ZoneParser(zone_file)
        dns_zone_records = list(zone_parser.parse())

    # Load the DNS overrides file
    override_file_path = config["DNS"]["override_file"]
    if "~" in override_file_path:
        override_file_path = os.path.expanduser(override_file_path)
    logger.info(f"[DNS Server] ...Reading DNS overrides file located at '{override_file_path}'...")
    with open(override_file_path, "r") as override_file:
        override_parser = ZoneParser(override_file)
        dns_override_records = list(override_parser.parse())

    # Start the DNS server
    logger.info(f"[DNS Server] ...Bringing up the server...")
    resolver = RougeDNSServer(dns_zone_records, dns_override_records, config["DNS"]["primary_upstream"], config["DNS"]["backup_upstream"], logger=logger)
    server = DNSServer(resolver, port=int(config["DNS"]["lport"]), address=config["DNS"]["laddr"])
    server.start_thread()
    logger.info(f"[DNS Server] ...Done! Server is up and listening on {config['DNS']['laddr']}:{config['DNS']['lport']}!")

    # Run until CTRL-C recieved
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.info(f"[DNS Server] Keyboard interupt recieved, stopping DNS server now.")
