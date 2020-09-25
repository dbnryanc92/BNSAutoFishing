'''
劍靈自動釣魚程式 - 玉蜂 2020
--------
  Title: BNS Auto Fishing Program
 Author: dbnryanc92 (玉蜂)
Version: 1.0
'''

# Image capture / match
import numpy as np
import win32gui
import win32con
import win32ui
from ctypes import windll
from cv2 import cv2
# Load config
import configparser
# Functionality
from time import sleep
from os import path, system
from threading import Thread
# UI
import logging
from rich.logging import RichHandler
from rich.console import Console
from rich.markdown import Markdown

# Variables
hwndThreads = {}

# Constants
programName = "劍靈自動釣魚程式v1.0"
clientName = "劍靈"
configFile = "config.ini"
dragKey = "F"
# VK_Key_Code : http://www.kbdedit.com/manual/low_level_vk_list.html
VK_Keys = {'1': 0x31, '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, 'F': 0x46}

# Default configuration values
showDetails = False
baitKey = "5"
captureImg = "fishing.png"
interval = 1
dragDelay = 0.5
threshold = 0.8
enableStopCheck = False
stopCheckInterval = 40

def validBaitKey(key):
    validList = ["5", "6", "7", "8"]
    if key in validList:
        return key
    return baitKey

# Window capturing / template matching
def getWindowSize(hwnd):
    # Get target window size
    try:
        left, top, right, bot = win32gui.GetWindowRect(hwnd)
        x0, y0, x1, y1 = win32gui.GetClientRect(hwnd)
    except:
        return (-1, -1, -1, -1, -1, -1)
    width = right - left
    height = bot - top
    x = x1 - x0
    y = y1 - y0
    # print("Position:", (left, top, width, height), "Size:", (x, y))
    return (left, top, width, height, x, y)

def getWindowImg(hwnd):
    # Check whether window is minimized
    minimized = win32gui.IsIconic(hwnd)
    if minimized == 1:
        # Cancel max/minimize animation
        win32gui.SystemParametersInfo(win32con.SPI_SETANIMATION, 0)
        # Set window as transparent
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 0, win32con.LWA_ALPHA)
        # Restore window from minimized state
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        # Put the window on bottom layer
        left, top, width, height, x, y = getWindowSize(hwnd)
        win32gui.SetWindowPos(hwnd, win32con.HWND_BOTTOM, left, top, width, height, win32con.SWP_NOACTIVATE)
        # Restore transparent and animation settings
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
        win32gui.SystemParametersInfo(win32con.SPI_SETANIMATION, 1)

    # Capture
    left, top, width, height, x, y = getWindowSize(hwnd)
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, x, y)
    saveDC.SelectObject(saveBitMap)
    windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 1)
    signedIntsArray = saveBitMap.GetBitmapBits(True)
    img = np.frombuffer(signedIntsArray, dtype='uint8')
    img.shape = (y, x, 4)

    # Debug
    # print("saveBitMap.GetInfo():", saveBitMap.GetInfo())
    # saveBitMap.SaveBitmapFile(saveDC, "debug.png")
    # print(img)

    # Release memory
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)
    win32gui.DeleteObject(saveBitMap.GetHandle())

    return img

def imageMatch(hwnd, image):
    # Match screenshot with template
    img = getWindowImg(hwnd)
    img_rgb = np.array(img)
    img_gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
    template = cv2.imread(image, 0)
    template.shape[::-1]
    res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
    # Match rate
    return cv2.minMaxLoc(res)[1]

# Client actions
def sendBait(hwnd):
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_Keys[baitKey], 0)
    sleep(0.1)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, VK_Keys[baitKey], 0)

def sendDrag(hwnd):
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_Keys[dragKey], 0)
    sleep(0.1)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, VK_Keys[dragKey], 0)

# Get client hwnds
def matchWindowHwnd(pattern):
    # Load all window hwnd into list
    windowList = []
    win32gui.EnumWindows(lambda hWnd, param: param.append(hWnd), windowList)
    # Find matching window hwnd
    matchList = []
    for window in windowList:
        if pattern == win32gui.GetWindowText(window): # Exact match
        #if pattern in win32gui.GetWindowText(window): # Contain
            matchList.append(window)
    return matchList

def scanWindowHwnd(pattern):
    # Clear stopped clients
    for hwnd in list(hwndThreads.keys()):
        if hwndThreads[hwnd]["status"] == -1:
            # del hwndThreads[hwnd]
            hwndThreads[hwnd]["status"] = 0
            log.info("劍靈客戶端[{}]: 視窗錯誤或已關閉，已停止搜尋".format(hwnd))

    # Find new clients
    matchList = matchWindowHwnd(pattern)
    for hwnd in matchList:
        # Create & initialize threadObj if doesn't exist
        if hwnd not in hwndThreads:
            hwndThreads[hwnd] = {}
            hwndThreads[hwnd]["status"] = 0
            hwndThreads[hwnd]["countDragSuccess"] = 0
            hwndThreads[hwnd]["countNotMatch"] = 0

        # Start thread
        if hwndThreads[hwnd]["status"] == 0:
            hwndThreads[hwnd]["status"] = 1
            hwndThreads[hwnd]["thread"] = Thread(target=fishing, args=(hwnd,))
            hwndThreads[hwnd]["thread"].start()
            log.info("劍靈客戶端[{}]: 已被偵測，開始搜尋上釣按鈕".format(hwnd))

