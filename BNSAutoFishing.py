'''
劍靈自動釣魚程式 - 玉蜂 2020
--------
  Title: BNS Auto Fishing
 Author: dbnryanc92 (玉蜂)
Version: 2.2
'''

# Image capture / match
import win32gui
import win32con
import win32ui
from ctypes import windll
import numpy as np
from cv2 import cv2
# Load config
import configparser
# Functionality
import sys
from time import sleep
from datetime import datetime
from os import path, system
from threading import Thread
# Classes / method modules
from ImageMatch import imageMatch
# GUI
from PyQt5 import QtCore, QtGui, QtWidgets
import gui

# Variables
isAdmin = None
cfg = None
window = None
mainSwitch = False
hwndThreads = {}

# Constants
programName = "劍靈自動釣魚程式"
programVersion = "v2.2"
clientName = "劍靈"
configFile = "config.ini"
dragKey = "F"
# VK_Key_Code : http://www.kbdedit.com/manual/low_level_vk_list.html
VK_Keys = {'1': 0x31, '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, 'F': 0x46}

# Formatting
enableText = {True: "啟動", False: "關閉"}
showText = {True: "顯示", False: "隱藏"}
def percent(val, digit=0):
  if digit == 0:
    return "{:.0%}".format(val)
  else:
    return str(round(val * 100, digit)) + '%'
def timestamp():
  return "【" + datetime.now().strftime("%H:%M:%S") + "】"

# Client actions
def sendBait(hwnd):
  win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, VK_Keys[cfg.baitKey], 0)
  sleep(0.1)
  win32gui.PostMessage(hwnd, win32con.WM_KEYUP, VK_Keys[cfg.baitKey], 0)

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
  for hwnd in list(hwndThreads.keys()):
    # Flag closed/missing clients
    if hwndThreads[hwnd]["status"] == -1:
      hwndThreads[hwnd]["missingTime"] = 0
      hwndThreads[hwnd]["status"] = 0
      hwndThreads[hwnd]["statusText"] = "視窗錯誤或已關閉"
      window.addLog(f"劍靈客戶端[{hwnd}]－客戶端視窗錯誤或已關閉，已停止搜尋")
    
    # Clear stopped clients
    if hwndThreads[hwnd]["status"] == 0:
      if hwndThreads[hwnd]["missingTime"] >= 15:
        del hwndThreads[hwnd]
      else:
        hwndThreads[hwnd]["missingTime"] += 1

  # Find new clients
  matchList = matchWindowHwnd(pattern)
  for hwnd in matchList:
    # Create & initialize threadObj if doesn't exist
    if hwnd not in hwndThreads:
      hwndThreads[hwnd] = {}
      hwndThreads[hwnd]["status"] = 0
      hwndThreads[hwnd]["pause"] = False
      hwndThreads[hwnd]["countDragSuccess"] = 0
      hwndThreads[hwnd]["countNotMatch"] = 0

    # Start thread
    if hwndThreads[hwnd]["status"] == 0:
      hwndThreads[hwnd]["status"] = 1
      hwndThreads[hwnd]["thread"] = Thread(target=fishing, args=(hwnd,))
      hwndThreads[hwnd]["thread"].start()
      window.addLog(f"劍靈客戶端[{hwnd}]－搜尋到客戶端")

def countActiveHwnd(hwndObj):
  count = 0
  for hwnd in list(hwndObj.keys()):
    if hwndThreads[hwnd]["status"] == 1:
      count += 1
  return count

