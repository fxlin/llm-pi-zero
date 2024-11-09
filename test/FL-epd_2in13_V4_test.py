#!/usr/bin/python
# -*- coding:utf-8 -*-


'''
xzl: only display, no touch
'''

import sys
import os
picdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pic')
libdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
from waveshare_epd import epd2in13_V4
import time
from PIL import Image,ImageDraw,ImageFont
import traceback

logging.basicConfig(level=logging.DEBUG)

try:
    logging.info("epd2in13_V4 Demo")
    
    epd = epd2in13_V4.EPD()
    logging.info("init and Clear")
    epd.init()
    epd.Clear(0xFF)

    # breakpoint()
    # Drawing on the image
    font15 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 15)
    font24 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 24)
    
    if 1:
        logging.info("E-paper refresh")
        epd.init()

        # xzl
        font_title = font24
        font_text = font15

        #######################################

        # Create the base image with the title
        base_image = Image.new('1', (epd.height, epd.width), 255)  # 1-bit image (black and white)
        base_draw = ImageDraw.Draw(base_image)
        base_draw.text((10, 10), "Title", font=font_title, fill=0)  # Draw the title at the top

        # Display the base image
        buffer = epd.getbuffer(base_image)
        epd.displayPartBaseImage(buffer)

        # List of text lines to display
        text_lines = [
            "This is line 1.",
            "This is line 2.",
            "This is line 3.",
            "This is line 4.",
            "This is line 5."
        ]

        # Start adding words incrementally below the title
        y_position = 40
        for line in text_lines:
            words = line.split()
            current_text = ""
            for word in words:
                # Add the next word to the current text
                current_text += word + " "

                # Draw the updated text on the base image
                base_draw.text((10, y_position), current_text, font=font_text, fill=0)

                # Update the e-ink display with the new word using partial update
                buffer = epd.getbuffer(base_image)
                epd.displayPartial(buffer)

                # Wait for 100ms before adding the next word
                time.sleep(0.1)
            
            # Move to the next line position
            y_position += 20

        #######################################

        # Create the base image with the title
        base_image = Image.new('1', (epd.height, epd.width), 255)  # 1-bit image (black and white)
        base_draw = ImageDraw.Draw(base_image)
        base_draw.text((10, 10), "Title", font=font_title, fill=0)  # Draw the title at the top

        # List of text lines to display
        text_lines = [
            "This is line 1.",
            "This is line 2.",
            "This is line 3.",
            "This is line 4.",
            "This is line 5."
        ]

        # Start adding lines of text below the title
        for idx, line in enumerate(text_lines):
            # Create an image for the partial update
            # partial_image = Image.new('1', (epd.height, epd.width), 255)
            # partial_draw = ImageDraw.Draw(partial_image)

            # Draw the new line of text (each line is spaced 20 pixels apart)
            y_position = 40 + idx * 20
            base_draw.text((10, y_position), line, font=font_text, fill=0)

            # Update the e-ink display with the new line using partial update
            buffer = epd.getbuffer(base_image)
            epd.displayPartial(buffer)

            # Wait for 1 second before adding the next line
            time.sleep(1)

        #######################################

        logging.info("1.Drawing on the image...")
        image = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame    
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0,0),(50,50)],outline = 0)
        draw.rectangle([(55,0),(100,50)],fill = 0)
        draw.line([(0,0),(50,50)], fill = 0,width = 1)
        draw.line([(0,50),(50,0)], fill = 0,width = 1)
        draw.chord((10, 60, 50, 100), 0, 360, fill = 0)
        draw.ellipse((55, 60, 95, 100), outline = 0)
        draw.pieslice((55, 60, 95, 100), 90, 180, outline = 0)
        draw.pieslice((55, 60, 95, 100), 270, 360, fill = 0)
        draw.polygon([(110,0),(110,50),(150,25)],outline = 0)
        draw.polygon([(190,0),(190,50),(150,25)],fill = 0)
        draw.text((120, 60), 'e-Paper demo', font = font15, fill = 0)
        draw.text((110, 90), u'微雪电子', font = font24, fill = 0)
        # image = image.rotate(180) # rotate
        epd.display(epd.getbuffer(image))
        time.sleep(2)
        
        # read bmp file 
        logging.info("2.read bmp file...")
        image = Image.open(os.path.join(picdir, '2in13.bmp'))
        epd.display(epd.getbuffer(image))
        time.sleep(2)
        
        # read bmp file on window
        logging.info("3.read bmp file on window...")
        # epd.Clear(0xFF)
        image1 = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame
        bmp = Image.open(os.path.join(picdir, '100x100.bmp'))
        image1.paste(bmp, (2,2))    
        epd.display(epd.getbuffer(image1))
        time.sleep(2)
        
       
    else:
        logging.info("E-paper refreshes quickly")
        epd.init_fast()
        logging.info("1.Drawing on the image...")
        image = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame    
        draw = ImageDraw.Draw(image)
        draw.rectangle([(0,0),(50,50)],outline = 0)
        draw.rectangle([(55,0),(100,50)],fill = 0)
        draw.line([(0,0),(50,50)], fill = 0,width = 1)
        draw.line([(0,50),(50,0)], fill = 0,width = 1)
        draw.chord((10, 60, 50, 100), 0, 360, fill = 0)
        draw.ellipse((55, 60, 95, 100), outline = 0)
        draw.pieslice((55, 60, 95, 100), 90, 180, outline = 0)
        draw.pieslice((55, 60, 95, 100), 270, 360, fill = 0)
        draw.polygon([(110,0),(110,50),(150,25)],outline = 0)
        draw.polygon([(190,0),(190,50),(150,25)],fill = 0)
        draw.text((120, 60), 'e-Paper demo', font = font15, fill = 0)
        draw.text((110, 90), u'微雪电子', font = font24, fill = 0)
        # image = image.rotate(180) # rotate
        epd.display_fast(epd.getbuffer(image))
        time.sleep(2)
        
        # read bmp file 
        logging.info("2.read bmp file...")
        image = Image.open(os.path.join(picdir, '2in13.bmp'))
        epd.display_fast(epd.getbuffer(image))
        time.sleep(2)
        
        # read bmp file on window
        logging.info("3.read bmp file on window...")
        # epd.Clear(0xFF)
        image1 = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame
        bmp = Image.open(os.path.join(picdir, '100x100.bmp'))
        image1.paste(bmp, (2,2))    
        epd.display_fast(epd.getbuffer(image1))
        time.sleep(2)

    
    # # partial update
    logging.info("4.show time...")
    time_image = Image.new('1', (epd.height, epd.width), 255)
    time_draw = ImageDraw.Draw(time_image)
    epd.displayPartBaseImage(epd.getbuffer(time_image))
    num = 0
    while (True):
        # The method ensures that the rectangle is filled with the specified color...
        time_draw.rectangle((120, 80, 220, 105), fill = 255)
        time_draw.text((120, 80), time.strftime('%H:%M:%S'), font = font24, fill = 0)
        # send to display....
        epd.displayPartial(epd.getbuffer(time_image))
        num = num + 1
        if(num == 10):
            break
    
    logging.info("Clear...")
    epd.init()
    epd.Clear(0xFF)
    
    logging.info("Goto Sleep...")
    epd.sleep()
        
except IOError as e:
    logging.info(e)
    
except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    epd2in13_V4.epdconfig.module_exit(cleanup=True)
    exit()
