#!/bin/bash

# for pi-demo, configure the demo options 
# can be launched manually (must be as root), or by a systemd service (cf pi-demo.service)


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
# our own models
# export MODEL_PATH='/data/models/pi-deployment/01b-pre-x52-1455'
export MODEL_PATH='/data/models/pi-deployment/04b-pre-x59-2405'
# export MODEL_PATH='/data/models/pi-deployment/04b-tunefull-x58-562'
# export MODEL_PATH='/data/models/pi-deployment/1b5-pre-x59-929'

####
# prompts
# export PROMPT_PATH='/boot/prompts-qa.txt'
export PROMPT_PATH='/boot/prompts-topics.txt'

python3 /root/workspace-rwkv/llm-epaper-demo/pi-demo.py