# Fishing loop
def fishing(hwnd):
  while True:
    if not path.exists(cfg.captureImg):
      hwndThreads[hwnd]["statusText"] = "找不到釣魚按鈕截圖"
      sleep(1)
    else:
      # Check if client window exist
      if win32gui.GetWindowText(hwnd) != clientName:
        break
      # Main fishing loop
      try:
        if mainSwitch and not hwndThreads[hwnd]["pause"]:
          hwndThreads[hwnd]["statusText"] = "釣魚中"
          matchRate = imageMatch(hwnd, cfg.captureImg)
          if matchRate < cfg.threshold:
            hwndThreads[hwnd]["countNotMatch"] += 1
            window.addLog(f"劍靈客戶端[{hwnd}]－未偵測到收竿按鈕（匹配度：{percent(matchRate, 1)}）", detail=True)

            # Stop check
            if cfg.enableStopCheck:
              if hwndThreads[hwnd]["countNotMatch"] >= cfg.stopCheckFreq:
                sendBait(hwnd)
                hwndThreads[hwnd]["countNotMatch"] = 0
                window.addLog(f"劍靈客戶端[{hwnd}]－檢查到釣魚狀態停止，已重新下魚餌")
          else:
            window.addLog(f"劍靈客戶端[{hwnd}]－已偵測到收竿按鈕（匹配度：{percent(matchRate, 1)}）", detail=True)

            # Delay & drag
            sleep(cfg.dragDelay)
            sendDrag(hwnd)
            hwndThreads[hwnd]["countNotMatch"] = 0
            hwndThreads[hwnd]["countDragSuccess"] += 1
            window.addLog(f"劍靈客戶端[{hwnd}]－釣魚成功（收竿次數：{hwndThreads[hwnd]['countDragSuccess']}）")

            # Wait and send bait
            sleep(1)
            sendBait(hwnd)

          # Delay for next loop
          sleep(cfg.interval)
        else:
          if not mainSwitch:
            hwndThreads[hwnd]["statusText"] = "程式未運行"
          else:
            hwndThreads[hwnd]["statusText"] = "暫停中"
          sleep(1)
      except:
        # print("Unexpected error:", sys.exc_info())
        break
  hwndThreads[hwnd]["status"] = -1
  return

