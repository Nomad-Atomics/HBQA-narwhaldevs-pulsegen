# gui.py (with explicit "Manual outputs" group for per-channel control)
import sys
import struct
import time
import threading
from typing import Optional, List, Dict, Any

from PyQt5.QtCore import (
    Qt, QObject, QThread, pyqtSignal, QTimer, QSettings, QSize
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QComboBox, QLabel, QAction, QToolBar, QGroupBox, QCheckBox,
    QTextEdit, QDoubleSpinBox, QLineEdit, QMessageBox, QScrollArea
)

import serial
import serial.tools.list_ports

from . import transcode


class SerialWorker(QObject):
    messageReceived = pyqtSignal(dict)
    devicestate = pyqtSignal(dict)
    powerlinestate = pyqtSignal(dict)
    devicestate_extras = pyqtSignal(dict)
    notification = pyqtSignal(dict)
    echo = pyqtSignal(dict)
    easyprint = pyqtSignal(dict)
    bytesDropped = pyqtSignal(int, float)
    errorOccurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, ser: serial.Serial, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.ser = ser
        self._running = True

    def stop(self):
        self._running = False
        try:
            self.ser.cancel_read()
        except Exception:
            pass

    def run(self):
        try:
            while self._running:
                try:
                    b = self.ser.read(1)
                except serial.serialutil.SerialException as ex:
                    self.errorOccurred.emit(str(ex)); break
                if not b:
                    continue
                ts = time.time()
                msg_id = b[0]
                dinfo = transcode.msgin_decodeinfo.get(msg_id)
                if not dinfo:
                    self.bytesDropped.emit(msg_id, ts); continue
                remaining = dinfo['message_length'] - 1
                try:
                    payload = self.ser.read(remaining)
                except serial.serialutil.SerialException as ex:
                    self.errorOccurred.emit(str(ex)); break
                if len(payload) != remaining:
                    self.bytesDropped.emit(msg_id, ts); continue
                try:
                    decoded = dinfo['decode_function'](payload)
                except Exception as ex:
                    self.errorOccurred.emit(f"Decode failed for id {msg_id}: {ex}"); continue
                decoded['timestamp'] = ts
                decoded['message_type'] = dinfo['message_type']
                self.messageReceived.emit(decoded)
                mtype = dinfo['message_type']
                if mtype == 'devicestate':
                    self.devicestate.emit(decoded)
                elif mtype == 'powerlinestate':
                    self.powerlinestate.emit(decoded)
                elif mtype == 'devicestate_extras':
                    self.devicestate_extras.emit(decoded)
                elif mtype == 'notification':
                    self.notification.emit(decoded)
                elif mtype == 'echo':
                    self.echo.emit(decoded)
                elif mtype == 'print':
                    self.easyprint.emit(decoded)
        finally:
            self.finished.emit()