def countActiveHwnd(hwndObj):
    count = 0
    for hwnd in list(hwndObj.keys()):
        if hwndThreads[hwnd]["status"] == 1:
            count += 1
    return count

# Fishing loop
def fishing(hwnd):
    while 1:
        try:
            matchRate = imageMatch(hwnd, captureImg)
            if matchRate < threshold:
                hwndThreads[hwnd]["countNotMatch"] += 1
                # log.debug("劍靈客戶端[{}]: 未發現上釣按鈕[{}]".format(hwnd, matchRate))
                log.debug("劍靈客戶端[{}]: 未發現上釣按鈕".format(hwnd))

                # Stop check
                if enableStopCheck:
                    if hwndThreads[hwnd]["countNotMatch"] >= stopCheckFreq:
                        sendBait(hwnd)
                        hwndThreads[hwnd]["countNotMatch"] = 0
                        log.info("劍靈客戶端[{}]: 發現釣魚狀態已停止，已重新下魚餌".format(hwnd))
            else:
                # log.debug("劍靈客戶端[{}]: 已發現上釣按鈕[{}]".format(hwnd, matchRate))
                log.debug("劍靈客戶端[{}]: 已發現上釣按鈕".format(hwnd))

                # Delay & drag
                sleep(dragDelay)
                sendDrag(hwnd)
                hwndThreads[hwnd]["countNotMatch"] = 0
                hwndThreads[hwnd]["countDragSuccess"] += 1
                log.info("劍靈客戶端[{}]: 釣魚成功 (成功次數: {})".format(hwnd, hwndThreads[hwnd]["countDragSuccess"]))

                # Wait and send bait
                sleep(1)
                sendBait(hwnd)

            # Delay for next loop
            sleep(interval)
        except:
            break
    hwndThreads[hwnd]["status"] = -1
    return

# Main program
if __name__ == "__main__":
    # Set up console
    system("title "+programName)

    # Set up logger
    FORMAT = "%(message)s"
    handler = RichHandler()
    handler._log_render.show_path = False
    logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[handler])
    log = logging.getLogger("rich")

    # Title
    console = Console()
    title = [
        "# 劍靈自動釣魚程式v1.0 - 玉蜂 2020",
        "## 使用前須知",
        "- 使用方法時請先閱讀README檔案，初次使用前須進行初期設定",
        "- 此程式只供測試用，且可能違反劍靈用戶協議，本人不負任何責任，請自行衡量",
        "- 開始釣魚吧！"
    ]
    for line in title:
        console.print(Markdown(line))
    print()

    # Check if running as admin
    isAdmin = windll.shell32.IsUserAnAdmin() != 0
    if(not isAdmin):
        log.fatal("請以系統管理員身份執行此程式")
    
    else:
        # Initialization
        if(path.exists(configFile)):
            # Load from custom configuration file
            config = configparser.ConfigParser()
            config.read(configFile)
            showDetails = config.getboolean('UserPreference', 'showDetails', fallback=showDetails)
            baitKey = validBaitKey(config.get('UserPreference', 'baitKey', fallback=baitKey))
            captureImg = config.get('UserPreference', 'captureImg', fallback=captureImg)
            interval = config.getfloat('UserPreference', 'interval', fallback=interval)
            dragDelay = config.getfloat('UserPreference', 'dragDelay', fallback=dragDelay)
            threshold = config.getfloat('UserPreference', 'threshold', fallback=threshold)
            enableStopCheck = config.getboolean('UserPreference', 'enableStopCheck', fallback=enableStopCheck)
            stopCheckInterval = config.getint('UserPreference', 'stopCheckInterval', fallback=stopCheckInterval)
            log.info("已從{}中讀取自定義配置".format(configFile))
        else:
            log.info("找不到{}，已載入預設配置".format(configFile))
            
        # Change debug logging settings
        if not showDetails:
            logging.getLogger().setLevel(logging.INFO)
        
        # Calculated configuration
        stopCheckFreq = int(round(stopCheckInterval / interval))

        # Show all config values
        log.debug(" ***** 釣魚程式參數 *****")
        log.debug(" * 魚餌位置 = {}".format(baitKey))
        log.debug(" * 釣魚按鈕截圖名稱 = {}".format(captureImg))
        log.debug(" * 刷新時間間距 = {}秒".format(interval))
        log.debug(" * 收竿延遲 = {}秒".format(dragDelay))
        log.debug(" * 最低近似度 = {}".format(threshold))
        log.debug(" * 啟動釣魚狀態檢查 = {}".format(enableStopCheck))
        log.debug(" * 釣魚狀態檢查間距 = {}秒".format(stopCheckInterval))
        # log.debug(" * 釣魚狀態檢查頻率 = {}".format(stopCheckFreq))
        log.debug(" ************************")
        
        system("pause")

        # Main operating loop
        while path.exists(captureImg):
            # Scan for new client hwnds to start fishing
            scanWindowHwnd(clientName)

            # If no active clients
            if(countActiveHwnd(hwndThreads) <= 0):
                log.info("未找到劍靈客戶端")

            # Debug usage
            #print(hwndThreads)

            # Delay for next leep
            sleep(interval)
        
        # Capture image not found
        log.fatal("找不到釣魚按鈕截圖，請檢查檔案名稱")
    
    # End program
    print()
    system("pause")