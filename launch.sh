#!/bin/bash

# for pi-demo, configure the demo options 
# 1. can be launched manually (must be as root), 

# 2. by a systemd service (cf pi-demo.service)
# to install: 
#       cp launch.sh /boot/


WORKDIR=/root/workspace-rwkv/llm-epaper-demo

# RUN THE VANILLA RWKV INFERENCE ENGINE (x51, x52 only)
# installed w/ the vanilla rwkv
#source /root/workspace-rwkv/rootenv/bin/activate

# RUN OUR OWN RWKV INFERENCE ENGINE 
# installed with our own rwkv packge
source /root/workspace-rwkv/myenv/bin/activate

####
# models
# official model
# export MODEL_PATH='/data/models/pi-deployment/RWKV-5-World-0.1B-v1-20230803-ctx4096'
# our own models (no cls, no mlp)
# export MODEL_PATH='/data/models/pi-deployment/01b-pre-x52-1455'
export MODEL_PATH='/data/models/pi-deployment/04b-pre-x59-2405'
# export MODEL_PATH='/data/models/pi-deployment/04b-tunefull-x58-562'
# export MODEL_PATH='/data/models/pi-deployment/1b5-pre-x59-929'
# our own models (cls, mlp)
# export MODEL_PATH='/data/models/orin-deployment/01b-x59'
# export MODEL_PATH='/data/models/orin-deployment/04b-x59'

####
# prompts
# export PROMPT_PATH='/boot/prompts-qa.txt'
export PROMPT_PATH='/boot/prompts-topics.txt'

cd $WORKDIR &&
python3 /root/workspace-rwkv/llm-epaper-demo/pi-demo.py