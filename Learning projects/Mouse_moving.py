

import pyautogui as pag
import random
import time

# Safety: move mouse to top-left corner to stop
pag.FAILSAFE = True  

while True:
    x = random.randint(900, 1500)
    y = random.randint(400, 800)

    duration = random.uniform(0.2, 0.8)  # random speed

    pag.moveTo(x, y, duration)

    time.sleep(random.uniform(1, 3))  # random pause


