'''
test rwkv inference engine
cf: https://pypi.org/project/rwkv/

speed benchmark res - see of file
full res: 
https://myuva.sharepoint.com/:x:/r/sites/XSEL-RWKV/Shared%20Documents/RWKV/results_rwkv.xlsx?d=wbf0bd61c5429469a8c039df4d8d4f46a&csf=1&web=1&e=0dyjUv

https://chatgpt.com/share/6722e34c-c920-8004-a2c2-0a99a4ecee00

'''
import sys, os
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
        self.xres = 250
        self.yres = 122 

        # text area
        self.xmax = self.xres
        self.ymax = self.yres - 30  # Leave some space for the menu

        # text area margin, to the boundary 
        self.margin = 5 # px 

        # Set up fonts, idx=1 seems fixed width?
        # self.font_text = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), size=12, index=1)
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

        print(f"print_token_scroll() token: [{token}]")

        # text_width = self.font_text.getlength(token + " ")
        _, _, text_width, _ = self.font_text.getbbox(token)

        if self.x_position + text_width > self.xmax:
            self.x_position = self.margin
            self.y_position += self.row_height
            need_update = True

        if self.y_position + self.text_height > self.ymax:    # hit the bottom of the text area
            # self.reset_position()
            self.x_position = self.margin   
            self.y_position -= self.row_height
            # Shift the contents of the base_image up by row_height
            shifted_image = self.base_image.crop((0, self.row_height, self.xmax, self.ymax))
            self.base_image.paste(shifted_image, (0, 0))
            # Fill the region of the bottom row with white
            self.base_draw.rectangle((0, self.ymax - self.row_height, self.xmax, self.ymax), fill=255)
            self.base_draw = ImageDraw.Draw(self.base_image)
            need_update = True

        # Draw the token on the base image
        self.base_draw.text((self.x_position, self.y_position), token, font=self.font_text, fill=0)

        # Update the x_position for the next word
        self.x_position += text_width

        # print("xpos:", self.x_position, "ypos:", self.y_position)

        if need_update:
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

            # print("Displaying buffer...")
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

    # print token, update per line (roughly)
    # clear the page when full, and restart from top
    # NB: token from rwkv contains a leading (?) space already
    def print_token_cleanpage(self, token):
        # if "\n" in token:
        #     breakpoint()
        # if token == "\n":
        #     self.y_position += 20  # Move to next line
        #     self.x_position = 10

        # preprocess... 
        token = token.replace('\n\n', '■')
        
        need_update = False

        # text_width = self.font_text.getlength(token + " ")
        _, _, text_width_nospace, _ = self.font_text.getbbox(token)
        _, _, text_width, _ = self.font_text.getbbox(token + " ")

        if self.x_position + text_width_nospace > self.xmax:
            self.y_position += self.row_height
            self.x_position = self.margin
            need_update = True       # a new line starts, refresh

        if self.y_position + self.text_height > self.ymax:
            self.clear_text_area()
            self.reset_position()
            need_update = True

        # Draw the token on the base image
        self.base_draw.text((self.x_position, self.y_position), token, font=self.font_text, fill=0)

        # Update the x_position for the next word
        self.x_position += text_width

        if need_update:  # async, notify the display thread ... 
            # Update the e-ink display with the new token using partial update
            # start_time = time.time()  # Start measuring time
            # takes ~0.6 sec...
            buffer = self.epd.getbuffer(self.base_image)
            self.epd.displayPartial(buffer)
            # end_time = time.time()  # End measuring time
            # print(f"Token display time: {end_time - start_time:.4f} seconds")

picdir = './pic'  
eink_display = EInkDisplay(picdir)

# emulate the chat app...
if 0:
    text = '''
    In the heart of a bustling city lies a quaint little café, hidden away from the busy streets and towering skyscrapers. The café, named "The Hidden Petal," has an atmosphere that radiates warmth and nostalgia, reminiscent of a time when life moved more slowly and people lingered over their coffee without a care in the world. The walls are adorned with vintage photographs, faded floral wallpaper, and shelves lined with books of all sorts, inviting patrons to stay and lose themselves in their pages. Small wooden tables are arranged with a view of the large window, which frames a charming garden filled with colorful flowers and gentle vines. The aroma of freshly baked croissants, ground coffee beans, and the distant sound of soft jazz music fills the air, creating an ambiance that makes one want to curl up with a book and forget the passage of time. The patrons, a mix of regulars and curious newcomers, seem to speak in hushed tones, as if not wanting to disturb the delicate tranquility of the place. Here, it feels as if the hustle and hurry of the world are miles away, and for a moment, time stands still, allowing one to simply be
    '''
    for token in text.split():
        # eink_display.print_token(token)
        eink_display.print_token_scroll(' ' + token)
        # no delay
    eink_display.print_token_scroll('■                                ')
    eink_display.stop()        
    eink_display.epd.sleep()
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
eink_display.epd.sleep()
eink_display.stop()
