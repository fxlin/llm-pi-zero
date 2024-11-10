'''

EMU=1 python3 pi-demo.py

test rwkv inference engine
cf: https://pypi.org/project/rwkv/

speed benchmark res - see of file
full res: 
https://myuva.sharepoint.com/:x:/r/sites/XSEL-RWKV/Shared%20Documents/RWKV/results_rwkv.xlsx?d=wbf0bd61c5429469a8c039df4d8d4f46a&csf=1&web=1&e=0dyjUv
https://chatgpt.com/share/6722e34c-c920-8004-a2c2-0a99a4ecee00

'''
import sys, os, psutil
import time, copy

if os.environ.get("EMU") != '1':
    from rwkv.model import RWKV
    from rwkv.utils import PIPELINE, PIPELINE_ARGS

import threading

######## choice of models #############
# official models
model_path='/data/models/pi-deployment/RWKV-5-World-0.1B-v1-20230803-ctx4096'
# our own models
# model_path='/data/models/pi-deployment/01b-pre-x52-1455'
# model_path='/data/models/pi-deployment/04b-pre-x59-2405'  # <--- works for demo
# model_path='/data/models/pi-deployment/04b-pre-x59-860'  # <--- works for demo
#######################################

# run chat app on the inference engine (rwkv), check for sanity 
# xzl: use our own version of lm_eval, rwkv

home_dir = os.environ.get('HOME')
if home_dir == None: 
    home_dir = "/home/xl6yq"  # guessed
home_dir += "/"

sys.path.append(home_dir + 'workspace-rwkv/RWKV-LM')
if os.environ.get("RWKV_JIT_ON") != '0':
    os.environ["RWKV_JIT_ON"] = '1'

if os.environ.get('RWKV_CUDA_ON') != '0':
    os.environ["RWKV_CUDA_ON"] = '1' #default

if os.environ.get("MODEL_PATH"):
    model_path = os.environ.get("MODEL_PATH")

###########
# global vars, written by main thread (e.g. during model_gen()), 
# read by UI thread (e.g. system info renderer)
the_sys_msg = ""          # status msg 
the_tok_persec = 0.0       # token per sec
# XXX lock them, oh well....

###########
# epaper display (epd)
# 2in13_V4, 250x122
# https://www.waveshare.com/wiki/2.13inch_Touch_e-Paper_HAT_Manual
import logging
# from waveshare_epd import epd2in13_V4  # old lib, conflicts with TP_lib for GPIO pins
from TP_lib import epd2in13_V4, gt1151
from PIL import Image,ImageDraw,ImageFont
import random

