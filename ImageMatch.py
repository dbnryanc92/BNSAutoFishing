# Window capturing / template matching
import win32gui
import win32con
import win32ui
from ctypes import windll
import numpy as np
from cv2 import cv2

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