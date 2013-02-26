# vim: tabstop=4 shiftwidth=4 softtabstop=4

import json
import os
import requests
import time
import unittest2

from opencenter.client import OpenCenterEndpoint


class ExampleTestCase(unittest2.TestCase):
    """
    This test case assumes a roush-server has been successfully created, and
    at least 3 nodes have roush-agent installed.
    """
    @classmethod
    def setUpClass(self):
        pass

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
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
        print "ENDPOINT_URL: %s" % self.endpoint_url
        print "SERVER_HOSTNAME: %s" % self.server_name
        print "COMPUTE_HOSTNAME: %s" % self.compute_name
        print "CONTROLLER_HOSTNAME: %s" % self.controller_name
        self.ep = OpenCenterEndpoint(self.endpoint_url)
        self.admin_ep = OpenCenterEndpoint(self.endpoint_url + '/admin')
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
        self.download_cookbooks = self.ep.adventures.filter(
            'name = "download chef cookbooks"').first()
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
        resp = self.ep.adventures[3].execute(node=server.id)
        self.assertEquals(resp.status_code, 202)

        # adventure is running, go poll
        task = resp.task
        task.wait_for_complete()
        # self._poll_till_task_done(server, wait_time=900)

        # refresh the server object
        server._request('get')
        self._validate_chef_server(server)

        # run the 'download chef cookbooks' adventure
        resp = self.ep.adventures[self.download_cookbooks.id].execute(node=server.id)
        self.assertEquals(resp.status_code, 202)
        task = resp.task
        task.wait_for_complete()
        # TODO(shep): probably need to assert against facts/attrs here

        # Lets check if the root workspace now has the correct adventure
        self.assertTrue(self.nova_clus.id in self.workspace.adventures.keys())
        # This will fail, as it needs input
        #plan = self.ep.adventures[self.nova_clus.id].execute(
        #    node=self.workspace.id, **self.cluster_data)
        #self.assertEquals(plan.status_code, 409)
        #self.assertTrue(plan.requires_input)

        # Trying new and improved adventure.execute()
        # new_plan = self._update_plan(plan.execution_plan.raw_plan)
        resp = self.ep.adventures[self.nova_clus.id].execute(
            node=self.workspace.id, plan_args=self.cluster_data)
        self.assertEquals(resp.status_code, 202)
        self.assertFalse(resp.requires_input)
        task = resp.task
        task.wait_for_complete()

        # # Lets post back the new plan
        # resp = self._post_new_plan(plan.execution_plan.raw_plan, self.workspace)
        # self.assertEquals(resp.status_code, 202)
	# task = resp.task
	# task.wait_for_complete()
        # # self._poll_till_task_done(self.workspace, wait_time=6)

        # make sure test_cluster got created
        test_cluster = self.ep.nodes.filter(
            'name = "%s"' % self.cluster_data['cluster_name']).first()
        self.assertIsNotNone(test_cluster)
        self.assertEquals(test_cluster.facts['parent_id'], self.workspace.id)
        infra_container = self.ep.nodes.filter('name = "Infrastructure"').first()
        self.assertIsNotNone(infra_container)
        self.assertEquals(infra_container.facts['parent_id'], test_cluster.id)
        compute_container = self.ep.nodes.filter('name = "Compute"').first()
        self.assertIsNotNone(compute_container)
        self.assertEquals(compute_container.facts['parent_id'], test_cluster.id)

        # Install chef-client
        new_controller = self.ep.nodes.filter('name = "%s"' % self.controller_name).first()
        new_compute = self.ep.nodes.filter('name = "%s"' % self.compute_name).first()
        for srv in [new_controller, new_compute]:
            resp = self.ep.adventures[self.chef_cli.id].execute(
                node=srv.id)
            self.assertEquals(resp.status_code, 202)
            self.assertFalse(resp.requires_input)
            task = resp.task
            task.wait_for_complete()

	# Reparent self.controller_name under the new infra container
        self._reparent(new_controller, infra_container)
 	new_controller._request('get')
        self.assertEquals(new_controller.facts['parent_id'], infra_container.id)

	# Reparent self.controller_name under the new infra container
        new_compute = self.ep.nodes.filter('name = "%s"' % self.compute_name).first()
        self._reparent(new_compute, compute_container)
        new_compute._request('get')
        self.assertEquals(new_compute.facts['parent_id'], compute_container.id)

    def _reparent(self, child_node, parent_node):
        new_fact = self.ep.facts.create(node_id=child_node.id, key='parent_id', value=parent_node.id)
        resp = new_fact.save()
        self.assertEquals(resp.status_code, 202)
        task = resp.task
        task.wait_for_complete()


    def _post_new_plan(self, raw_plan, node):
        new_plan = self._update_plan(raw_plan)
        headers = {'content-type': 'application/json'}
        payload = {'node': node.id,
                   'plan': new_plan}
        # I know this works
        #resp = requests.post(self.ep.endpoint + '/plan/',
        #                     data=json.dumps(payload),
        #                     headers=headers)
        # I want this to work
        resp = self.ep.requests.post(self.ep.endpoint + '/plan/',
                                     data=json.dumps(payload),
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
                     'chef_server_pem', 'chef_server_uri']
        for key in fact_keys:
            self.assertIsNotNone(node.facts.get(key, None))

    def _poll_till_task_done(self, node, wait_time=10):
        time.sleep(5)
        task_list = node.tasks.keys()
        task = task_list.pop()
        count = 0
        while node.tasks[task].state != 'done':
            if count >= wait_time:
                break
            else:
                time.sleep(5)
                count += 1