class EInkDisplay:
    def __init__(self, picdir):
        # https://www.waveshare.com/wiki/2.13inch_Touch_e-Paper_HAT_Manual
        # screen dimension
        self.xres = 250
        self.yres = 122 

        # text area, dimension
        self.xmax = self.xres
        self.ymax = self.yres - 30  # Leave some space for the menu

        # text area margin, to the boundary 
        self.margin = 5 # px 

        # Set up fonts, idx=1 seems fixed width?
        self.font_tiny = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), size=12, index=0)
        self.font_text = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), size=15, index=0)
        self.font_title = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), size=24)

        # calculate row height ... 1.5x of text height
        left, top, right, bottom  = self.font_text.getbbox("A")
        self.text_height = bottom - top
        self.row_height = self.text_height * 3 / 2

        self.hard_reset()
        self.clear_text_area(True)
        # self.reset_position()

        # -- tok/s statistics -- #
        self.last_ts = time.time()
        self.token_cnt = 0  # token printed in the past period

        # Create a lock and condition for the display thread
        self.display_lock = threading.Lock()
        self.display_condition = threading.Condition(self.display_lock)
        self.display_buffer = None
        self.stop_thread = False

        # Create a condition for the system info update thread
        self.system_info_condition = threading.Condition()

        # Start the display update thread
        self.display_thread = threading.Thread(target=self.display_update_worker)
        self.display_thread.start()

        # Start the system info update thread. periodically poll cpu/mem/tmp/speed and render to the menu bar
        self.system_info_thread = threading.Thread(target=self.system_info_update_worker)
        self.system_info_thread.start()

        # some "marquee" visuals for the text msg displayed
        self.prev_sys_msg = None   # the last sys msg rendered
        self.sys_msg_offset = 0

    # def reset_position(self):
    #     self.y_position = self.margin
    #     self.x_position = self.margin

    def clear_text_area(self, update=False):
        # blank "base image" (background)
        # self.base_image = Image.new('1', (self.epd.height, self.epd.width), 255)  # 1-bit image (black and white)
        # self.base_draw = ImageDraw.Draw(self.base_image)
        # self.base_draw.text((10, 10), "Title", font=self.font_title, fill=0)  # Draw the title at the top

        # image as background, the image file orientation will affect the coordinate system
        self.base_image = Image.open(os.path.join(picdir, "2in13/Photo_2-3iconX.bmp")).rotate(-90, expand=True)

        self.base_draw = ImageDraw.Draw(self.base_image)
        # self.base_image.paste(newimage, (0, 0))

        # Display the base image 
        #   this is a "full" update  -- erase whole screen 
        if update:
            buffer = self.epd.getbuffer(self.base_image)
            self.epd.displayPartBaseImage(buffer)        

        # Create a larger text image for scrolling
        self.text_image_height = self.ymax * 20  # Set height to 20 times the e-ink display height
        self.text_image = Image.new('1', (self.xmax, self.text_image_height), 255)  # 1-bit image (black and white)
        self.text_draw = ImageDraw.Draw(self.text_image)
        self.scroll_offset = 0   # in pixel
        self.max_y_position = 0  # Track the maximum y_position that has ever been rendered

        # reset_position
        self.y_position = self.margin
        self.x_position = self.margin

    def hard_reset(self):
        # Initialize the e-ink display
        self.epd = epd2in13_V4.EPD()
        # self.epd.init()
        self.epd.init(self.epd.FULL_UPDATE)

        # clr: about 2.2 sec....
        start_time = time.time()  # Start measuring time
        self.epd.Clear(0xFF)
        end_time = time.time()  # End measuring time
        print(f"Clr time: {end_time - start_time:.4f} seconds")

    # NB: (some) tokens from rwkv contains a leading (?) space already
    def print_token_scroll(self, token):
        # statistics 
        self.token_cnt += 1
        elpased = time.time() - self.last_ts
        if elpased > 1: # count every 1 sec
            post_tks(self.token_cnt / elpased)
            self.token_cnt = 0
            self.last_ts = time.time()

        # preprocess... 
        token = token.replace('  ', ' ')  # two spaces as one
        # token = token.replace(' \n', ' ')  # space+newline as one space
        # token = token.replace('\n\n', '■')
        
        need_update = False

        # print(f"print_token_scroll() token: [{token}]")

        # text_width = self.font_text.getlength(token + " ")
        _, _, text_width, _ = self.font_text.getbbox(token)

        # start a new line 
        if self.x_position + text_width > self.xmax:
            self.x_position = self.margin
            self.y_position += self.row_height
            need_update = True

        # Hit the bottom of the text image (rare case); drop the top part of the text image
        if self.y_position + self.text_height > self.text_image_height:  
            self.x_position = self.margin
            self.y_position -= self.row_height
            # Shift the contents of the text_image up by row_height
            shifted_image = self.text_image.crop((0, self.row_height, self.xmax, self.text_image_height))
            self.text_image.paste(shifted_image, (0, 0))
            # Fill the region of the bottom row with white
            self.text_draw.rectangle((0, self.text_image_height - self.row_height, self.xmax, self.text_image_height), fill=255)

        # Draw the token on the text image
        self.text_draw.text((self.x_position, self.y_position), token, font=self.font_text, fill=0)

        # Update the x_position for the next word
        self.x_position += text_width

        # Update the maximum y_position (the maximum rendered text height, so far)
        self.max_y_position = max(self.max_y_position, self.y_position)

        # Update the scroll offset to keep at the bottom
        self.scroll_offset = max(0, self.y_position + self.text_height - self.ymax)

        # Update the base image by cropping the relevant part of the text image
        # t0=time.time()
        self.update_viewport(self.scroll_offset)
        # t1=time.time()
        # print(f"update_viewport time: {(t1-t0):.4f} seconds")

        # print("xpos:", self.x_position, "ypos:", self.y_position)

        '''
        # Update the base image by cropping the relevant part of the text image
        cropped_image = self.text_image.crop((0, self.scroll_offset, self.xmax, self.scroll_offset + self.ymax))
        self.base_image.paste(cropped_image, (0, 0))

        # Draw the vertical progress bar based on the scroll offset
        # progress = self.scroll_offset / (self.max_y_position - self.ymax)  # Calculate the scroll progress (0 to 1)
        # progress_bar_width = 3  # Width of the progress bar
        # progress_bar_height = int(self.ymax * progress)
        # self.base_draw.rectangle((self.xmax - progress_bar_width, 0, self.xmax, self.ymax), fill=255)  # Clear previous progress bar
        # self.base_draw.rectangle((self.xmax - progress_bar_width, 0, self.xmax, progress_bar_height), fill=0)  # Draw new progress bar

        # if need_update:
        if True:
            # print("try to update display...")
            with self.display_condition:
                # Update the e-ink display with the new token using partial update
                # start_time = time.time()  # Start measuring time
                # takes ~0.6 sec...
                # buffer = self.epd.getbuffer(self.base_image)
                # self.epd.displayPartial(buffer)
                # end_time = time.time()  # End measuring time
                # print(f"Token display time: {end_time - start_time:.4f} seconds")

                self.display_buffer = self.base_image.copy()
                self.display_condition.notify()
        '''

    # scroll_offset: pixel, if <0, will scroll to 0  
    def scroll_view(self, scroll_offset):
        # Set the new scroll offset
        self.scroll_offset = max(0, min(scroll_offset, self.text_image_height - self.ymax))
        # print(f"scroll_view got {scroll_offset}, set offset to: {self.scroll_offset}")
        # Update the base image by cropping the relevant part of the text image
        self.update_viewport(self.scroll_offset)

    def scroll_view_ratio(self, ratio):
        # Set the new scroll offset based on the ratio
        ratio = max(0.0, min(ratio, 1.0))
        scroll_offset = int((self.max_y_position - self.ymax) * ratio)
        self.scroll_view(scroll_offset)

    def update_viewport(self, scroll_offset):
        cropped_image = self.text_image.crop((0, scroll_offset, self.xmax, scroll_offset + self.ymax))
        self.base_image.paste(cropped_image, (0, 0))

        # Draw the vertical progress bar based on the scroll offset

        # we haven't rendered one screen worth of text ...
        if self.max_y_position == 0 or self.max_y_position <= self.ymax:
            progress = 0
        else: 
            progress = scroll_offset / (self.max_y_position - self.ymax)  # Calculate the scroll progress (0 to 1)
            # progress = scroll_offset / self.max_y_position  # Calculate the scroll progress (0 to 1)
        if progress > 1:  
            progress = 1 # is this right? TBD
        progress_bar_width = 3  # Width of the progress bar
        progress_bar_height = int(self.ymax * progress)     # calculated height of the progress bar (per progress
        self.base_draw.rectangle((self.xmax - progress_bar_width, 0, self.xmax, self.ymax), fill=255)  # Clear previous progress bar
        # print(f"scroll_offset {scroll_offset} max_y_position {self.max_y_position} ymax {self.ymax} progress: {progress}, height: {progress_bar_height}")
        self.base_draw.rectangle((self.xmax - progress_bar_width, 0, self.xmax, progress_bar_height), fill=0)  # Draw new progress bar

        # Copy the base_image buffer for the display thread
        with self.display_condition:
            self.display_buffer = self.base_image.copy()
            self.display_condition.notify()

    ################ the worker thread: for system info rendering  ################

    def system_info_update_worker(self):
        global the_tok_persec, the_sys_msg
        
        while not self.stop_thread:
            with self.system_info_condition:
                '''
                # Wait for notification or timeout
                if self.system_info_condition.wait(timeout=1):
                    # we have the lock, copy the global vars
                    tok_persec = the_tok_persec
                    sys_msg = copy.deepcopy(the_sys_msg)
                else: 
                    # we timeout, no new info, use the stale info 
                    #  (need to do this??) 
                    #   with self.system_info_condition:
                    # we dont have lock. need to grab
                    tok_persec = the_tok_persec
                    sys_msg = copy.deepcopy(the_sys_msg)
                '''
                # if we timeout, we may not have lock for the global vars
                # the intention is to use the stale values. (how?)
                # below goes w/o lock, for simplicity ... there's a race condition: 
                # (see above) TBD...
                self.system_info_condition.wait(timeout=1)
                tok_persec = the_tok_persec
                sys_msg = copy.deepcopy(the_sys_msg)
            # lock released, now draw
            self.draw_system_info(tok_persec, sys_msg)
            if self.stop_thread:
                break

    # called by the "system info" thread, to render the sys info on the menu bar. 
    # b/c the menu bar area is disjoint vs. the text area, no lock needed vs. update_viewport()
    def draw_system_info(self, token_per_sec, sys_msg):
        # print(f"draw sys info....{token_per_sec:.0f} tok/s, {sys_msg}")

        # Draw system information in a defined rectangle
        rect_x_start = 130  # Top-left x-coordinate
        rect_y_start = self.yres - 30  # Top-left y-coordinate
        rect_x_end = self.xres  # Bottom-right x-coordinate
        rect_y_end = self.yres  # Bottom-right y-coordinate

        # Number of characters that can fit in the system info area        
        left, top, right, bottom = self.font_tiny.getbbox("A")
        text_width = right - left
        info_text_bottom_len = (rect_x_end - rect_x_start) // text_width   # XXX why under-estimate?
        info_text_bottom_len += 4  # dirty fix....

        # Clear the previous system info area
        self.base_draw.rectangle((rect_x_start, rect_y_start, rect_x_end, rect_y_end), fill=255)

        # Row 0: Display the_tok_persec, CPU util, temperature, and memory usage
        tok_persec = f"{token_per_sec:.0f}".ljust(2)
        
        # Marquee effect for the system message (if it has not changed since last drawing)
        # Pad sys_msg with spaces to the length of info_text_bottom_len
        if len(sys_msg) < info_text_bottom_len:
            sys_msg = sys_msg.ljust(info_text_bottom_len)
        if self.prev_sys_msg and self.prev_sys_msg == sys_msg:  # sys_msg unchanged
            self.sys_msg_offset = (self.sys_msg_offset + 1) % len(sys_msg)
        else:
            self.sys_msg_offset = 0
        self.prev_sys_msg = sys_msg
        rotated_sys_msg = sys_msg[self.sys_msg_offset:] + sys_msg[:self.sys_msg_offset]
        info_text_bottom = rotated_sys_msg[:info_text_bottom_len]   # copy, truncated to fit the area
            
        cpu_usage = f"{psutil.cpu_percent():.0f}%".rjust(3)
        cpu_temp = f"{self.get_cpu_temperature():.0f}C".rjust(3)
        process = psutil.Process(os.getpid())
        mem_usage_str = self.format_memory_size(process.memory_info().rss).rjust(4)

        info_text_top = f"{tok_persec} tks {cpu_usage} {cpu_temp} {mem_usage_str}"
        self.base_draw.text((rect_x_start + 2, rect_y_start + 2), info_text_top, font=self.font_tiny, fill=0)

        # Row 1: Display the_sys_msg        
        self.base_draw.text((rect_x_start + 2, rect_y_start + 15), info_text_bottom, font=self.font_tiny, fill=0)

        # useful dbg info
        # print(f"draw sys info: {info_text_top}, {info_text_bottom}")

        # Copy the base_image buffer for the display thread
        with self.display_condition:
            self.display_buffer = self.base_image.copy()
            self.display_condition.notify()

        '''
        # Draw system information in a 2x2 grid, on bottom-right of the whole screen 
        grid_x_start = self.xres - 50  # Bottom-right corner grid starting position
        grid_y_start = self.yres - 30
        grid_width = 25
        grid_height = 15

        # Row 0, Col 0: CPU utilization (average over all cores)
        cpu_usage = int(psutil.cpu_percent())
        x_pos = grid_x_start
        y_pos = grid_y_start
        self.base_draw.rectangle((x_pos, y_pos, x_pos + grid_width, y_pos + grid_height), fill=255)  # Clear previous value
        self.base_draw.text((x_pos + 2, y_pos + 2), f"{cpu_usage}%", font=self.font_tiny, fill=0)

        # Row 0, Col 1: CPU temperature (e.g., 60C)
        cpu_temp = self.get_cpu_temperature()
        x_pos = grid_x_start + grid_width
        y_pos = grid_y_start
        self.base_draw.rectangle((x_pos, y_pos, x_pos + grid_width, y_pos + grid_height), fill=255)  # Clear previous value
        self.base_draw.text((x_pos + 2, y_pos + 2), f"{cpu_temp}C", font=self.font_tiny, fill=0)

        # Row 1, Col 0: Memory used by the current process (e.g., 300M or 1.5G)
        process = psutil.Process(os.getpid())
        mem_usage = process.memory_info().rss
        mem_usage_str = self.format_memory_size(mem_usage)
        x_pos = grid_x_start
        y_pos = grid_y_start + grid_height
        self.base_draw.rectangle((x_pos, y_pos, x_pos + grid_width, y_pos + grid_height), fill=255)  # Clear previous value
        self.base_draw.text((x_pos + 2, y_pos + 2), mem_usage_str, font=self.font_tiny, fill=0)

        # Row 1, Col 1: Blank (TBD)
        x_pos = grid_x_start + grid_width
        y_pos = grid_y_start + grid_height
        # self.base_draw.rectangle((x_pos, y_pos, x_pos + grid_width, y_pos + grid_height), fill=255)  # Clear previous value

        # Copy the base_image buffer for the display thread
        with self.display_condition:
            self.display_buffer = self.base_image.copy()
            self.display_condition.notify()
        '''

    # rapsi 
    def get_cpu_temperature(self):
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_str = f.readline().strip()
                temp_c = int(temp_str) / 1000.0  # Convert from millidegrees to degrees Celsius
                return round(temp_c)
        except FileNotFoundError:
            return 0

    def format_memory_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes // 1024}K"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes // (1024 * 1024)}M"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}G"

    ############ the worker thread: for refreshing the display (slow) ####################

    def display_update_worker(self):
        print("Display update worker started")
        while True:
            with self.display_condition:
                # Wait for a new buffer to be available
                while self.display_buffer is None and not self.stop_thread:
                    self.display_condition.wait()

                if self.stop_thread:
                    break

                # Get the buffer and clear it for the next update
                buffer_to_display = self.display_buffer
                self.display_buffer = None

            # print("render thr: displaying buffer...", end="")
            start_time = time.time()  # Start measuring time
            # Update the e-ink display with the new buffer using partial update
            # creates a byte array buffer that the e-ink driver can use to perform the partial update on the display
            buffer = self.epd.getbuffer(buffer_to_display)
            # self.epd.displayPartial(buffer)   # this is async in newer lib 
            self.epd.displayPartial_Wait(buffer)
            # end_time = time.time()  # End measuring time
            # print(f": {end_time - start_time:.2f} seconds")
    
    ############ stop all worker threads ####################
    def stop(self):
        # Stop the display update thread
        with self.display_condition:
            self.stop_thread = True
            self.display_condition.notify()
        self.display_thread.join()
        self.system_info_thread.join()

