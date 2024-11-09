
'''
# by FL, for orange pi, Nov 2024
# path: /home/orangepi/workspace-waveshare/Touch_e-Paper_Code/python/lib/TP_lib/epdconfig_ori.py
then 
from . import epdconfig_ori as config
'''

# import gpiozero
import wiringpi as wp
import time
from smbus import SMBus
import spidev
import ctypes
import logging

# e-Paper
# these are Pin numbers as in 'wiringPi lib', also referred to as 'wPi' numbers
EPD_RST_PIN     = 5
EPD_DC_PIN      = 13
EPD_CS_PIN      = 15    # in fact, ununsed (FL
EPD_BUSY_PIN    = 10

# TP
TRST    = 8
INT     = 7

# spi     = spidev.SpiDev(0, 0)
spi     = spidev.SpiDev(1, 0)   # xzl: opi spi-1, chip select 0 /dev/spidev1.0
address = 0x0
# address = 0x14
# address = 0x48
# bus     = SMBus(1)
bus     = SMBus(3)      # xzl: opi /dev/i2c-3 is used for touch panel...

wp.wiringPiSetup()

# configure the GPIO pins...
wp.pinMode(EPD_RST_PIN, wp.OUTPUT)   # Set RST pin as output
wp.pinMode(EPD_DC_PIN, wp.OUTPUT)    # Set DC pin as output
wp.pinMode(TRST, wp.OUTPUT)          # Set TRST pin as output

wp.pinMode(EPD_BUSY_PIN, wp.INPUT)   # Set BUSY pin as input
wp.pullUpDnControl(EPD_BUSY_PIN, wp.PUD_OFF)  # Disable pull-up for BUSY pin (same as pull_up=False in gpiozero)

wp.pinMode(INT, wp.INPUT)            # Set INT pin as input
wp.pullUpDnControl(INT, wp.PUD_OFF)  # Disable pull-up for INT pin

# Function to write digital values to pins (translation from gpiozero to WiringPi)
def digital_write(pin, value):
    if pin == EPD_RST_PIN:
        if value:
            wp.digitalWrite(EPD_RST_PIN, wp.HIGH)
        else:
            wp.digitalWrite(EPD_RST_PIN, wp.LOW)
    elif pin == EPD_DC_PIN:
        if value:
            wp.digitalWrite(EPD_DC_PIN, wp.HIGH)
        else:
            wp.digitalWrite(EPD_DC_PIN, wp.LOW)
    # CS -- do nothing
    elif pin == TRST:
        if value:
            wp.digitalWrite(TRST, wp.HIGH)
        else:
            wp.digitalWrite(TRST, wp.LOW)

    # xzl: how about other pins? do nothing?

# Function to read digital values from pins (translation from gpiozero to WiringPi)
def digital_read(pin):
    if pin == EPD_BUSY_PIN:
        return wp.digitalRead(EPD_BUSY_PIN)
    elif pin == INT:
        return wp.digitalRead(INT)


# --- below are same from the original epdconfig.py ---

def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)

def spi_writebyte(data):
    spi.writebytes(data)

def spi_writebyte2(data):
    spi.writebytes2(data)

def i2c_writebyte(reg, value):
    bus.write_word_data(address, (reg>>8) & 0xff, (reg & 0xff) | ((value & 0xff) << 8))

def i2c_write(reg):
    bus.write_byte_data(address, (reg>>8) & 0xff, reg & 0xff)

def i2c_readbyte(reg, len):
    i2c_write(reg)
    rbuf = []
    for i in range(len):
        rbuf.append(int(bus.read_byte(address)))
    return rbuf

def module_init():
   
    spi.max_speed_hz = 10000000
    spi.mode = 0b00
    
    # wp.wiringPiSetup()

    return 0

def module_exit():
    logging.debug("spi end")
    spi.close()
    bus.close()
        
    logging.debug("close 5V, Module enters 0 power consumption ...")
    wp.digitalWrite(EPD_RST_PIN, wp.LOW)
    wp.digitalWrite(EPD_DC_PIN, wp.LOW)
    # wp.digitalWrite(EPD_CS_PIN, wp.LOW)  # Uncomment if EPD_CS_PIN is defined and used
    wp.digitalWrite(TRST, wp.LOW)

    # There is no need for .close() in WiringPi; simply setting the pins LOW is enough.
    # Input pins do not need to be explicitly closed.
    

### END OF FILE ###
