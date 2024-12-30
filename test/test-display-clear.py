#!/usr/bin/python
# -*- coding:utf-8 -*-


'''
fxl: works for both touch and non-touch display 
'''

import sys
import os
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic/2in13')
fontdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)
    
from TP_lib import gt1151
from TP_lib import epd2in13_V4
import time
import logging
from PIL import Image,ImageDraw,ImageFont
import traceback
import threading

# logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

logging.info("epd2in13_V4 Touch Demo")

epd = epd2in13_V4.EPD()
gt = gt1151.GT1151()
GT_Dev = gt1151.GT_Development()
GT_Old = gt1151.GT_Development()

logging.info("init and Clear")

epd.init(epd.FULL_UPDATE)
# gt.GT_Init()
epd.Clear(0xFF)