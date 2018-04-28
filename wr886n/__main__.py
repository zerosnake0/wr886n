# -*- coding: utf8 -*-
from __future__ import print_function
import os
import base64
from collections import defaultdict, namedtuple
from itertools import count

import requests
import re
import json
try:
    from urllib.parse import quote
    # from urllib.parse import urlencode
except ImportError:
    from urllib import quote

TPLINK_HOST = os.environ['TPLINK_HOST']
TPLINK_PASSWORD = os.environ['TPLINK_PASSWORD']

Server = namedtuple('Server', ['sid', 'page',
                               'start_port', 'end_port', 'internal_port',
                               'ip_addr', 'protocol', 'status'])


class TPLink(object):
    def __init__(self):
        self.session = requests.Session()
        self.host = TPLINK_HOST
        self.password = TPLINK_PASSWORD
        self.server_url = 'http://{}/userRpm/VirtualServerRpm.htm'.format(self.host)
        self.menu_url = 'http://{}/userRpm/MenuRpm.htm'.format(self.host)

    def login(self):
        auth = "admin:" + self.password
        auth = "Basic " + base64.b64encode(auth.encode()).decode()
        self.session.cookies.update({
            'Authorization': quote(auth),
            'path': '/'
        })
        r = self.session.get("http://{}".format(self.host))
        return r.status_code == 200

    @staticmethod
    def get_array(array_name, src):
        pattern = r"var +{} *= *new +Array *\((.*?)\)".format(array_name)
        m = re.search(pattern, src, re.S)
        if m is None:
            return None
        return json.loads('[{}]'.format(m.group(1)))

    def get_virtual_server(self):
        self.session.headers.update({
            'Referer': self.menu_url
        })

        servers = defaultdict(list)
        for cur_page in count(1):  # page number start from 1
            print("Page:", cur_page)
            r = self.session.get(self.server_url, params=dict(Page=cur_page))
            if r.status_code != 200:
                print("Unable to open %s", self.server_url)
                return None

            vir_server_list_para = self.get_array('virServerListPara', r.text)
            if vir_server_list_para is None:
                print("Unable to find virServerListPara")
                return None

            vir_server_para = self.get_array('virServerPara', r.text)
            if vir_server_para is None:
                print("Unable to find virServerPara")
                return None

            protocol_list = self.get_array('protocolList', r.text)
            if protocol_list is None:
                print("Unable to find protocolList")
                return None

            page_size = vir_server_para[4]

            n_servers = vir_server_para[2]
            print(n_servers, "servers")
            id_base = page_size * (cur_page - 1)
            for i in range(n_servers):
                sid = id_base + i
                row = i * vir_server_para[3]
                ip_addr = vir_server_list_para[row + 3]
                s = Server(sid, cur_page, *vir_server_list_para[row:row + 6])
                servers[ip_addr].append(s)

            # cur_page = virServerPara[0]
            # nextPage = virServerPara[1] > 0
            if vir_server_para[1] <= 0:
                break

        return servers

    def add_or_modify_server(self, ip_addr, start_port, end_port,
                             internal_port='', protocol=1, status=1,
                             changed=0, page=0, sel_index=0):
        """ Add a virtual server

        :param ip_addr: ip address
        :param start_port: start internal port
        :param end_port: end internal port
        :param internal_port: '' if use the same range
        :param protocol: 1. ALL, 2. TCP, 3. UDP
        :param status: 0. disable, 1. enable

        The following should be used when modify

        :param changed: 0 for new server, 1 for a existing server
        :param page: the page of the server
        :param sel_index: 0 for new server, otherwise the server idx on the page

        :return:
        """
        r = self.session.get(self.server_url, params={
            'ExPort': start_port if start_port == end_port else '{}-{}'.format(start_port, end_port),
            'InPort': internal_port,
            'Ip': ip_addr,
            'Protocol': protocol,
            'State': status,
            'Commonport': 0,
            'Changed': changed,
            'Page': page,
            'SelIndex': sel_index,
            'curpage': 1,
            'Save': quote("保 存")
        })
        return r.status_code == 200

    def delete_server(self, index, page):
        r = self.session.get(self.server_url, params={'Del': index, 'Page': page})
        return r.status_code == 200

    @staticmethod
    def show_servers(servers):
        for ip, l in servers.items():
            for v in sorted(l, key=lambda x: (x.start_port, x.end_port)):
                print(ip, v)

    def run(self):
        print("Logging...")
        if not self.login():
            print("Unable to login")
            return

        print("Getting servers...")
        servers = self.get_virtual_server()
        self.show_servers(servers)

        test_ip = '192.168.0.254'
        print("Adding servers...")
        for i in range(1, 10):
            print("Adding", i)
            self.add_or_modify_server(test_ip, i, i)

        print("Refreshing servers...")
        servers = self.get_virtual_server()

        print("Deleting servers...")
        for s in sorted(servers[test_ip], key=lambda x: x.sid, reverse=True):
            print('Deleting', s)
            self.delete_server(s.sid, s.page)

        print("Refreshing servers...")
        servers = self.get_virtual_server()
        self.show_servers(servers)


def main():
    t = TPLink()
    t.run()

    
if __name__ == "__main__":
    main()
