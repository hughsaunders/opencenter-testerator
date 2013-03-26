# vim: tabstop=4 shiftwidth=4 softtabstop=4

import json
import os
import requests
import time
import unittest2

from opencenter.config import OpenCenterConfiguration
from opencenterclient.client import OpenCenterEndpoint

class AdventureTest(unittest2.TestCase):
    """
    Test the update agent adventure
    """
    def setUp(self):
                config = OpenCenterConfiguration()
        opencenter_config = config.opencenter_config
        cluster_data =  config.cluster_data
        
        self.endpoint_url = opencenter_config.endpoint_url
        self.user = opencenter_config.user
        self.password = opencenter_config.password

        if self.user:
            self.ep = OpenCenterEndpoint(self.endpoint_url, user=self.user, password=self.password)
        else:
            self.ep = OpenCenterEndpoint(self.endpoint_url)

        self.ep = OpenCenterEndpoint(self.endpoint_url, user=self.user, password=self.password)
        self.admin_ep = OpenCenterEndpoint(self.endpoint_url + '/admin', user=self.user, password=self.password)
        self.workspace = self.ep.nodes.filter('name = "workspace"').first()
        

    def test_update_adventure(self):
        update_agent_adventure = self.ep.adventures.filter('name = "Update Agent"').first()
        for node in self.ep.nodes:
            if 'agent' in node.facts['backends']:
                resp = self.ep.adventures[update_agent_adventure.id].execute(node=node.id)
                self.assertEquals(resp.status_code, 202)
                task = resp.task
                task.wait_for_complete()
