from TP_lib import epd2in13_V4

epd = epd2in13_V4.EPD()
epd.init(epd.FULL_UPDATE)
epd.Clear(0xFF)
epd.sleep()
epd2in13_V4.epdconfig.module_exit()

