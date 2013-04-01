# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import ConfigParser
import logging
import os


class BaseConfig(object):

    SECTION_NAME = None

    def __init__(self, conf):
        self.conf = conf

    def get(self, item_name, default_value=None):
        try:
            return self.conf.get(self.SECTION_NAME, item_name, raw=True)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default_value




class OpenCenterConfig(BaseConfig):
    SECTION_NAME = "opencenter"

    @property
    def endpoint_url(self):
        return self.get("endpoint_url", '127.0.0.0:8080')
    
    @property
    def instance_server_hostname(self):
        return self.get("instance_server_hostname", 'opencenter-server')
    
    @property
    def instance_chef_hostname(self):
        return self.get("instance_chef_hostname", 'opencenter-server')
    
    @property
    def instance_controller_hostname(self):
        return self.get("instance_controller_hostname", 'opencenter-agent1')
    
    @property
    def instance_compute_hostname(self):
        return self.get("instance_compute_hostname", 'opencenter-agent2')
        
    @property
    def user(self):
        return self.get("user", None)
    
    @property
    def password(self):
        return self.get("password", None)
    
    
   
        
    
    
    
    
    
class ClusterDataConfig(BaseConfig):
    SECTION_NAME = "cluster_data"

    @property
    def libvirt_type(self):
        return self.get("libvirt_type", "kvm")
    
    @property
    def osops_public(self):
        return self.get("osops_public", '10.0.0.0/8')
    
    @property
    def osops_mgmt(self):
        return self.get("osops_mgmt", '10.0.0.0/8')
    
    @property
    def osops_nova(self):
        return self.get("osops_nova", '10.0.0.0/8')
  
    @property
    def nova_public_if(self):
        return self.get("nova_public_if", 'eth0')
  
    @property
    def nova_vm_bridge(self):
        return self.get("nova_vm_bridge", 'br100')
  
    @property
    def nova_dmz_cidr(self):
        return self.get("nova_dmz_cidr", '172.16.0.0/12')
  
    @property
    def cluster_name(self):
        return self.get("cluster_name", 'test_cluster')
  
    @property
    def keystone_admin_pw(self):
        return self.get("keystone_admin_pw", 'secret')
  
    @property
    def nova_vm_fixed_if(self):
        return self.get("nova_vm_fixed_if", 'eth1')
  
    @property
    def nova_vm_fixed_range(self):
        return self.get("nova_vm_fixed_range", '192.168.200.0/24')
  


    
class VipConfig(BaseConfig):
    SECTION_NAME = "vip_data"

    @property
    def nova_api_vip(self):o
        return self.get("nova_api_vip")

    @property
    def mysql_vip(self):
        return self.get("mysql_vip")    

    @property
    def rabbit_vip(self):
        return self.get("rabbit_vip")    
    

def singleton(cls):
    """Simple wrapper for classes that should only have a single instance"""
    instances = {}

    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]
    return getinstance


@singleton
class OpenCenterConfiguration:
    """Provides OpenStack configuration information."""

    DEFAULT_CONFIG_DIR = os.path.join(
        os.path.abspath(
          os.path.dirname(
            os.path.dirname(__file__))),
        "etc")

    DEFAULT_CONFIG_FILE = "opencenter.conf"

    def __init__(self):
        """Initialize a configuration from a conf directory and conf file."""
        # Environment variables override defaults...
        
        self.log = logging.getLogger(__name__)
        self.log.setLevel(getattr(logging, "INFO"))
                
        conf_dir = os.environ.get('OPENCENTER_CONFIG_DIR',self.DEFAULT_CONFIG_DIR)
        conf_file = os.environ.get('OPENCENTER_CONFIG', self.DEFAULT_CONFIG_FILE)
        path = os.path.join(conf_dir, conf_file)
        self.log.info("Using opencenter config file %s" % path)
        if not os.path.exists(path):
            msg = "**** Config file %(path)s NOT FOUND ****" % locals()
            raise RuntimeError(msg)
        self.conf = self.load_config(path)

        self.opencenter_config = OpenCenterConfig(self.conf)
        self.cluster_data = ClusterDataConfig(self.conf)
        

    def load_config(self, path):
        """Read configuration from given path and return a config object."""
        config = ConfigParser.SafeConfigParser()
        config.read(path)
        return config
    
    def get(self, section, item_name, default_value=None):
        try:
            return self.conf.get(section, item_name, raw=True)
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            return default_value
        
        
        

