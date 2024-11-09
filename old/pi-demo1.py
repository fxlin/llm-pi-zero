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
import time

from rwkv.model import RWKV
from rwkv.utils import PIPELINE, PIPELINE_ARGS
from rwkv.arm_plat import is_amd_cpu
import threading


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

###########
# epaper display (epd)
# 2in13_V4, 250x122
# https://www.waveshare.com/wiki/2.13inch_Touch_e-Paper_HAT_Manual
import logging
from waveshare_epd import epd2in13_V4
from PIL import Image,ImageDraw,ImageFont

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
        left, top, right, bottom,  = self.font_text.getbbox("A")
        self.text_height = bottom - top
        self.row_height = self.text_height * 3 / 2

        self.hard_reset()
        self.clear_text_area(True)
        self.reset_position()

        # Create a lock and condition for the display thread
        self.display_lock = threading.Lock()
        self.display_condition = threading.Condition(self.display_lock)
        self.display_buffer = None
        self.stop_thread = False

        # Start the display update thread
        self.display_thread = threading.Thread(target=self.display_update_worker)
        self.display_thread.start()

    def reset_position(self):
        self.y_position = self.margin
        self.x_position = self.margin

    def clear_text_area(self, update=False):
        # blank "base image" (background)
        # self.base_image = Image.new('1', (self.epd.height, self.epd.width), 255)  # 1-bit image (black and white)
        # self.base_draw = ImageDraw.Draw(self.base_image)
        # self.base_draw.text((10, 10), "Title", font=self.font_title, fill=0)  # Draw the title at the top

        # image as background, the image file orientation will affect the coordinate system
        self.base_image = Image.open(os.path.join(picdir, "2in13/Photo_2.bmp")).rotate(-90, expand=True)

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

    def hard_reset(self):
        # Initialize the e-ink display
        self.epd = epd2in13_V4.EPD()
        self.epd.init()

        # clr: about 2.2 sec....
        start_time = time.time()  # Start measuring time
        self.epd.Clear(0xFF)
        end_time = time.time()  # End measuring time
        print(f"Clr time: {end_time - start_time:.4f} seconds")

    # NB: (some) tokens from rwkv contains a leading (?) space already
    def print_token_scroll(self, token):
        # preprocess... 
        token = token.replace('  ', ' ')  # two spaces as one
        token = token.replace(' \n', ' ')  # space+newline as one space
        token = token.replace('\n\n', '■')
        
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
        self.update_viewport(self.scroll_offset)

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

    # scroll_offset: pixel 
    def scroll_view(self, scroll_offset):
        # Set the new scroll offset
        self.scroll_offset = max(0, min(scroll_offset, self.text_image_height - self.ymax))
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
        if progress > 1:   # also means we haven't rendered one screen worth of text
            progress = 0
        progress_bar_width = 3  # Width of the progress bar
        progress_bar_height = int(self.ymax * progress)     # calculated height of the progress bar (per progress
        self.base_draw.rectangle((self.xmax - progress_bar_width, 0, self.xmax, self.ymax), fill=255)  # Clear previous progress bar
        print(f"scroll_offset {scroll_offset} max_y_position {self.max_y_position} ymax {self.ymax} progress: {progress}, height: {progress_bar_height}")
        self.base_draw.rectangle((self.xmax - progress_bar_width, 0, self.xmax, progress_bar_height), fill=0)  # Draw new progress bar

        # Draw CPU utilization for cores 0-3 in a 2x2 grid
        cpu_usages = psutil.cpu_percent(percpu=True)[:4]
        grid_x_start = self.xres - 30  # Bottom-right corner grid starting position
        grid_y_start = self.yres - 30
        grid_width = 15
        grid_height = 15

        for i in range(2):
            for j in range(2):
                core_index = i * 2 + j
                usage_text = f"{int(cpu_usages[core_index])}"  # Only print the integer usage value (0-99)
                x_pos = grid_x_start + j * grid_width
                y_pos = grid_y_start + i * grid_height
                self.base_draw.rectangle((x_pos, y_pos, x_pos + grid_width, y_pos + grid_height), fill=255)  # Clear previous value
                self.base_draw.text((x_pos + 2, y_pos + 2), usage_text, font=self.font_tiny, fill=0)  # Draw CPU usage

        # Copy the base_image buffer for the display thread
        with self.display_condition:
            self.display_buffer = self.base_image.copy()
            self.display_condition.notify()

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

            print("Displaying buffer...")
            # Update the e-ink display with the new buffer using partial update
            # creates a byte array buffer that the e-ink driver can use to perform the partial update on the display
            buffer = self.epd.getbuffer(buffer_to_display)
            self.epd.displayPartial(buffer)
            # print("done")

    def stop(self):
        # Stop the display update thread
        with self.display_condition:
            self.stop_thread = True
            self.display_condition.notify()
        self.display_thread.join()