# Config class
class Config:
  # UI helpers
  btnStatusTimer = None

  # Default configuration values
  captureImg = captureImgDefault = "fishing.png"
  baitKey = baitKeyDefault = "5"
  interval = intervalDefault = 1
  dragDelay = dragDelayDefault = 0.5
  threshold = thresholdDefault = 0.8
  enableStopCheck = enableStopCheckDefault = False
  stopCheckInterval = stopCheckIntervalDefault = 40
  showDetails = showDetailsDefault = False
  hideToTray = hideToTrayDefault = False
  darkTheme = darkThemeDefault = True

  def __init__(self):
    self.configExist = path.exists(configFile)
    if(self.configExist):
      config = configparser.ConfigParser()
      config.read(configFile)
      self.captureImg = config.get('UserPreference', 'captureImg', fallback=self.captureImgDefault)
      self.baitKey = self.validBaitKey(config.get('UserPreference', 'baitKey', fallback=self.baitKeyDefault))
      self.interval = config.getfloat('UserPreference', 'interval', fallback=self.intervalDefault)
      self.dragDelay = config.getfloat('UserPreference', 'dragDelay', fallback=self.dragDelayDefault)
      self.threshold = config.getfloat('UserPreference', 'threshold', fallback=self.thresholdDefault)
      self.enableStopCheck = config.getboolean('UserPreference', 'enableStopCheck', fallback=self.enableStopCheckDefault)
      self.stopCheckInterval = config.getint('UserPreference', 'stopCheckInterval', fallback=self.stopCheckIntervalDefault)
      self.showDetails = config.getboolean('UserPreference', 'showDetails', fallback=self.showDetailsDefault)
      self.hideToTray = config.getboolean('UserPreference', 'hideToTray', fallback=self.hideToTrayDefault)
      self.darkTheme = config.getboolean('UserPreference', 'darkTheme', fallback=self.darkThemeDefault)
    
    # Calculated configuration
    self.stopCheckFreq = int(round(self.stopCheckInterval / self.interval))

  def validBaitKey(self, key):
    validList = ["5", "6", "7", "8"]
    if key in validList:
        return key
    return self.baitKey

  def setUiValue(self, default=False):
    window.ui.inputCaptureImg.setText(self.captureImg)
    window.ui.inputBaitKey.setCurrentText(self.baitKey)
    window.ui.inputInterval.setValue(self.interval)
    window.ui.inputDragDelay.setValue(self.dragDelay)
    window.ui.inputThreshold.setValue(self.threshold * 100)
    window.ui.inputEnableStopCheck.setChecked(self.enableStopCheck)
    window.ui.inputStopCheckInterval.setValue(self.stopCheckInterval)
    window.ui.inputShowDetails.setChecked(self.showDetails)
    window.ui.inputHideToTray.setChecked(self.hideToTray)
    window.ui.inputDarkTheme.setChecked(self.darkTheme)
    if default:
      window.ui.inputCaptureImg.setText(self.captureImgDefault)
      window.ui.inputBaitKey.setCurrentText(self.baitKeyDefault)
      window.ui.inputInterval.setValue(self.intervalDefault)
      window.ui.inputDragDelay.setValue(self.dragDelayDefault)
      window.ui.inputThreshold.setValue(self.thresholdDefault * 100)
      window.ui.inputEnableStopCheck.setChecked(self.enableStopCheckDefault)
      window.ui.inputStopCheckInterval.setValue(self.stopCheckIntervalDefault)
      window.ui.inputShowDetails.setChecked(self.showDetailsDefault)
      window.ui.inputHideToTray.setChecked(self.hideToTrayDefault)
      window.ui.inputDarkTheme.setChecked(self.darkThemeDefault)

  def getUiValue(self):
    self.captureImg = window.ui.inputCaptureImg.text()
    self.baitKey = window.ui.inputBaitKey.currentText()
    self.interval = window.ui.inputInterval.value()
    self.dragDelay = window.ui.inputDragDelay.value()
    self.threshold = window.ui.inputThreshold.value() / 100
    self.enableStopCheck = window.ui.inputEnableStopCheck.isChecked()
    self.stopCheckInterval = window.ui.inputStopCheckInterval.value()
    self.showDetails = window.ui.inputShowDetails.isChecked()
    self.hideToTray = window.ui.inputHideToTray.isChecked()
    self.darkTheme = window.ui.inputDarkTheme.isChecked()
    # Calculated configuration
    self.stopCheckFreq = int(round(self.stopCheckInterval / self.interval))

  def save(self):
    self.getUiValue()
    config = configparser.ConfigParser()
    config.optionxform = str
    config["UserPreference"] = {}
    pref = config["UserPreference"]
    pref["captureImg"] = str(self.captureImg)
    pref["baitKey"] = str(self.baitKey)
    pref["interval"] = str(self.interval)
    pref["dragDelay"] = str(self.dragDelay)
    pref["threshold"] = str(self.threshold)
    pref["enableStopCheck"] = str(self.enableStopCheck)
    pref["stopCheckInterval"] = str(self.stopCheckInterval)
    pref["showDetails"] = str(self.showDetails)
    pref["hideToTray"] = str(self.hideToTray)
    pref["darkTheme"] = str(self.darkTheme)
    with open(configFile, "w") as file:
      config.write(file)

    self.showConfigBtnStatus("配置設定已套用並儲存")
    self.addLog(f"配置設定已套用並儲存至{configFile}")

  def restore(self):
    self.setUiValue()
    self.showConfigBtnStatus("未套用的配置設定已回復")
    self.addLog("未套用的配置設定已回復至上次儲存狀態")

  def default(self):
    self.setUiValue(default=True)
    self.showConfigBtnStatus("配置設定已還原成預設值（未套用）")
    self.addLog("配置設定已還原成預設值（未套用、需按「套用設定」套用設定）")

  def hideConfigBtnStatus(self):
    window.ui.lblConfigBtnText.setText("")

  def showConfigBtnStatus(self, msg):
    window.ui.lblConfigBtnText.setText(timestamp() + "：" + msg)
    self.btnStatusTimer = QtCore.QTimer()
    self.btnStatusTimer.timeout.connect(self.hideConfigBtnStatus)
    self.btnStatusTimer.setSingleShot(True)
    self.btnStatusTimer.start(4000)

  def addLog(self, msg, detail=False, bold=False):
    if not detail or self.showDetails:
      msg = str(msg)
      if bold:
        msg = "<b>" + msg + "</b>"
      window.addLog(msg)

