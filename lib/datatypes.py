"""
lib/datatypes.py

Custom datatype definitions
"""

import os
import sys
import subprocess
import configparser
from dnslib import DNSRecord, QTYPE, RR, A, ZoneParser
from dnslib.server import DNSServer as dnslib_DNSServer
from dnslib.server import DNSHandler, BaseResolver
from . import exceptions

class DNSResolver(BaseResolver):
    """ DNS query resolver
    """

    def __init__(self, config=None, logger=None):
        """ Initialize the object
        """
        self.config = config
        self.logger = logger
        self.primary_upstream = self.config["DNS"]["primary_upstream"]
        self.backup_upstream = self.config["DNS"]["backup_upstream"]
        zone_file_path = self.config["DNS"]["zone_file"]
        with open(zone_file_path, "r") as zone_file:
            zone_parser = ZoneParser(zone_file)
            self.dns_zone_records = list(zone_parser.parse())
        override_file_path = self.config["DNS"]["override_file"]
        with open(override_file_path, "r") as override_file:
            override_parser = ZoneParser(override_file)
            self.dns_override_records = list(override_parser.parse())
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

        # Attempt resolution through override records
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
                self.query = self.query + 1
                return reply

        # Attempt resolution through zone records
        if self.dns_zone_records:
            for rr in self.dns_zone_records:
                if qtype in (QTYPE[rr.rtype], "ANY") and qname == normalize(str(rr.rname)):
                    reply.add_answer(rr)
                    reply.header.aa = 1
                    self.query = self.query + 1
                    return reply

        # Resolve through upstream resolvers
        for upstream in (self.primary_upstream, self.backup_upstream):
            try:
                upstream_response = request.send(upstream, 53, tcp=False)
                self.query = self.query + 1
                return DNSRecord.parse(upstream_response)
            except Exception:
                continue
        self.query = self.query + 1

class DNSServer(object):
    """ DNS server
    """

    def __init__(self, config=None, logger=None):
        """ Initialize the object
        """
        self.config = config
        self.logger = logger
        self.state = "not running"
        self.dns_server = None

    def _start_dns_server(self):
        """ DNS server startup sequence
        """
        resolver = DNSResolver(config=self.config, logger=self.logger)
        self.dns_server = dnslib_DNSServer(resolver, port=int(self.config["DNS"]["lport"]), address=self.config["DNS"]["laddr"])
        self.dns_server.start_thread()
        self.state = "running"
        return None

    def _stop_dns_server(self):
        """ DNS server shutdown sequence
        """
        self.dns_server.stop()
        self.state = "not running"
        return None

    def _restart_dns_server(self):
        """ DNS server restart sequence
        """
        self._stop_dns_server()
        self._start_dns_server()
        return None

    def start(self):
        """ Start the DNS server
        """
        if self.state == "running":
            raise exceptions.StateChangeError(f"DNS server is already started!")
        try:
            self._start_dns_server()
        except Exception as err_msg:
            raise exceptions.StateChangeError(f"Encountered an exception when trying to start DNS server! Error message: {err_msg}")
        return None

    def stop(self):
        """ Stop the DNS server
        """
        if self.state == "not running":
            raise exceptions.StateChangeError(f"DNS server is already stopped!")
        try:
            self._stop_dns_server()
        except Exception as err_msg:
            raise exceptions.StateChangeError(f"Encountered an exception when trying to stop DNS server! Error message: {err_msg}")
        return None

    def restart(self):
        """ Restart the DNS server
        """
        if self.state == "not running":
            raise exceptions.StateChangeError(f"DNS server has not been started!")
        try:
            self._restart_dns_server()
        except Exception as err_msg:
            raise exceptions.StateChangeError(f"Encountered an exception when trying to restart DNS server! Error message: {err_msg}")
        return None

    def configure(self, setting, value):
        """ Configure the DNS server
        """
        if setting in (
            "zone_file",
            "override_file",
            "primary_upstream",
            "backup_upstream",
            "laddr",
            "lport",
            "ttl"
        ):
            self.config["DNS"][setting] = value
        else:
            raise exceptions.ConfigurationError(f"Invalid setting '{setting}'!")
        return None