###############  the model invoker #####################

# ex prompt from paper: https://arxiv.org/pdf/2305.07759
prompt_list = [
    "\nUniversity of Virginia is",
    "\nWhat is the sum of 123 and 456",
    "\nElon Musk has",
    u"\n我们认为",
    # In a forest, there lived a cute rabbit named Tarou
    u"\nある森に、一匹のかわいいウサギが住んでいました",
    "\nAlice was so tired when she got back home so she went",
    # "\nLily likes cats and dogs. She asked her mom for a dog and her mom said no, so instead she asked",
    # "\nOnce upon a time there was a little girl named Lucy",
]

current_prompt = prompt_list[0]
pipeline=None

def model_load(model_path):
    global pipeline    
    print(f'Loading model - {model_path}')


    if os.environ["RWKV_CUDA_ON"] == '1':
        strategy='cuda fp16'
        # strategy='cuda fp16i8',
    else:    
        strategy='cpu fp16'
        # strategy='cpu fp32'
        # strategy='cpu fp16i8'

    t0 = time.time()
    model = RWKV(model=model_path, 
                strategy=strategy, 
                verbose=True)
    #              head_K=200, load_token_cls='/data/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/from-hpc/rwkv-823-cls.npy')

    pipeline = PIPELINE(model, "rwkv_vocab_v20230424")
    t1 = time.time()

    print(f"model build: {(t1-t0):.2f} sec")

