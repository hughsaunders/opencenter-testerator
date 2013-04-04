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
        # Gather configuration data
        config = OpenCenterConfiguration()
        opencenter_config = config.opencenter_config
        cluster_data =  config.cluster_data
        vip_data = config.vip_data
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
        self.vip_data = {
            'nova_rabbitmq_vip': vip_data.nova_rabbitmq_vip,
            'nova_api_vip': vip_data.nova_api_vip,
            'nova_mysql_vip': vip_data.nova_mysql_vip
        }
        
        # Establish connections with endpoints
        if self.user:
            self.ep = OpenCenterEndpoint(self.endpoint_url, user=self.user, password=self.password)
        else:
            self.ep = OpenCenterEndpoint(self.endpoint_url)
        self.admin_ep = OpenCenterEndpoint(self.endpoint_url + '/admin', user=self.user, password=self.password)

        # Collect all the nodes we need
        self.workspace = self.find_node("workspace")
        self.unprovisioned = self.find_node('unprovisioned')

        # Collect all the adventures we are going to run
        self.chef_svr = self.ep.adventures.filter('name = "Install Chef Server"').first()
        self.chef_cli = self.ep.adventures.filter('name = "Install Chef Client"').first()
        self.nova_clus = self.ep.adventures.filter('name = "Create Nova Cluster"').first()
        self.n_api = self.ep.adventures.filter('name = "Install Nova Controller"').first()
        self.n_cpu = self.ep.adventures.filter('name = "Install Nova Compute"').first()
        self.download_cookbooks = self.ep.adventures.filter('name = "Download Chef Cookbooks"').first()
        self.upload_glance_images = self.ep.adventures.filter('name = "Upload Initial Glance Images"').first()
        self.enable_ha = self.ep.adventures.filter('name = "Enable HA Infrastructure"').first()

    def tearDown(self):
        pass

    def find_node(self, partial_name):
        """find a node by partial name match.
        Useful for unpredictable jenkins node names."""
        matches = [n for n in self.ep.nodes if
                   re.search(partial_name.strip(), n.name)]
        if matches:
            return matches[0]
        else:
            raise ValueError('No nodes found for pattern %s' % partial_name)

    def wait_for_all_tasks(self):
        while not all([t.complete for t in self.ep.tasks]):
            time.sleep(1)

    def test_opencenter_happy_path(self):
        """Happy path creates a chef server and lays down an openstack 
        cluster. If there's enough controllers in the configuration a
        second controller is created for HA"""
        
        # Run the install-chef-server adventure on the node
        chef_server = self.find_node(self.chef_name)
        resp = self.ep.adventures[self.chef_svr.id].execute(node=chef_server.id)
        self.assertEquals(resp.status_code, 202)

        # adventure is running, go poll
        task = resp.task
        task.wait_for_complete()

        # refresh the server object
        chef_server._request('get')
        self._validate_chef_server(chef_server)

        # Lets check if the root workspace now has the correct adventure
        self.assertTrue(self.nova_clus.id in self.workspace.adventures.keys())
        
        # Create an OpenStack cluster
        resp = self.ep.adventures[self.nova_clus.id].execute(
            node=self.workspace.id, plan_args=self.cluster_data)
        self.assertEquals(resp.status_code, 202)
        self.assertFalse(resp.requires_input)
        task = resp.task

        #only waits for adventurate tasks
        task.wait_for_complete()

        #wait for any other tasks to complete
        self.wait_for_all_tasks()

        for node in self.ep.nodes:
            print node.name, node.id

        for task in self.ep.tasks:
            print task.action, task.id, task.state

        # make sure test_cluster got created
        test_cluster = self.find_node(self.cluster_data['cluster_name'])
        self.assertIsNotNone(test_cluster)
        self.assertEquals(test_cluster.facts['parent_id'], self.workspace.id)
        infra_container = self.find_node("Infrastructure")
        self.assertIsNotNone(infra_container)
        self.assertEquals(infra_container.facts['parent_id'], test_cluster.id)
        compute_container = self.find_node("Compute")
        self.assertIsNotNone(compute_container)
        self.assertEquals(compute_container.facts['parent_id'], test_cluster.id)
        az_container = self.find_node("AZ nova")
        self.assertIsNotNone(az_container)
        self.assertEquals(az_container.facts['parent_id'], compute_container.id)
        
        
        controllers = []
        for controller_name in self.controller_name.split(","):
            controllers.append(self.find_node(controller_name))
        computes = []
        for compute_name in self.compute_name.split(","):
            computes.append(self.find_node(compute_name))
        
        # Reparent self.controller_name under the new infra container
        ha_enabled = False
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

            # Enable HA if possible
            if not ha_enabled and len(controllers) > 1:
                resp = self.ep.adventures[self.enable_ha.id].execute(
                    node=infra_container.id, plan_args=self.vip_data)
                self.assertEquals(resp.status_code, 202)
                self.assertFalse(resp.requires_input)
                task = resp.task
                task.wait_for_complete()
                infra_container._request('get')
                self.assertTrue(infra_container.facts['ha_infra'])
                ha_enabled = True
            
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

