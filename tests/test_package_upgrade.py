# vim: tabstop=4 shiftwidth=4 softtabstop=4

import json
import os
import requests
import time
import unittest2

from opencenterclient.client import OpenCenterEndpoint


class AdventureTest(unittest2.TestCase):
    """
    Test the update agent adventure
    """
    def setUpClass(self):
        self.endpoint_url = os.environ.get('OPENCENTER_ENDPOINT','http://127.0.0.0:8080')
        self.user = os.environ.get('OPENCENTER_USER',"admin")
        self.password = os.environ.get('OPENCENTER_PASSWORD',None)

        print "ENDPOINT_URL: %s" % self.endpoint_url

        self.ep = OpenCenterEndpoint(self.endpoint_url, user=self.user, password=self.password)
        self.admin_ep = OpenCenterEndpoint(self.endpoint_url + '/admin', user=self.user, password=self.password)
        self.workspace = self.ep.nodes.filter('name = "workspace"').first()
        
        

    def updateAdventure(self):
        update_agent_adventure = self.ep.adventures.filter('name = "Update Agent"').first()
        for node in self.ep.nodes:
            if 'agent' in node.facts['backends']:
                resp = self.ep.adventures[update_agent_adventure.id].execute(node=node.id)
                self.assertEquals(resp.status_code, 202)
                task = resp.task
                task.wait_for_complete()
