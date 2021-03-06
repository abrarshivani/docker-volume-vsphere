#!/usr/bin/env python
# Copyright 2016 VMware, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Utility functions for dealing with vmdks and datastores

import os
import logging
import pyVim.connect
import vsan_info

# datastores should not change during 'vmdkops_admin' run,
# so using global to avoid multiple scans of /vmfs/volumes
datastores = None

# we assume files smaller that that to be descriptor files
MAX_DESCR_SIZE = 10000


def get_datastores():
    """
    Return pairs of datastore names and absolute paths to dockvols directory,
    after following the symlink
    """

    global datastores
    if datastores != None:
        return datastores

    si = pyVim.connect.Connect()
    #  We are connected to ESX so childEntity[0] is current DC/Host
    ds_objects = si.content.rootFolder.childEntity[
        0].datastoreFolder.childEntity
    datastores = [(d.info.name, os.path.join(d.info.url, 'dockvols'))
                  for d in ds_objects]
    pyVim.connect.Disconnect(si)

    return datastores


def get_vsan_dockvols_path():
    """
    Return the VSAN datastore dockvols path for a given cluster. Default to the
    first datastore for now, so we can test without VSAN.
    """
    datastore = vsan_info.get_vsan_datastore()
    if datastore:
        return os.path.join(datastore.info.url, 'dockvols')
    else:
        return None


def get_volumes():
    """ Return dicts of docker volumes, their datastore and their paths """
    volumes = []
    for (datastore, path) in get_datastores():
        for file_name in list_vmdks(path):
            volumes.append({'path': path,
                            'filename': file_name,
                            'datastore': datastore})
    return volumes


def list_vmdks(path):
    """ Return a list all VMDKs in a given path """
    try:
        files = os.listdir(path)
        return [f for f in files
                if vmdk_is_a_descriptor(os.path.join(path, f))]
    except OSError as e:
        # dockvols may not exists on a datastore, so skip it
        return []


def vmdk_is_a_descriptor(filepath):
    """
    Is the file a vmdk descriptor file?  We assume any file that ends in .vmdk
    and has a size less than MAX_DESCR_SIZE is a desciptor file.
    """
    if filepath.endswith('.vmdk') and os.stat(filepath).st_size < MAX_DESCR_SIZE:
        try:
            with open(filepath) as f:
                line = f.readline()
                return line.startswith('# Disk DescriptorFile')
        except:
            logging.exception("Failed to open %s for descriptor check", filepath)

    return False


def strip_vmdk_extension(filename):
    """ Remove the .vmdk file extension from a string """
    return filename.replace(".vmdk", "")