picdir = './pic'  
eink_display = EInkDisplay(picdir)

# emulate the chat app...
# if 1:
if os.environ.get("EMU") == '1':
    text = '''
    In the heart of a bustling city lies a quaint little café, hidden away from the busy streets and towering skyscrapers. The café, named "The Hidden Petal," has an atmosphere that radiates warmth and nostalgia, reminiscent of a time when life moved more slowly and people lingered over their coffee without a care in the world. The walls are adorned with vintage photographs, faded floral wallpaper, and shelves lined with books of all sorts, inviting patrons to stay and lose themselves in their pages. Small wooden tables are arranged with a view of the large window, which frames a charming garden filled with colorful flowers and gentle vines. The aroma of freshly baked croissants, ground coffee beans, and the distant sound of soft jazz music fills the air, creating an ambiance that makes one want to curl up with a book and forget the passage of time. The patrons, a mix of regulars and curious newcomers, seem to speak in hushed tones, as if not wanting to disturb the delicate tranquility of the place. Here, it feels as if the hustle and hurry of the world are miles away, and for a moment, time stands still, allowing one to simply be
    '''
    for token in text.split():
        # eink_display.print_token(token)
        eink_display.print_token_scroll(' ' + token)
        # no delay
    eink_display.print_token_scroll('■                                ')
    time.sleep(1) # wait for the last screen to be rendered

    # debug: scroll back 
    # for i in range(20):
    #     print("scrolling back...")
    #     eink_display.scroll_view(eink_display.scroll_offset - 10)
    #     time.sleep(1) 

    for i in range(10):
        print("scrolling fwd...")
        eink_display.scroll_view_ratio(0.1 * i)
        time.sleep(1) 

    eink_display.stop()        
    eink_display.epd.sleep()    
    # dbg: Save the text image as a bmp file
    # eink_display.text_image.save("text.bmp")
    # eink_display.base_image.save("base.bmp")
    sys.exit(0)
###### 

# rva
# model_path='/scratch/xl6yq/data/models/RWKV-5-World-0.1B-v1-20230803-ctx4096'

# official
# model_path='/data/models/RWKV-5-World-0.1B-v1-20230803-ctx4096' # official, NB it's v1
# model_path='/data/models/pi-deployment/RWKV-5-World-0.4B-v2-20231113-ctx4096'

# .1B 16x, deeply compressed 
# model_path='/data/models/01b-pre-x59-16x-901'

#v5.9
# model_path='/data-xsel02/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/rwkv-init'   #unmodified model,  pretrained by us 
# model_path='/data-xsel02/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01B-relu-diag-pretrain/rwkv-25'
# model_path='/data-xsel02/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01B-relu-diag-pretrain/rwkv-35'

# model_path='/data-xsel02/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/run1/rwkv-7'  # old
# model_path='/data-xsel02/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/rwkv-init'
# model_path='/data-xsel02/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/run2/rwkv-24'  #Only head.l1 tuned

# model_path='/data/models/0.1b-pre-x59-16x-1451'
# model_path='/data/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-pretrain-x59/from-hpc/rwkv-976'

model_path='/data/models/pi-deployment/01b-pre-x52-1455'
# model_path='/data/models/pi-deployment/01b-pre-x58-512'

# model_path='/data/models/pi-deployment/01b-pre-x52-1455_fp16i8'     # can directly load quant model like this. cf "conversion" below
# model_path='/data/models/pi-deployment/01b-pre-x59-976'
# model_path='/data/models/pi-deployment/04b-tunefull-x58-562'
# model_path='/data/models/pi-deployment/04b-pre-x59-2405'  # <--- works for demo

# model_path='/data/models/rwkv-04b-pre-x59-860'

# model_path='/data/models/pi-deployment/1b5-pre-x59-929'
# model_path='/data/models/pi-deployment/01b-pre-x59-CLS-TEST'

# #Only head.l1 tuned. KL loss (good
# model_path='/data/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/run3-KL-loss/rwkv-43'