# Worker loop
class Worker(QtCore.QObject):
  addLogSignal = QtCore.pyqtSignal(str)
  updateStatusSignal = QtCore.pyqtSignal()

  def __init__(self, parent=None):
    QtCore.QObject.__init__(self, parent=parent)
    self.loadProgress = 0

  def addLoad(self, val):
    self.loadProgress += val
    window.ui.barLoad.setValue(self.loadProgress)
    sleep(0.8)

  def addLog(self, msg, detail=False, bold=False):
    if not detail or cfg.showDetails:
      msg = str(msg)
      if bold:
        msg = "<b>" + msg + "</b>"
      self.addLogSignal.emit(msg)

  def mainLoop(self):
    # Loading starts
    self.addLog(f"{programName}{programVersion}啟動中", bold=True)

    # 1. Check admin rights
    isAdmin = windll.shell32.IsUserAnAdmin() != 0
    self.addLoad(33)
    if(not isAdmin):
      window.ui.lblLoadStatus.setText("載入錯誤：請以系統管理員身份執行此程式")
      palette = QtGui.QPalette()
      palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.red)
      window.ui.lblLoadStatus.setPalette(palette)
    else:
      # 2. Insert custom config values to ui
      if cfg.configExist:
        self.addLog(f"已找到{configFile}，正在讀取自定義配置")
      else:
        self.addLog(f"找不到{configFile}，已載入預設配置")
      cfg.setUiValue()
      self.addLog("＊＊＊自動釣魚程式參數＊＊＊", detail=True)
      self.addLog(f"＊釣魚收竿按鈕截圖名稱：{cfg.captureImg}", detail=True)
      self.addLog(f"＊魚餌道具欄位置：{cfg.baitKey}", detail=True)
      self.addLog(f"＊判定時間間距秒數：{cfg.interval}秒", detail=True)
      self.addLog(f"＊收竿延遲秒數：{cfg.dragDelay}秒", detail=True)
      self.addLog(f"＊最低匹配近似度：{percent(cfg.threshold)}", detail=True)
      self.addLog(f"＊釣魚狀態檢查：{enableText[cfg.enableStopCheck]}", detail=True)
      self.addLog(f"＊檢查間距秒數：{cfg.stopCheckInterval}秒", detail=True)
      self.addLog(f"＊運行日誌更詳細記錄：{showText[cfg.showDetails]}", detail=True)
      self.addLog(f"＊黑夜模式：{enableText[cfg.darkTheme]}", detail=True)
      self.addLoad(34)

      # Search client once before window show
      scanWindowHwnd(clientName)
      self.addLoad(33)

      # Loading complete
      if self.loadProgress >= 100:
        window.ui.tabsMain.show()
        window.ui.widgetLoad.hide()
        window.loadDone = True
        self.addLog(f"{programName}{programVersion}載入完成", bold=True)

      # Operation loop
      while True:
        self.updateStatusSignal.emit()
        if mainSwitch:
          # Scan for new client hwnds to start fishing
          scanWindowHwnd(clientName)

          # If no active clients
          if(countActiveHwnd(hwndThreads) <= 0):
            self.addLog("未找到劍靈客戶端")

          # Check if capture image exist
          if not path.exists(cfg.captureImg):
            self.addLog("找不到釣魚按鈕截圖")

          # Delay for next loop
          QtCore.QThread.msleep(int(1000 * cfg.interval))
        else:
          QtCore.QThread.sleep(1)

