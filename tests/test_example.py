# vim: tabstop=4 shiftwidth=4 softtabstop=4

import os
import unittest2

from roushclient.client import RoushEndpoint

class ExampleTestCase(unittest2.TestCase):
    @classmethod
    def setUpClass(self):
        self.endpoint_url = os.environ.get('ROUSH_ENDPOINT', 'http://127.0.0.0:8080')
        pass

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        self.ep = RoushEndpoint(self.endpoint_url)
        self.admin_ep = RoushEndpoint(self.endpoint_url + '/admin')

    def tearDown(self):
        pass

    def test_example_test(self):
        print self.endpoint_url
        print self.ep
        print self.admin_ep
        pass
