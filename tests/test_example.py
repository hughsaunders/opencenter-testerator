# vim: tabstop=4 shiftwidth=4 softtabstop=4

import os
import time
import unittest2

from roushclient.client import RoushEndpoint


class ExampleTestCase(unittest2.TestCase):
    """
    This test case assumes a roush-server has been successfully created, and
    at least 3 nodes have roush-agent installed.
    """
    @classmethod
    def setUpClass(self):
        self.endpoint_url = os.environ.get('ROUSH_ENDPOINT',
                                           'http://127.0.0.0:8080')
        pass

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        self.ep = RoushEndpoint(self.endpoint_url)
        self.admin_ep = RoushEndpoint(self.endpoint_url + '/admin')
        self.unprovisioned = self.ep.nodes.filter(
            "name = 'unprovisioned'").first()

    def tearDown(self):
        pass

    def test_example_test(self):
        # Examine all nodes and for every one with a backend of node, set
        #   their parent_id to the 'unprovisioned' container
        nodes = self.ep.nodes.filter(
            "'container' ! in facts.backends")
        for node in nodes:
            new_fact = self.ep.facts.create(node_id=node.id,
                                            key='parent_id',
                                            value=self.unprovisioned.id)
            new_fact.save()
            # sleep for 5 seconds to let the async operations process
            time.sleep(2)
            self.ep.nodes._refresh(True)
            self.ep.facts._refresh(True)
            self.assertEquals(node.facts['parent_id'],
                              self.unprovisioned.id)
