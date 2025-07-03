#!/bin/bash
echo "${file_content}" > /home/ubuntu/tf-cloud-init
sudo chown ubuntu tf-cloud-init  
chmod 600 /home/ubuntu/tf-cloud-init