# debubgging
def my_print(s):
    print(s, end='', flush=True)

def model_gen(prompt=None, print_prompt=False):
    global pipeline
    if not prompt:
        # ex prompt from paper: https://arxiv.org/pdf/2305.07759
        # ctx = "\nWhat is the sum of 123 and 456"
        # ctx = "\nElon Musk has"
        ctx = "\nUniversity of Virginia is"
        # ctx = u"\n我们认为"
        # ctx = "\nAlice was so tired when she got back home so she went"
        # ctx = "\nLily likes cats and dogs. She asked her mom for a dog and her mom said no, so instead she asked"
        # ctx = "\nOnce upon a time there was a little girl named Lucy"
        # print(ctx, end='')
    else:
        ctx = "\n" + prompt

    # def my_print(s):
    #     print(s, end='', flush=True)

    if print_prompt:
        eink_display.print_token_scroll(ctx.replace('\n', ''))

    args = PIPELINE_ARGS(temperature = 1.0, top_p = 0.7, top_k = 100, # top_k = 0 then ignore
                        alpha_frequency = 0.25,
                        alpha_presence = 0.25,
                        alpha_decay = 0.996, # gradually decay the penalty
                        token_ban = [0], # ban the generation of some tokens
                        token_stop = [], # stop generation whenever you see any token here
                        chunk_len = 256) # split input into chunks to save VRAM (shorter -> slower)
    
    t1 = time.time()
    TOKEN_CNT = 100 
    pipeline.generate(ctx, token_count=TOKEN_CNT, args=args, callback=eink_display.print_token_scroll)
    # pipeline.generate(ctx, token_count=TOKEN_CNT, args=args, callback=my_print)
    print('\n')
    t2 = time.time()
    print(f"exec {TOKEN_CNT} tokens in {(t2-t1):.2f} sec, {TOKEN_CNT/(t2-t1):.2f} tok/sec")

    eink_display.print_token_scroll('■                                ')
    time.sleep(1) # wait for the last screen to be rendered
    post_sys_msg(f"Done. {TOKEN_CNT}tk in {(t2-t1):.0f}s")

