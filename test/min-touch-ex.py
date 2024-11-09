###############  touch device #####################
# cf: https://www.waveshare.com/wiki/2.13inch_Touch_e-Paper_HAT_Manual#Touch_Driver (for C) 

# GT_Development -- stores information about the current touch points
import threading
import logging

from TP_lib import gt1151, epd2in13_V4

flag_t = 1   # flag: if gt.INT is high, indicates a touch event

# touch dev polling thread, set a flag showing if a touch even has occurred
# xzl: NB: GT_Dev is a global obj. ::Touch is a flag set by this thread
# below polling???
# ::Touch will be examined by class code of GT1151::GT_scan()
def pthread_irq() :
    print("pthread running")    
    while flag_t == 1 :
    # xzl: non blocking? inefficient...     
        if(gt.digital_read(gt.INT) == 0) :    
            GT_Dev.Touch = 1
        else :
            GT_Dev.Touch = 0
    print("thread:exit")
    
xres = 250
# transpose, and mirror, so that top/left is 0,0 and long side is x axis    
def transpose_touch(GT_dev):
    tr = gt1151.GT_Development()
    tr.Touch = GT_dev.Touch
    tr.TouchpointFlag = GT_dev.TouchpointFlag
    tr.TouchCount = GT_dev.TouchCount
    tr.Touchkeytrackid = GT_dev.Touchkeytrackid
    tr.S = GT_dev.S
    tr.X = GT_dev.Y
    tr.Y = GT_dev.X
    tr.X = [xres - x for x in tr.X]
    return tr
    
def transpose_touch_inplace(dev):
    dev.X, dev.Y = dev.Y, dev.X         # transpose
    dev.X = [xres - x for x in dev.X]   # mirror
    
###############  start of mini touch ex #####################
try: 
    epd = epd2in13_V4.EPD()
    gt = gt1151.GT1151()
    GT_Dev = gt1151.GT_Development()
    # seems to be used to store the old or previous state of the touch information
    GT_Old = gt1151.GT_Development()

    epd.init(epd.FULL_UPDATE)   # must do this, otherwise, touch won't work (io error)
    gt.GT_Init()

    # touch dev polling thread
    t = threading.Thread(target = pthread_irq)
    t.setDaemon(True)
    t.start()

    '''
     five buttons on bottom: 
    x,y ~=
    25,110
    80,110
    135,110
    180,110
    235,110
    '''

    while (1):
        gt.GT_Scan(GT_Dev, GT_Old)

        # dedup, avoid exposing repeated events to app
        if(GT_Old.X[0] == GT_Dev.X[0] and GT_Old.Y[0] == GT_Dev.Y[0] and GT_Old.S[0] == GT_Dev.S[0]):
            continue

        if(GT_Dev.TouchpointFlag):
            GT_Dev.TouchpointFlag = 0

            tr_new=transpose_touch(GT_Dev)
            tr_old=transpose_touch(GT_Old)
            print(f"tr_new GT_Dev.X[0]: {tr_new.X[0]}, tr_new GT_Dev.Y[0]: {tr_new.Y[0]}, tr_new GT_Dev.S[0]: {tr_new.S[0]}")

            # transpose_touch_inplace(GT_Dev)
            # transpose_touch_inplace(GT_Old)

            # meaning touch event ready to be read out
            # if(GT_Dev.TouchpointFlag):
            #     GT_Dev.TouchpointFlag = 0
            #     print(f"touch ev GT_Dev.X[0]: {GT_Dev.X[0]}, GT_Dev.Y[0]: {GT_Dev.Y[0]}, GT_Dev.S[0]: {GT_Dev.S[0]}")

except IOError as e:
    print("io error")
    logging.info(e)

except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    exit()