#model_path='/data/home/bfr4xr/RWKV-LM/RWKV-v5/out/01b-cls-mine/run3-KL-loss/rwkv-43'
#model_path='/data/home/bfr4xr/RWKV-LM/RWKV-v5/out/01b-pre-x59-8x-cls/from-hpc/rwkv-1366'
#model_path='/data/home/bfr4xr/RWKV-LM/RWKV-v5/out/01b-pre-x59-8x-cls/from-hpc/0.1b-official'
# only head.l1fc1, head.l1fc2 (MLP) trained. KL loss
#   very bad
# model_path='/data/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/run5-KL-loss-MLP-KaimingInit/rwkv-230'
#   very bad
# model_path='/data/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/run4-KL-loss-MLP/rwkv-40'


print(f'Loading model - {model_path}')

# xzl: for strategy, cf: https://pypi.org/project/rwkv/ for more ex
#
# Strategy Examples: (device = cpu/cuda/cuda:0/cuda:1/...)
# 'cpu fp32' = all layers cpu fp32
# 'cuda fp16' = all layers cuda fp16
# 'cuda fp16i8' = all layers cuda fp16 with int8 quantization
# 'cuda fp16i8 *10 -> cpu fp32' = first 10 layers cuda fp16i8, then cpu fp32 (increase 10 for better speed)
# 'cuda:0 fp16 *10 -> cuda:1 fp16 *8 -> cpu fp32' = first 10 layers cuda:0 fp16, then 8 layers cuda:1 fp16, then cpu fp32
#
# Use '+' for STREAM mode, which can save VRAM too, and it is sometimes faster
# 'cuda fp16i8 *10+' = first 10 layers cuda fp16i8, then fp16i8 stream the rest to it (increase 10 for better speed)
# 'cuda fp16i8 *0+ -> cpu fp32 *1' = stream all layers cuda fp16i8, last 1 layer [ln_out+head] cpu fp32

if os.environ["RWKV_CUDA_ON"] == '1':
    strategy='cuda fp16'
    # strategy='cuda fp16i8',
else:
    if is_amd_cpu():
        strategy='cpu fp32'  # amd cpu lacks hard fp16...
    else:
        strategy='cpu fp16'
    # strategy='cpu fp16i8'

# use below to quantize model & save
if False: 
    strategy_token = strategy.split()[1]
    basename, extension = os.path.splitext(os.path.basename(model_path))
    save_path = os.path.join(os.path.dirname(model_path), f"{basename}_{strategy_token}{extension}")
    print(f'Save path: {save_path}')
    model = RWKV(model=model_path, strategy=strategy, verbose=True, convert_and_save_and_exit=save_path)
    sys.exit(0)

t0 = time.time()
model = RWKV(model=model_path, 
             strategy=strategy, 
             verbose=True)
#              head_K=200, load_token_cls='/data/home/xl6yq/workspace-rwkv/RWKV-LM/RWKV-v5/out/01b-cls-mine/from-hpc/rwkv-823-cls.npy')

pipeline = PIPELINE(model, "rwkv_vocab_v20230424")

# ex prompt from paper: https://arxiv.org/pdf/2305.07759
# ctx = "\nWhat is the sum of 123 and 456"
# ctx = "\nElon Musk has"
ctx = "\nUniversity of Virginia is"
# ctx = u"\n我们认为"
# ctx = "\nAlice was so tired when she got back home so she went"
# ctx = "\nLily likes cats and dogs. She asked her mom for a dog and her mom said no, so instead she asked"
# ctx = "\nOnce upon a time there was a little girl named Lucy"
print(ctx, end='')

def my_print(s):
    print(s, end='', flush=True)

eink_display.print_token_scroll(ctx.replace('\n', ''))

t1 = time.time()

# For alpha_frequency and alpha_presence, see "Frequency and presence penalties":
# https://platform.openai.com/docs/api-reference/parameter-details

args = PIPELINE_ARGS(temperature = 1.0, top_p = 0.7, top_k = 100, # top_k = 0 then ignore
                     alpha_frequency = 0.25,
                     alpha_presence = 0.25,
                     alpha_decay = 0.996, # gradually decay the penalty
                     token_ban = [0], # ban the generation of some tokens
                     token_stop = [], # stop generation whenever you see any token here
                     chunk_len = 256) # split input into chunks to save VRAM (shorter -> slower)

TOKEN_CNT = 100 
pipeline.generate(ctx, token_count=TOKEN_CNT, args=args, callback=eink_display.print_token_scroll)
print('\n')
t2 = time.time()
print(f"model build: {(t1-t0):.2f} sec, exec {TOKEN_CNT} tokens in {(t2-t1):.2f} sec, {TOKEN_CNT/(t2-t1):.2f} tok/sec")

eink_display.print_token_scroll('■                                ')
time.sleep(1) # wait for the last screen to be rendered

eink_display.epd.sleep()
eink_display.stop()