###############  touch device #####################
TOUCH_POLL_INTERVAL = 0.1  # 100 ms

flag_t = 1 
# touch dev polling thread, set a flag showing if a touch even has occurred
# xzl: NB: GT_Dev is a global obj. ::Touch is a flag set by this thread
# below polling???
# ::Touch will be examined by class code of GT1151::GT_scan()
def pthread_irq() :
    print("touch dev poll thread: running")    
    while flag_t == 1 :
    # xzl: non blocking? inefficient...     
        if(gt.digital_read(gt.INT) == 0) :    
            GT_Dev.Touch = 1
        else :
            GT_Dev.Touch = 0
        time.sleep(TOUCH_POLL_INTERVAL)     # 100 ms too much?
    print("thread:exit")

# transpose the touch x-y to be same as the display x-y
def transpose_touch_inplace(dev, xres):
    dev.X, dev.Y = dev.Y, dev.X         # transpose
    dev.X = [xres - x for x in dev.X]   # mirror

def transpose_touch(GT_dev, xres):
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
        
###############  start of rendering  #####################
# cf: https://www.waveshare.com/wiki/2.13inch_Touch_e-Paper_HAT_Manual#Touch_Driver (for C) 
picdir = './pic'  
eink_display = EInkDisplay(picdir)

def post_tks(tks):
    global the_tok_persec
    with eink_display.system_info_condition:
        the_tok_persec = tks
        eink_display.system_info_condition.notify()

