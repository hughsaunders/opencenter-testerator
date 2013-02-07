# vim: tabstop=4 shiftwidth=4 softtabstop=4

import os
import time
import unittest2
import requests

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
        self.server_name = os.environ.get('INSTANCE_SERVER_HOSTNAME',
                                          None)
        self.chef_name = os.environ.get('INSTANCE_CHEF_HOSTNAME',
                                        None)
        self.compute_name = os.environ.get('INSTANCE_COMPUTE_HOSTNAME',
                                           None)
        self.controller_name = os.environ.get('INSTANCE_CONTROLLER_HOSTNAME',
                                              None)
        self.ep = RoushEndpoint(self.endpoint_url)
        self.admin_ep = RoushEndpoint(self.endpoint_url + '/admin')

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        self.workspace = self.ep.nodes.filter('name = "workspace"').first()
        self.unprovisioned = self.ep.nodes.filter(
            "name = 'unprovisioned'").first()
        # Collect all the adventures we are going to run
        self.chef_svr = self.ep.adventures.filter(
            'name = "install chef server"').first()
        self.chef_cli = self.ep.adventures.filter(
            'name = "install chef client"').first()
        self.nova_clus = self.ep.adventures.filter(
            'name = "create nova cluster"').first()
        self.n_api = self.ep.adventures.filter(
            'name = "install nova controller"').first()
        self.n_cpu = self.ep.adventures.filter(
            'name = "install nova compute"').first()
        self.cluster_data = {
            'osops_public': '10.0.0.0/8', 'osops_mgmt': '10.0.0.0/8',
            'osops_nova': '10.0.0.0/8', 'nova_public_if': 'eth1',
            'nova_vm_bridge': 'br100', 'nova_dmz_cidr': '172.16.0.0/12',
            'cluster_name': 'test_cluster',
            'keystone_admin_pw': 'secrete', 'nova_vm_fixed_if': 'eth1',
            'nova_az': 'az1', 'nova_vm_fixed_range': '192.168.200.0/24'}

    def tearDown(self):
        pass

    def test_roush_happy_path(self):
        # Run the install-chef-server adventure on the node
        server = self.ep.nodes.filter(
            "name = '%s'" % self.server_name).first()
        resp = self.ep.adventure[3].execute(node=server.id)
        if resp.status_code != 202:
            self.assertTrue(False)

        # adventure is running, go poll
        self._poll_till_task_done(server, wait_time=900)

        # refresh the server object
        server._request('get')
        _validate_chef_server(server)

        # Lets check if the root workspace now has the correct adventure
        assertTrue(self.nova_clus.id in self.workspace.adventures.keys())
        # This will fail, as it needs input
        plan = self.ep.adventures[self.nova_clus.id].execute(
            node=workspace.id, **info)
        assertEquals(plan.status_code, 409)
        assertTrue(plan.requires_input)

        # Lets post back the new plan
        resp = self._post_new_plan(plan.execution_plan.raw_plan, workspace)
        assertEquals(resp.status_code, 202)

        # make sure test_cluster got created
        test_cluster = ep.nodes.filter(
            'name = "%s"' % self.cluster_data['cluster_name']).first()
        self.assertIsNotNone(test_cluster)
        self.assertEquals(test_cluster.facts['parent_id'], self.workspace.id)
        infra = ep.nodes.filter('name = "Infrastructure"').first()
        self.assertIsNotNone(infra)
        self.assertEquals(infra.facts['parent_id'], test_cluster.id)
        compute = ep.nodes.filter('name = "Compute"').first()
        self.assertIsNotNone(infra)
        self.assertEquals(compute.facts['parent_id'], test_cluster.id)

    def _post_new_plan(self, raw_plan, node):
        new_plan = self._update_plan(raw_plan)
        headers = {'content-type': 'application/json'}
        payload = {'node': node.id,
                   'plan': new_plan}
        # I know this works
        #resp = requests.post(self.ep.endpoint + '/plan/',
        #                     payload=json.dumps(payload),
        #                     headers=headers)
        #assertEquals(resp.status_code, 202)
        # I want this to work
        resp = ep.requests.post(self.ep.endpoint + '/plan/',
                                payload=json.dumps(payload),
                                headers=headers)
        return resp

    def _update_plan(self, plan):
        for entry in plan:
            if 'args' in entry:
                for arg in entry['args']:
                    if arg in self.cluster_data:
                        entry['args'][arg]['value'] = self.cluster_data[arg]
        return plan

    def _validate_chef_server(self, node):
        self.assertTrue('chef-server' in node.facts['backends'])
        fact_keys = ['chef_server_client_name', 'chef_server_client_pem',
                     'chef_server_pem', 'chef_server_uri',
                     'chef_webui_password']
        for key in fact_keys:
            self.assertIsNotNone(node.facts.get(key, None))

    def _poll_till_task_done(self, node, wait_time=10):
        task_list = node.tasks.keys()
        task = task_list.pop()
        count = 0
        while node.tasks[task].state != 'done':
            if count >= wait_time:
                break
            else:
                time.sleep(1)
                count += 1