# Program window (GUI)
class GUI(QtWidgets.QMainWindow):
  loadDone = False
  def __init__(self):
    # Initialize and setup window
    super(GUI, self).__init__()
    self.ui = gui.Ui_BNSAutoFishing()
    self.ui.setupUi(self)
    self.ui.lblVersion.setText(programVersion)
    self.ui.tabsMain.hide()
    self.ui.widgetDebug.hide()

    # System tray icon
    self.tray_icon = QtWidgets.QSystemTrayIcon(self)
    self.tray_icon.setIcon(QtGui.QIcon(":/icon.ico"))
    show_action = QtWidgets.QAction("顯示", self)
    hide_action = QtWidgets.QAction("隱藏", self)
    quit_action = QtWidgets.QAction("結束程式", self)
    show_action.triggered.connect(self.show)
    hide_action.triggered.connect(self.hide)
    quit_action.triggered.connect(QtWidgets.qApp.quit)
    tray_menu = QtWidgets.QMenu()
    tray_menu.addAction(show_action)
    tray_menu.addAction(hide_action)
    tray_menu.addAction(quit_action)
    self.tray_icon.setContextMenu(tray_menu)
    self.tray_icon.show()
    self.tray_icon.activated.connect(self.restoreFromTray)

    # Connect UI components
    self.ui.btnDebug.clicked.connect(self.btnDebug)
    self.ui.btnStart.clicked.connect(self.startStop)
    checkboxWidget = []
    btnWidget = []
    for i in range(10):
      checkboxWidget.append(self.ui.gridStatus.itemAt(i).widget().layout().itemAt(0).widget())
      btnWidget.append(self.ui.gridStatus.itemAt(i).widget().layout().itemAt(1).widget())
    checkboxWidget[0].stateChanged.connect(lambda: self.toggleThreadPause(0))
    checkboxWidget[1].stateChanged.connect(lambda: self.toggleThreadPause(1))
    checkboxWidget[2].stateChanged.connect(lambda: self.toggleThreadPause(2))
    checkboxWidget[3].stateChanged.connect(lambda: self.toggleThreadPause(3))
    checkboxWidget[4].stateChanged.connect(lambda: self.toggleThreadPause(4))
    checkboxWidget[5].stateChanged.connect(lambda: self.toggleThreadPause(5))
    checkboxWidget[6].stateChanged.connect(lambda: self.toggleThreadPause(6))
    checkboxWidget[7].stateChanged.connect(lambda: self.toggleThreadPause(7))
    checkboxWidget[8].stateChanged.connect(lambda: self.toggleThreadPause(8))
    checkboxWidget[9].stateChanged.connect(lambda: self.toggleThreadPause(9))
    btnWidget[0].clicked.connect(lambda: self.focusClientWindow(0))
    btnWidget[1].clicked.connect(lambda: self.focusClientWindow(1))
    btnWidget[2].clicked.connect(lambda: self.focusClientWindow(2))
    btnWidget[3].clicked.connect(lambda: self.focusClientWindow(3))
    btnWidget[4].clicked.connect(lambda: self.focusClientWindow(4))
    btnWidget[5].clicked.connect(lambda: self.focusClientWindow(5))
    btnWidget[6].clicked.connect(lambda: self.focusClientWindow(6))
    btnWidget[7].clicked.connect(lambda: self.focusClientWindow(7))
    btnWidget[8].clicked.connect(lambda: self.focusClientWindow(8))
    btnWidget[9].clicked.connect(lambda: self.focusClientWindow(9))
    self.ui.btnConfigSave.clicked.connect(cfg.save)
    self.ui.btnConfigRestore.clicked.connect(cfg.restore)
    self.ui.btnConfigDefault.clicked.connect(cfg.default)

    # Create worker thread
    self.thread = QtCore.QThread()
    self.worker = Worker()  
    self.worker.moveToThread(self.thread)
    self.worker.addLogSignal.connect(self.addLog)
    self.worker.updateStatusSignal.connect(self.updateStatus)
    self.thread.started.connect(self.worker.mainLoop)
    self.thread.start()

    self.show()
    
  # Hide to tray: override closeEvent
  def closeEvent(self, event):
    if self.loadDone and cfg.hideToTray:
      event.ignore()
      self.hide()
      self.tray_icon.showMessage(programName, "縮小到系統列在背景運行", QtGui.QIcon(":/icon.ico"), 2000)

  def restoreFromTray(self, event):
    if event == QtWidgets.QSystemTrayIcon.DoubleClick:
      self.show()

  def btnDebug(self):
    print(hwndThreads)

  def startStop(self):
    global mainSwitch
    if not mainSwitch:
      mainSwitch = True
      self.ui.btnStart.setText("停止釣魚")
      self.ui.lblStatus2.setText("釣魚中")
      self.addLog("程式開始運行")
    else:
      mainSwitch = False
      self.ui.btnStart.setText("開始釣魚")
      self.ui.lblStatus2.setText("未運行")
      self.addLog("程式停止運行")

  def toggleThreadPause(self, pos):
    hwnd = self.ui.gridStatus.itemAt(pos).widget().property("hwnd")
    checked = self.ui.gridStatus.itemAt(pos).widget().layout().itemAt(0).widget().isChecked()
    hwndThreads[hwnd]["pause"] = checked
    if checked:
      self.addLog(f"劍靈客戶端[{hwnd}]－此客戶端暫停釣魚")
    else:
      self.addLog(f"劍靈客戶端[{hwnd}]－此客戶端繼續釣魚")

  def focusClientWindow(self, pos):
    try:
      bnsClientHwnd = self.ui.gridStatus.itemAt(pos).widget().property("hwnd")
      fishingAppHwnd = win32gui.GetForegroundWindow()
      win32gui.BringWindowToTop(bnsClientHwnd)
      sleep(0.05)
      win32gui.BringWindowToTop(fishingAppHwnd)
    except:
      return

  def addLog(self, msg, detail=False, bold=False):
    if not detail or cfg.showDetails:
      msg = str(msg)
      if bold:
        msg = "<b>" + msg + "</b>"
      self.ui.txtLog.append(timestamp() + "：" + msg)
      self.ui.txtLog.ensureCursorVisible()

  def updateStatus(self):
    i = 0
    for hwnd in list(hwndThreads.keys()):
      if i < 10:
        statusUi = self.ui.gridStatus.itemAt(i).widget()
        statusUi.show()
        statusUi.setProperty("hwnd", hwnd)
        statusUi.layout().itemAt(0).widget().setChecked(hwndThreads[hwnd]["pause"])
        statusUi.layout().itemAt(1).widget().setText(str(hwnd))
        statusUi.layout().itemAt(2).widget().setText(str(hwndThreads[hwnd]["statusText"]))
        statusUi.layout().itemAt(3).widget().setText(str(hwndThreads[hwnd]["countDragSuccess"]))
        i += 1
    for j in range(i,10):
      self.ui.gridStatus.itemAt(j).widget().hide()


if __name__ == '__main__':
  app = QtWidgets.QApplication(sys.argv)
  app.setStyle('Fusion')

  cfg = Config()

  # Dark theme
  if cfg.darkTheme:
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Highlight, QtCore.Qt.gray)
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Window, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, QtCore.Qt.gray)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Base, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Text, QtCore.Qt.gray)
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.Button, QtGui.QColor(53,53,53))
    palette.setColor(QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText, QtCore.Qt.gray)
    app.setPalette(palette)

  window = GUI()
  sys.exit(app.exec_())