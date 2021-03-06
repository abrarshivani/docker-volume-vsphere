#!/bin/sh
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


# This script sets up the testbed.

usage() {
  echo "$0 <ESX IP> <VM1 IP> <VM2 IP> <Build id>"
  echo "root user will be used for all operations"
  echo "Advisable to setup ssh keys."
  echo "run this script from the root of the repo"
}

if [ $# -lt 3 ]
then
  usage
  exit 1
fi

BUILD_NUMBER=$4

export ESX=$1
export VM1=$2
export VM2=$3

USER=root
. ./misc/scripts/commands.sh
. ./misc/drone-scripts/cleanup.sh
. ./misc/drone-scripts/dump_log.sh

echo "Setting up lock on $ESX"
$SCP ./misc/drone-scripts/lock.sh $ESX:/tmp/

# Unlock performed in stop_build in cleanup.sh
until $SSH $USER@$ESX "sh /tmp/lock.sh lock $BUILD_NUMBER"
 do
  sleep 30
  log "Retrying acquire lock"
done 

dump_vm_info() {
  set -x
  $SSH $USER@$1 uname -a
  $SSH $USER@$1 docker version
  set +x
}

dump_esx_info() {
  set -x
  $SSH $USER@$ESX uname -a
  $SSH $USER@$ESX vmware -vl
  set +x
}

truncate_vm_logs() {
  $SSH $USER@$1 "cat /dev/null > /var/log/docker-volume-vsphere.log"
}

truncate_esx_logs() {
  $SSH $USER@$ESX "cat /dev/null > /var/log/vmware/vmdk_ops.log"
}

log "Acquired lock for build $BUILD_NUMBER"

log "truncate vm logs"
truncate_vm_logs $VM1
truncate_vm_logs $VM2

log "truncate esx logs"
truncate_esx_logs

log "starting deploy and test"

make clean-vm
make clean-esx

if make deploy-esx deploy-vm testasroot testremote TEST_VOL_NAME=vol-build$BUILD_NUMBER;
then
  dump_esx_info $ESX
  dump_vm_info $VM1
  dump_vm_info $VM2
  dump_log $VM1 $VM2 $ESX
  stop_build $VM1 $BUILD_NUMBER
else
  log "deploy failed cleaning up"
  log " Dumping logs..."
  dump_log $VM1 $VM2 $ESX
  stop_build $VM1 $BUILD_NUMBER
  exit 1
fi