class PulseGenerator(QObject):
    devicestate = pyqtSignal(dict)
    powerlinestate = pyqtSignal(dict)
    devicestate_extras = pyqtSignal(dict)
    notification = pyqtSignal(dict)
    echo = pyqtSignal(dict)
    easyprint = pyqtSignal(dict)
    bytesDropped = pyqtSignal(int, float)
    errorOccurred = pyqtSignal(str)
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.ser = serial.Serial()
        self.ser.timeout = 0.1
        self.ser.write_timeout = 1
        self.ser.baudrate = 12000000

        self._write_lock = threading.Lock()
        self._thread: Optional[QThread] = None
        self._worker: Optional[SerialWorker] = None

        self._valid_vid = 1027
        self._valid_pid = 24592

        self.serial_number_save: Optional[int] = None
        self.device_type: Optional[int] = None
        self.firmware_version: Optional[str] = None
        self.hardware_version: Optional[str] = None

    def is_open(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def _start_reader(self):
        self._thread = QThread()
        self._worker = SerialWorker(self.ser)
        self._worker.moveToThread(self._thread)
        self._worker.devicestate.connect(self.devicestate)
        self._worker.powerlinestate.connect(self.powerlinestate)
        self._worker.devicestate_extras.connect(self.devicestate_extras)
        self._worker.notification.connect(self.notification)
        self._worker.echo.connect(self.echo)
        self._worker.easyprint.connect(self.easyprint)
        self._worker.bytesDropped.connect(self.bytesDropped)
        self._worker.errorOccurred.connect(self.errorOccurred)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()
        self.connected.emit(self.ser.port)

    def _stop_reader(self):
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit(); self._thread.wait(1500)
        self._worker = None; self._thread = None

    def disconnect(self):
        try:
            self._stop_reader()
        finally:
            try:
                if self.ser and self.ser.is_open:
                    self.ser.close()
            finally:
                self.disconnected.emit()

    def connect(self, serial_number: Optional[int] = None, port: Optional[str] = None) -> bool:
        if self.is_open():
            try:
                self.ser.reset_input_buffer(); self.ser.reset_output_buffer()
            except Exception: pass
            return True

        target_port = None; device_meta = None
        if serial_number is not None or port is None:
            devices = self.get_connected_devices()['validated_devices']
            for d in devices:
                if (serial_number is not None and d.get('serial_number') == serial_number) or \
                   (serial_number is None and port is None):
                    target_port = d['comport']; device_meta = d; break
        if port is not None and target_port is None:
            target_port = port
        if not target_port: return False

        self.ser.port = target_port; self.ser.open()
        self.ser.reset_input_buffer(); self.ser.reset_output_buffer()
        self._start_reader()

        if device_meta:
            self.serial_number_save = device_meta.get('serial_number')
            self.device_type = device_meta.get('device_type')
            self.firmware_version = device_meta.get('firmware_version')
            self.hardware_version = device_meta.get('hardware_version')
        return True

    def get_connected_devices(self) -> Dict[str, Any]:
        validated_devices = []; unvalidated = []
        comports = list(serial.tools.list_ports.comports())
        valid_ports = [cp for cp in comports if getattr(cp, 'vid', None) == self._valid_vid and getattr(cp, 'pid', None) == self._valid_pid]
        for cp in valid_ports:
            ok, meta = self._try_handshake(cp.device)
            if ok and meta: meta['comport'] = cp.device; validated_devices.append(meta)
            else: unvalidated.append(cp.device)
        return {'validated_devices': validated_devices, 'unvalidated_devices': unvalidated}

    def _try_handshake(self, port: str, timeout_s: float = 1.0):
        s = serial.Serial()
        s.port = port; s.baudrate = self.ser.baudrate; s.timeout = 0.2; s.write_timeout = 0.5
        try: s.open()
        except Exception: return False, None
        try:
            s.reset_input_buffer(); s.reset_output_buffer()
            check_byte = bytes([209])
            s.write(transcode.encode_echo(check_byte))
            t0 = time.time()
            while time.time() - t0 < timeout_s:
                b = s.read(1)
                if not b: continue
                msg_id = b[0]
                dinfo = transcode.msgin_decodeinfo.get(msg_id)
                if not dinfo: continue
                remaining = dinfo['message_length'] - 1
                payload = s.read(remaining)
                if len(payload) != remaining: continue
                decoded = dinfo['decode_function'](payload)
                if dinfo['message_type'] == 'echo' and decoded.get('echoed_byte') == check_byte:
                    return True, {
                        'device_type': decoded.get('device_type'),
                        'hardware_version': decoded.get('hardware_version'),
                        'firmware_version': decoded.get('firmware_version'),
                        'serial_number': decoded.get('serial_number'),
                    }
            return False, None
        finally:
            try: s.close()
            except Exception: pass

    def write_command(self, encoded_command: bytes):
        if not self.is_open():
            raise serial.serialutil.PortNotOpenError("Serial port is not open")
        with self._write_lock:
            self.ser.write(encoded_command)

    def write_echo(self, byte_to_echo: bytes):
        self.write_command(transcode.encode_echo(byte_to_echo))

    def write_device_options(self, final_address=None, run_mode=None,
                             accept_hardware_trigger=None,
                             trigger_out_length=None, trigger_out_delay=None,
                             notify_on_main_trig_out=None,
                             notify_when_run_finished=None,
                             software_run_enable=None):
        self.write_command(
            transcode.encode_device_options(
                final_address, run_mode, accept_hardware_trigger,
                trigger_out_length, trigger_out_delay,
                notify_on_main_trig_out, notify_when_run_finished,
                software_run_enable
            )
        )

    def write_powerline_trigger_options(self, trigger_on_powerline=None, powerline_trigger_delay=None):
        self.write_command(
            transcode.encode_powerline_trigger_options(trigger_on_powerline, powerline_trigger_delay)
        )

    def write_action(self, trigger_now=False, disable_after_current_run=False, disarm=False,
                     request_state=False, request_powerline_state=False, request_state_extras=False):
        self.write_command(
            transcode.encode_action(
                trigger_now, disable_after_current_run, disarm,
                request_state, request_powerline_state, request_state_extras
            )
        )

    def write_general_debug(self, message: bytes):
        self.write_command(transcode.encode_general_debug(message))

    def write_static_state(self, state: List[bool]):
        self.write_command(transcode.encode_static_state(state))

    def write_instructions(self, instructions: List[bytes]):
        if hasattr(transcode, 'encode_instructions'):
            self.write_command(transcode.encode_instructions(instructions))
        else:
            for instr in instructions: self.write_command(instr)


class MainWindow(QMainWindow):
    POLL_MS = 100

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pulse Generator Controller")
        self.resize(1220, 840)

        self.settings = QSettings("ndpulsegen", "gui")
        self.pg = PulseGenerator(self)

        self.pg.devicestate.connect(self.on_devicestate)
        self.pg.powerlinestate.connect(self.on_powerlinestate)
        self.pg.devicestate_extras.connect(self.on_devicestate_extras)
        self.pg.notification.connect(self.on_notification)
        self.pg.echo.connect(self.on_echo)
        self.pg.easyprint.connect(self.on_easyprint)
        self.pg.bytesDropped.connect(self.on_bytes_dropped)
        self.pg.errorOccurred.connect(self.on_error)
        self.pg.connected.connect(self.on_connected)
        self.pg.disconnected.connect(self.on_disconnected)

        # Status bar
        self.connStatusLabel = QLabel("Disconnected")
        self.statusBar().addPermanentWidget(self.connStatusLabel)
        self.statusBar().showMessage("Ready", 2000)

        # Toolbar
        toolbar = QToolBar("Main"); toolbar.setIconSize(QSize(16, 16)); self.addToolBar(toolbar)
        self.refreshAction = QAction("Refresh Devices", self); self.refreshAction.triggered.connect(self.check_devices); toolbar.addAction(self.refreshAction)
        self.connectAction = QAction("Connect", self); self.connectAction.triggered.connect(self.connect_device); toolbar.addAction(self.connectAction)
        self.disconnectAction = QAction("Disconnect", self); self.disconnectAction.triggered.connect(self.disconnect_device); toolbar.addAction(self.disconnectAction)

        # Device chooser
        self.deviceComboBox = QComboBox()

        # ---- Manual outputs group (top half) ----
        channelGrid = QGridLayout()
        self.channelWidgets = []  # list of (QLineEdit, QPushButton)
        for i in range(24):
            container = QWidget()
            vbox = QVBoxLayout(container); vbox.setContentsMargins(2,2,2,2); vbox.setSpacing(2)
            label_edit = QLineEdit(); label_edit.setPlaceholderText(f"Ch {i}")
            saved = self.settings.value(f"channels/{i}", "")
            if saved is None: saved = ""
            label_edit.setText(saved)
            label_edit.editingFinished.connect(lambda i=i, e=label_edit: self.settings.setValue(f"channels/{i}", e.text()))
            vbox.addWidget(label_edit)

            btn = QPushButton(str(i)); btn.setCheckable(True)
            btn.clicked.connect(self.make_toggle_handler(i))
            vbox.addWidget(btn)

            self.channelWidgets.append((label_edit, btn))
            row, col = divmod(i, 8)
            channelGrid.addWidget(container, row, col)

        manualBox = QGroupBox("Manual outputs")
        manualLayout = QVBoxLayout(manualBox)
        manualLayout.addLayout(channelGrid)

        # Global manual controls
        globalsRow = QHBoxLayout()
        allOn = QPushButton("All ON"); allOff = QPushButton("All OFF"); invert = QPushButton("Invert")
        allOn.clicked.connect(self.set_all_on); allOff.clicked.connect(self.set_all_off); invert.clicked.connect(self.invert_all)
        globalsRow.addWidget(allOn); globalsRow.addWidget(allOff); globalsRow.addWidget(invert); globalsRow.addStretch(1)
        manualLayout.addLayout(globalsRow)

        # ---- Bottom: two columns ----
        # Status
        statusBox = QGroupBox("Status"); statusLayout = QGridLayout(statusBox)
        statusLayout.addWidget(QLabel("Running:"), 0, 0); self.runningIndicator = QLabel(); self.runningIndicator.setFixedSize(16,16); statusLayout.addWidget(self.runningIndicator, 0, 1)
        statusLayout.addWidget(QLabel("Run enable - Software:"), 1, 0); self.softwareRunEnable = QLabel(); self.softwareRunEnable.setFixedSize(16,16); statusLayout.addWidget(self.softwareRunEnable, 1, 1)
        statusLayout.addWidget(QLabel("Run enable - Hardware:"), 2, 0); self.hardwareRunEnable = QLabel(); self.hardwareRunEnable.setFixedSize(16,16); statusLayout.addWidget(self.hardwareRunEnable, 2, 1)
        statusLayout.addWidget(QLabel("Current address:"), 3, 0); self.currentAddrLabel = QLabel("—"); statusLayout.addWidget(self.currentAddrLabel, 3, 1)
        statusLayout.addWidget(QLabel("Final address:"), 4, 0); self.finalAddrLabel = QLabel("—"); statusLayout.addWidget(self.finalAddrLabel, 4, 1)
        statusLayout.addWidget(QLabel("Total run time:"), 5, 0); self.runTimeLabel = QLabel("—"); statusLayout.addWidget(self.runTimeLabel, 5, 1)

        # Synchronisation
        syncBox = QGroupBox("Synchronisation"); syncLayout = QGridLayout(syncBox)
        syncLayout.addWidget(QLabel("Reference Clock:"), 0, 0); self.refClockLabel = QLabel("—"); syncLayout.addWidget(self.refClockLabel, 0, 1)
        syncLayout.addWidget(QLabel("Powerline frequency (Hz):"), 1, 0); self.freqLabel = QLabel("—"); syncLayout.addWidget(self.freqLabel, 1, 1)

        # Device info
        infoBox = QGroupBox("Device info"); infoLayout = QGridLayout(infoBox)
        infoLayout.addWidget(QLabel("Serial number:"), 0, 0); self.snLabel = QLabel("—"); infoLayout.addWidget(self.snLabel, 0, 1)
        infoLayout.addWidget(QLabel("Device type:"), 1, 0); self.devTypeLabel = QLabel("—"); infoLayout.addWidget(self.devTypeLabel, 1, 1)
        infoLayout.addWidget(QLabel("Firmware version:"), 2, 0); self.fwLabel = QLabel("—"); infoLayout.addWidget(self.fwLabel, 2, 1)
        infoLayout.addWidget(QLabel("Hardware version:"), 3, 0); self.hwLabel = QLabel("—"); infoLayout.addWidget(self.hwLabel, 3, 1)
        infoLayout.addWidget(QLabel("Port:"), 4, 0); self.portLabel = QLabel("—"); infoLayout.addWidget(self.portLabel, 4, 1)

        # Trigger in
        inBox = QGroupBox("Trigger in"); inLayout = QGridLayout(inBox)
        inLayout.addWidget(QLabel("Accept hardware trigger:"), 0, 0)
        self.acceptHwCombo = QComboBox(); self.acceptHwCombo.addItems(["never", "always", "single_run", "once"])
        self.acceptHwCombo.currentTextChanged.connect(self.on_accept_hw_changed); inLayout.addWidget(self.acceptHwCombo, 0, 1)
        inLayout.addWidget(QLabel("Wait for powerline:"), 1, 0)
        self.waitCheckbox = QCheckBox(); self.waitCheckbox.stateChanged.connect(self.on_wait_changed); inLayout.addWidget(self.waitCheckbox, 1, 1)
        inLayout.addWidget(QLabel("Delay after powerline (ms):"), 2, 0)
        self.delaySpin = QDoubleSpinBox(); self.delaySpin.setDecimals(3); self.delaySpin.setRange(0.0, 10000.0)
        self.delaySpin.valueChanged.connect(self.on_delay_changed); inLayout.addWidget(self.delaySpin, 2, 1)

        # Trigger out
        outBox = QGroupBox("Trigger out"); outLayout = QGridLayout(outBox)
        outLayout.addWidget(QLabel("Duration (µs):"), 0, 0)
        self.trigOutLenSpin = QDoubleSpinBox(); self.trigOutLenSpin.setDecimals(3); self.trigOutLenSpin.setRange(0.0, 10000.0)
        self.trigOutLenSpin.valueChanged.connect(self.on_trigout_len_changed); outLayout.addWidget(self.trigOutLenSpin, 0, 1)
        outLayout.addWidget(QLabel("Delay (s):"), 1, 0)
        self.trigOutDelaySpin = QDoubleSpinBox(); self.trigOutDelaySpin.setDecimals(3); self.trigOutDelaySpin.setRange(0.0, 10000.0)
        self.trigOutDelaySpin.valueChanged.connect(self.on_trigout_delay_changed); outLayout.addWidget(self.trigOutDelaySpin, 1, 1)
        
        # self.triggerNowBtn = QPushButton("Trigger now"); self.triggerNowBtn.clicked.connect(lambda: self.pg.write_action(trigger_now=True))
        # outLayout.addWidget(self.triggerNowBtn, 4, 0, 1, 2)

        # Notifications
        notifBox = QGroupBox("Notifications"); notifLayout = QGridLayout(notifBox)
        notifLayout.addWidget(QLabel("Notify when finished:"), 0, 0)
        self.notifyFinishedCheckbox = QCheckBox(); self.notifyFinishedCheckbox.stateChanged.connect(self.on_notify_finished_changed)
        notifLayout.addWidget(self.notifyFinishedCheckbox, 0, 1)
        notifLayout.addWidget(QLabel("Notify on main trig out:"), 1, 0)
        self.notifyMainTrigOutCheckbox = QCheckBox(); self.notifyMainTrigOutCheckbox.stateChanged.connect(self.on_notify_main_trig_out_changed)
        notifLayout.addWidget(self.notifyMainTrigOutCheckbox, 1, 1)
        notifLayout.addWidget(QLabel("Incoming Notifications"), 2, 0)
        self.notifLog = QTextEdit(); self.notifLog.setReadOnly(True); notifLayout.addWidget(self.notifLog, 3, 0, 1, 2)

        # Two columns
        leftCol = QVBoxLayout(); leftCol.addWidget(statusBox); leftCol.addWidget(syncBox); leftCol.addWidget(infoBox); leftCol.addStretch(1)
        rightCol = QVBoxLayout(); rightCol.addWidget(inBox); rightCol.addWidget(outBox); rightCol.addWidget(notifBox); rightCol.addStretch(1)
        bottomCols = QHBoxLayout(); bottomCols.addLayout(leftCol, 1); bottomCols.addLayout(rightCol, 1)

        # Central layout
        centralLayout = QVBoxLayout()
        centralLayout.addWidget(self.deviceComboBox)
        centralLayout.addWidget(manualBox)
        centralLayout.addLayout(bottomCols)
        # central = QWidget(); central.setLayout(centralLayout); self.setCentralWidget(central)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        central = QWidget()
        central.setLayout(centralLayout)
        scroll.setWidget(central)

        self.setCentralWidget(scroll)


        # Timer
        self.request_timer = QTimer(self); self.request_timer.setInterval(self.POLL_MS); self.request_timer.timeout.connect(self.poll_status)

        self.check_devices()

    # Helpers
    @staticmethod
    def _set_indicator(widget: QLabel, on: bool):
        widget.setStyleSheet("background-color: green; border-radius: 8px;" if on else "background-color: red; border-radius: 8px;")

    def _state_to_bools(self, state_val: int) -> List[bool]:
        return [bool((state_val >> i) & 1) for i in range(24)]

    def _apply_state_to_buttons(self, state_bools: List[bool]):
        for i, (_, btn) in enumerate(self.channelWidgets):
            old = btn.blockSignals(True); btn.setChecked(bool(state_bools[i])); btn.blockSignals(old)

    # Global manual control handlers
    def set_all_on(self):
        for _, btn in self.channelWidgets:
            btn.setChecked(True)
        self.send_static_state()

    def set_all_off(self):
        for _, btn in self.channelWidgets:
            btn.setChecked(False)
        self.send_static_state()

    def invert_all(self):
        for _, btn in self.channelWidgets:
            btn.setChecked(not btn.isChecked())
        self.send_static_state()

    def send_static_state(self):
        state = [btn.isChecked() for _, btn in self.channelWidgets]
        try:
            self.pg.write_static_state(state)
            self.statusBar().showMessage("Static state sent", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error sending static state: {e}", 3000)

    # UI -> Device
    def make_toggle_handler(self, channel: int):
        def handler(checked: bool):
            self.send_static_state()
        return handler

    def on_accept_hw_changed(self, text: str):
        try:
            self.pg.write_device_options(accept_hardware_trigger=text)
            self.statusBar().showMessage("Updated accept_hardware_trigger", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 3000)

    def on_wait_changed(self, state: int):
        try:
            self.pg.write_powerline_trigger_options(trigger_on_powerline=bool(state))
            self.statusBar().showMessage("Updated trigger_on_powerline", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 3000)

    def on_delay_changed(self, value: float):
        value_clock_cycles = int(round(value*1e-3/10e-9))
        try:
            self.pg.write_powerline_trigger_options(powerline_trigger_delay=value_clock_cycles)
            self.statusBar().showMessage("Updated powerline delay", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 3000)

    def on_notify_finished_changed(self, state: int):
        try:
            self.pg.write_device_options(notify_when_run_finished=bool(state))
            self.statusBar().showMessage("Updated notify_when_run_finished", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 3000)

    def on_notify_main_trig_out_changed(self, state: int):
        try:
            self.pg.write_device_options(notify_on_main_trig_out=bool(state))
            self.statusBar().showMessage("Updated notify_on_main_trig_out", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 3000)

    def on_trigout_len_changed(self, value: float):
        value_clock_cycles = int(round(value*1e-6/10e-9))
        try:
            self.pg.write_device_options(trigger_out_length=value_clock_cycles)
            self.statusBar().showMessage("Updated trig out length", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 3000)

    def on_trigout_delay_changed(self, value: float):
        value_clock_cycles = int(round(value/10e-9))
        try:
            self.pg.write_device_options(trigger_out_delay=value_clock_cycles)
            self.statusBar().showMessage("Updated trig out delay", 1000)
        except Exception as e:
            self.statusBar().showMessage(f"Error: {e}", 3000)

    # Connection actions
    def check_devices(self):
        try:
            devs = self.pg.get_connected_devices().get('validated_devices', [])
            self.deviceComboBox.clear()
            for d in devs:
                label = f"SN {d.get('serial_number')} | FW {d.get('firmware_version')} | {d.get('comport')}"
                self.deviceComboBox.addItem(label, d)
            self.statusBar().showMessage("Devices updated." if devs else "No devices found.", 3000)
        except Exception as e:
            self.statusBar().showMessage(f"Error checking devices: {e}", 5000)

    def connect_device(self):
        idx = self.deviceComboBox.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Connect", "No device selected."); return
        dev = self.deviceComboBox.itemData(idx)
        try:
            ok = self.pg.connect(serial_number=dev.get('serial_number'))
            if ok:
                self.statusBar().showMessage("Connected", 2000)
                self.connStatusLabel.setText(f"Connected: {dev.get('comport')}")
                self.portLabel.setText(str(dev.get('comport')))
                self.snLabel.setText(str(dev.get('serial_number')))
                self.devTypeLabel.setText(str(dev.get('device_type')))
                self.fwLabel.setText(str(dev.get('firmware_version')))
                self.hwLabel.setText(str(dev.get('hardware_version')))
                self.request_timer.start()
            else:
                self.statusBar().showMessage("Connect failed: device not found.", 4000)
        except Exception as e:
            self.statusBar().showMessage(f"Error connecting: {e}", 5000)

    def disconnect_device(self):
        try:
            self.request_timer.stop(); self.pg.disconnect()
            self.statusBar().showMessage("Disconnected", 2000)
            self.connStatusLabel.setText("Disconnected"); self.portLabel.setText("—")
        except Exception as e:
            self.statusBar().showMessage(f"Error disconnecting: {e}", 5000)

    def poll_status(self):
        if not self.pg.is_open(): return
        try:
            self.pg.write_action(request_state=True, request_powerline_state=True, request_state_extras=True)
        except Exception as e:
            self.statusBar().showMessage(f"Error requesting state: {e}", 3000)

    # Worker slots
    def on_connected(self, port: str):
        self.statusBar().showMessage(f"Connected on {port}", 3000)
        self.connStatusLabel.setText(f"Connected: {port}"); self.portLabel.setText(port)

    def on_disconnected(self):
        self.statusBar().showMessage("Disconnected", 3000)
        self.connStatusLabel.setText("Disconnected"); self.portLabel.setText("—")

    def on_error(self, message: str):
        self.statusBar().showMessage(f"ERROR: {message}", 5000)

    def on_bytes_dropped(self, msg_id: int, ts: float):
        self.statusBar().showMessage(f"Dropped byte id {msg_id} at {ts:.3f}", 2000)

    def on_echo(self, msg: dict):
        if 'serial_number' in msg: self.snLabel.setText(str(msg.get('serial_number')))
        if 'device_type' in msg: self.devTypeLabel.setText(str(msg.get('device_type')))
        if 'firmware_version' in msg: self.fwLabel.setText(str(msg.get('firmware_version')))
        if 'hardware_version' in msg: self.hwLabel.setText(str(msg.get('hardware_version')))

    def on_easyprint(self, msg: dict):
        self.statusBar().showMessage(str(msg.get('easy_printed_value', msg)), 3000)

    def on_notification(self, msg: dict):
        self.notifLog.append(str(msg))

    def on_powerlinestate(self, msg: dict):
        freq = msg.get('powerline_freq_hz'); 
        if freq is not None:
            try: self.freqLabel.setText(f"{float(freq):.3f}")
            except Exception: self.freqLabel.setText(str(freq))


    def on_devicestate_extras(self, msg: dict):
        maybe_time = msg.get('total_run_time')
        if maybe_time is not None: self.runTimeLabel.setText(f"{maybe_time}")

    def on_devicestate(self, ds: dict):
        self._set_indicator(self.runningIndicator, bool(ds.get('running')))
        self._set_indicator(self.softwareRunEnable, bool(ds.get('software_run_enable')))
        self._set_indicator(self.hardwareRunEnable, bool(ds.get('hardware_run_enable')))
        if 'current_address' in ds: self.currentAddrLabel.setText(str(ds['current_address']))
        if 'final_address' in ds: self.finalAddrLabel.setText(str(ds['final_address']))
        if 'accept_hardware_trigger' in ds:
            val = str(ds['accept_hardware_trigger'])
            idx = self.acceptHwCombo.findText(val)
            if idx >= 0:
                old = self.acceptHwCombo.blockSignals(True); self.acceptHwCombo.setCurrentIndex(idx); self.acceptHwCombo.blockSignals(old)
        if 'trigger_on_powerline' in ds:
            old = self.waitCheckbox.blockSignals(True); self.waitCheckbox.setChecked(bool(ds['trigger_on_powerline'])); self.waitCheckbox.blockSignals(old)
        if 'powerline_trigger_delay' in ds:
            old = self.delaySpin.blockSignals(True); self.delaySpin.setValue(float(ds['powerline_trigger_delay'])); self.delaySpin.blockSignals(old)
        if 'notify_when_run_finished' in ds:
            old = self.notifyFinishedCheckbox.blockSignals(True); self.notifyFinishedCheckbox.setChecked(bool(ds['notify_when_run_finished'])); self.notifyFinishedCheckbox.blockSignals(old)
        if 'notify_on_main_trig_out' in ds:
            old = self.notifyMainTrigOutCheckbox.blockSignals(True); self.notifyMainTrigOutCheckbox.setChecked(bool(ds['notify_on_main_trig_out'])); self.notifyMainTrigOutCheckbox.blockSignals(old)
        if 'clock_source' in ds:
            self.refClockLabel.setText(f"{ds['clock_source']}")
        if 'trigger_out_length' in ds:
            old = self.trigOutLenSpin.blockSignals(True); self.trigOutLenSpin.setValue(float(ds['trigger_out_length'])); self.trigOutLenSpin.blockSignals(old)
        if 'trigger_out_delay' in ds:
            old = self.trigOutDelaySpin.blockSignals(True); self.trigOutDelaySpin.setValue(float(ds['trigger_out_delay'])); self.trigOutDelaySpin.blockSignals(old)
        if 'state' in ds and isinstance(ds['state'], int):
            self._apply_state_to_buttons(self._state_to_bools(ds['state']))
        ### Can get rif of all the if --- in statements. I know the form of the dictionary. It ALWAYS contains the same emenets.

    def closeEvent(self, ev):
        try:
            self.request_timer.stop()
            if self.pg and self.pg.is_open(): self.pg.disconnect()
        finally:
            super().closeEvent(ev)


def main():
    app = QApplication(sys.argv)
    w = MainWindow(); w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