def post_sys_msg(msg):
    global the_sys_msg
    with eink_display.system_info_condition:
        the_sys_msg = msg
        eink_display.system_info_condition.notify()
        
# load model, slow.. may be preloaded in the future        
if os.environ.get("EMU") != '1':
    post_sys_msg(f"Load {os.path.basename(model_path).replace('.pth', '')}... ")
    model_load(model_path)
    post_sys_msg(f"Model loaded.READY  ")
else: 
    post_sys_msg(f"EMU mode")

# test model....
# model_gen(print_prompt=True)
try: 
    # emu only 
    if os.environ.get("EMU") == '1':
        text = '''
        In the heart of a bustling city lies a quaint little café, hidden away from the busy streets and towering skyscrapers. The café, named "The Hidden Petal," has an atmosphere that radiates warmth and nostalgia, reminiscent of a time when life moved more slowly and people lingered over their coffee without a care in the world. The walls are adorned with vintage photographs, faded floral wallpaper, and shelves lined with books of all sorts, inviting patrons to stay and lose themselves in their pages. Small wooden tables are arranged with a view of the large window, which frames a charming garden filled with colorful flowers and gentle vines. The aroma of freshly baked croissants, ground coffee beans, and the distant sound of soft jazz music fills the air, creating an ambiance that makes one want to curl up with a book and forget the passage of time. The patrons, a mix of regulars and curious newcomers, seem to speak in hushed tones, as if not wanting to disturb the delicate tranquility of the place. Here, it feels as if the hustle and hurry of the world are miles away, and for a moment, time stands still, allowing one to simply be
        '''
        toks=15 # emulated tokens/sec
        for token in text.split():
            # eink_display.print_token(token)
            time.sleep(1.0/toks)
            eink_display.print_token_scroll(' ' + token)
            # no delay
        eink_display.print_token_scroll('■                                ')
        time.sleep(1) # wait for the last screen to be rendered

        # debug: scroll back 
        # for i in range(20):
        #     print("scrolling back...")
        #     eink_display.scroll_view(eink_display.scroll_offset - 10)
        #     time.sleep(1) 

        # for i in range(10):
        #     print("scrolling fwd...")
        #     eink_display.scroll_view_ratio(0.1 * i)
        #     time.sleep(1) 

    # else: # actual generation 
    #     model_gen()
    
    # --- geneation done, start the touch UI --- # 

    # GT_Development -- stores information about the current touch points
    gt = gt1151.GT1151()
    GT_Dev = gt1151.GT_Development()
    GT_Old = gt1151.GT_Development()

    gt.GT_Init()
    # touch dev polling thread
    t = threading.Thread(target = pthread_irq)
    t.setDaemon(True)
    t.start()

    # show the initial prompt
    current_prompt = random.choice(prompt_list)
    eink_display.print_token_scroll(current_prompt.replace('\n', ''))

    # the main UI loop, touch event handling
    while (1):
        time.sleep(TOUCH_POLL_INTERVAL)

        gt.GT_Scan(GT_Dev, GT_Old)
        # dedup, avoid exposing repeated events to app
        if(GT_Old.X[0] == GT_Dev.X[0] and GT_Old.Y[0] == GT_Dev.Y[0] and GT_Old.S[0] == GT_Dev.S[0]):
            continue

        # meaning touch event ready to be read out
        if(GT_Dev.TouchpointFlag):
            GT_Dev.TouchpointFlag = 0

            # not working
            # transpose_touch_inplace(GT_Dev, eink_display.xres)
            # transpose_touch_inplace(GT_Old, eink_display.xres)
            touchnew = transpose_touch(GT_Dev, eink_display.xres)
            touchold = transpose_touch(GT_Old, eink_display.xres)
            
            touchx,touchy,touchs = touchnew.X[0], touchnew.Y[0], touchnew.S[0]
            # print(f"touch ev touchx {touchx}, touchy {touchy}, touchs {touchs}")
            
            # Buttons for the UI
            # bottom-left corner, 35x35 button, "reload prompt"
            if touchx < 35 and touchy > eink_display.yres - 35:
                print("reload")
                eink_display.clear_text_area(False)
                current_prompt = random.choice(prompt_list)
                eink_display.print_token_scroll(current_prompt.replace('\n', ''))
            # center x,y ~= 80,120
            elif touchx > 70 and touchx < 90 and touchy > 110:
                # print("gen")
                post_sys_msg(f"Generating...")
                model_gen(current_prompt)
            # x,y ~= 120,120, clear
            elif touchx > 110 and touchx < 130 and touchy > 110:
                print("quit")
                post_sys_msg("Quitting...")
                eink_display.stop()
                flag_t = 0
                eink_display.epd.Clear(0xFF)
                eink_display.epd.sleep()
                time.sleep(1)
                t.join()
                epd2in13_V4.epdconfig.module_exit()
                exit()

            # scroll controls 
            # top-right corner
            elif touchx > eink_display.yres *7//8 and touchy < eink_display.yres // 2:
                if touchs <= 50: # light touch
                    # print("scrolling up...")
                    eink_display.scroll_view(eink_display.scroll_offset - 10)
                else: 
                    # print("scrolling to top...")
                    eink_display.scroll_view_ratio(0)
            # bottom-right corner
            elif touchx > eink_display.yres *7//8 and touchy > eink_display.yres // 2:
                if touchs <= 50:
                    # print("scrolling down...")
                    eink_display.scroll_view(eink_display.scroll_offset + 10)
                else:
                    # print("scrolling to bottom...")
                    eink_display.scroll_view_ratio(1.0)
            

    eink_display.stop()
    eink_display.epd.sleep()
    # dbg: Save the text image as a bmp file
    # eink_display.text_image.save("text.bmp")
    # eink_display.base_image.save("base.bmp")
    sys.exit(0)
            
except IOError as e:
    logging.info(e)

except KeyboardInterrupt:    
    logging.info("ctrl + c:")
    eink_display.stop()     # render thread to quit 
    flag_t = 0          # touch thread to quit 
    eink_display.epd.sleep()
    time.sleep(1)
    t.join()           # wait for touch thread to quit
    eink_display.epd.Dev_exit()
    exit()


eink_display.epd.sleep()
eink_display.stop()


