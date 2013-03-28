# vim: tabstop=4 shiftwidth=4 softtabstop=4

import json
import os
import requests
import time
import unittest2

from opencenter.config import OpenCenterConfiguration
from opencenterclient.client import OpenCenterEndpoint
import re


class OpenCenterTestCase(unittest2.TestCase):
    """
    This test case assumes a opencenter-server has been successfully created, and
    at least 3 nodes have opencenter-agent installed.
    """
    @classmethod
    def setUpClass(self):
        pass

    @classmethod
    def tearDownClass(self):
        pass

    def setUp(self):
        
        config = OpenCenterConfiguration()
        opencenter_config = config.opencenter_config
        cluster_data = config.cluster_data
        
        self.endpoint_url = opencenter_config.endpoint_url
        self.server_name = opencenter_config.instance_server_hostname
        self.chef_name = opencenter_config.instance_chef_hostname
        self.compute_name = opencenter_config.instance_compute_hostname
        self.controller_name = opencenter_config.instance_controller_hostname
        self.user = opencenter_config.user
        self.password = opencenter_config.password
             
        self.cluster_data = {
            'osops_public': cluster_data.osops_public,
            'osops_mgmt': cluster_data.osops_mgmt,
            'osops_nova': cluster_data.osops_nova, 
            'nova_public_if': cluster_data.nova_public_if,
            'nova_vm_bridge': cluster_data.nova_vm_bridge, 
            'nova_dmz_cidr': cluster_data.nova_dmz_cidr,
            'cluster_name': cluster_data.cluster_name,
            'keystone_admin_pw': cluster_data.keystone_admin_pw,
            'nova_vm_fixed_if': cluster_data.nova_vm_fixed_if,
            'nova_vm_fixed_range': cluster_data.nova_vm_fixed_range,
            'libvirt_type': cluster_data.libvirt_type
        }
        
        if self.user:
            self.ep = OpenCenterEndpoint(self.endpoint_url, user=self.user, password=self.password)
        else:
            self.ep = OpenCenterEndpoint(self.endpoint_url)
            
        self.admin_ep = OpenCenterEndpoint(self.endpoint_url + '/admin', user=self.user, password=self.password)
        self.workspace = self.ep.nodes.filter('name = "workspace"').first()
        self.unprovisioned = self.ep.nodes.filter("name = 'unprovisioned'").first()
        # Collect all the adventures we are going to run
        self.chef_svr = self.ep.adventures.filter('name = "Install Chef Server"').first()
        self.chef_cli = self.ep.adventures.filter('name = "Install Chef Client"').first()
        self.nova_clus = self.ep.adventures.filter('name = "Create Nova Cluster"').first()
        self.n_api = self.ep.adventures.filter('name = "Install Nova Controller"').first()
        self.n_cpu = self.ep.adventures.filter('name = "Install Nova Compute"').first()
        self.download_cookbooks = self.ep.adventures.filter('name = "Download Chef Cookbooks"').first()
        self.upload_glance_images = self.ep.adventures.filter('name = "Upload Initial Glance Images"').first()

    def tearDown(self):
        pass

    def find_node(self, partial_name):
        matches = [n for n in self.ep.nodes if
                   re.search(partial_name, n.name)]
        if matches:
            return matches[0]
        else:
            raise ValueError('No nodes found for pattern %s' % partial_name )


    def test_opencenter_happy_path(self):

        chef_node = self.find_node(self.chef_name)
        # Run the install-chef-server adventure on the chef node
        resp = self.ep.adventures[self.chef_svr.id].execute(
            node=chef_node.id)
        self.assertEquals(resp.status_code, 202)

        # adventure is running, go poll
        task = resp.task
        task.wait_for_complete()
        # self._poll_till_task_done(server, wait_time=900)

        # refresh the server object
        chef_node._request('get')
        self._validate_chef_server(chef_node)

        # run the 'download chef cookbooks' adventure
        # resp = self.ep.adventures[self.download_cookbooks.id].execute(
        #     node=chef_node.id)
        # self.assertEquals(resp.status_code, 202)
        # task = resp.task
        # task.wait_for_complete()
        # TODO(shep): probably need to assert against facts/attrs here

        # Lets check if the root workspace now has the correct adventure
        self.assertTrue(self.nova_clus.id in self.workspace.adventures.keys())
        
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
        az_container = self.ep.nodes.filter('name = "AZ nova"').first()
        self.assertIsNotNone(az_container)
        self.assertEquals(az_container.facts['parent_id'], compute_container.id)

        controllers = []
        for controller_name in self.controller_name.split(","):
            controllers.append(self.find_node(controller_name))
        computes = []
        for compute_name in self.compute_name.split(","):
            computes.append(self.find_node(compute_name))

        # new_controller = self.find_nodes(controller_name)
        # new_compute = self.find_node(self.compute_name)
        
        # Install chef-client
        for srv in (controllers + computes):
            resp = self.ep.adventures[self.chef_cli.id].execute(
                node=srv.id)
            self.assertEquals(resp.status_code, 202)
            self.assertFalse(resp.requires_input)
            task = resp.task
            task.wait_for_complete()
        
	    # Reparent self.controller_name under the new infra container
        for new_controller in controllers:
            self._reparent(new_controller, infra_container)
            new_controller._request('get')
            self.assertEquals(new_controller.facts['parent_id'], infra_container.id)
            
            #Upload initial glance images
            resp = self.ep.adventures[self.upload_glance_images.id].execute(
                        node=new_controller.id, plan_args=self.cluster_data)
            self.assertEquals(resp.status_code, 202)
            self.assertFalse(resp.requires_input)
            task = resp.task
            task.wait_for_complete()
            
            

	    # Reparent self.controller_name under the new infra container
        for new_compute in computes:
            self._reparent(new_compute, az_container)
            new_compute._request('get')
            self.assertEquals(new_compute.facts['parent_id'], az_container.id)
            


    def _reparent(self, child_node, parent_node):
        new_fact = self.ep.facts.create(node_id=child_node.id, key='parent_id', value=parent_node.id)
        resp = new_fact.save()
        self.assertEquals(resp.status_code, 202)
        task = resp.task
        task.wait_for_complete()
        time.sleep(10)
        #Wait for the chain of adventures that follow to finish 
        tasks = self.ep.nodes[child_node.id].tasks
        for task in tasks:
            task.wait_for_complete()
            if (tasks != self.ep.nodes[child_node.id].tasks):
                tasks = self.ep.nodes[child_node.id].tasks

    def _validate_chef_server(self, node):
        self.assertTrue('chef-server' in node.facts['backends'])
        fact_keys = ['chef_server_client_name', 'chef_server_client_pem',
                     'chef_server_pem', 'chef_server_uri']
        for key in fact_keys:
            self.assertIsNotNone(node.facts.get(key, None))

