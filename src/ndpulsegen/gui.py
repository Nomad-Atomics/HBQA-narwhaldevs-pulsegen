# gui.py (rewritten)
import sys
import struct
import time
import threading
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from PyQt5.QtCore import (
    Qt, QObject, QThread, pyqtSignal, QTimer, QSettings, QSize
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QComboBox, QLabel, QAction, QToolBar, QGroupBox, QCheckBox,
    QTextEdit, QDoubleSpinBox, QLineEdit, QMessageBox
)

import serial
import serial.tools.list_ports

# NOTE: this file re-implements PulseGenerator; transcode is still imported.
# If gui.py lives in a package with transcode.py, keep the relative import:
from . import transcode


# -------------------------------
# Worker thread for serial reads
# -------------------------------
class SerialWorker(QObject):
    # Generic and typed signals from decoded messages
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
        # Try to break out of a blocking read if supported
        try:
            self.ser.cancel_read()
        except Exception:
            pass

    def run(self):
        try:
            while self._running:
                try:
                    b = self.ser.read(1)  # blocking with timeout
                except serial.serialutil.SerialException as ex:
                    self.errorOccurred.emit(str(ex))
                    break

                if not b:  # timeout
                    continue

                ts = time.time()
                msg_id, = struct.unpack('B', b)
                dinfo = transcode.msgin_decodeinfo.get(msg_id)
                if not dinfo:
                    # Unknown id; drop one byte
                    self.bytesDropped.emit(msg_id, ts)
                    continue

                remaining = dinfo['message_length'] - 1
                try:
                    payload = self.ser.read(remaining)
                except serial.serialutil.SerialException as ex:
                    self.errorOccurred.emit(str(ex))
                    break

                if len(payload) != remaining:
                    self.bytesDropped.emit(msg_id, ts)
                    continue

                try:
                    decoded = dinfo['decode_function'](payload)
                except Exception as ex:
                    self.errorOccurred.emit(f"Decode failed for id {msg_id}: {ex}")
                    continue

                decoded['timestamp'] = ts
                decoded['message_type'] = dinfo['message_type']
                self.messageReceived.emit(decoded)

                # Emit typed channels for convenience
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


# ------------------------------------
# PulseGenerator: I/O API + QThread
# ------------------------------------
class PulseGenerator(QObject):
    # Re-emit worker signals at this level as well (useful for UI to connect to pg.*)
    devicestate = pyqtSignal(dict)
    powerlinestate = pyqtSignal(dict)
    devicestate_extras = pyqtSignal(dict)
    notification = pyqtSignal(dict)
    echo = pyqtSignal(dict)
    easyprint = pyqtSignal(dict)
    bytesDropped = pyqtSignal(int, float)
    errorOccurred = pyqtSignal(str)
    connected = pyqtSignal(str)     # port
    disconnected = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        # pyserial port
        self.ser = serial.Serial()
        self.ser.timeout = 0.1         # 100 ms read timeout
        self.ser.write_timeout = 1
        self.ser.baudrate = 12000000

        self._write_lock = threading.Lock()
        self._thread: Optional[QThread] = None
        self._worker: Optional[SerialWorker] = None

        self.serial_number_save: Optional[int] = None
        self.device_type: Optional[int] = None  # may be set from echo response

        # VID/PID for filtering (from existing comms.py)
        self._valid_vid = 1027
        self._valid_pid = 24592

    # ---------- Connection Management ----------
    def is_open(self) -> bool:
        return bool(self.ser and self.ser.is_open)

    def _start_reader(self):
        # Create and start the worker thread that does blocking reads
        self._thread = QThread()
        self._worker = SerialWorker(self.ser)
        self._worker.moveToThread(self._thread)

        # Wire signals out
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
            self._thread.quit()
            self._thread.wait(1500)
        self._worker = None
        self._thread = None

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
        """
        Try to connect to a device. If serial_number provided, we first enumerate and match it.
        If port is provided, we try that port directly.
        Returns True if connected.
        """
        if self.is_open():
            # Already open; reset streams
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass
            return True

        target_port = None
        device_meta = None

        if serial_number is not None or port is None:
            # enumerate and validate
            devices = self.get_connected_devices()['validated_devices']
            for d in devices:
                if (serial_number is not None and d.get('serial_number') == serial_number) or \
                   (serial_number is None and port is None):
                    target_port = d['comport']
                    device_meta = d
                    break
        if port is not None and target_port is None:
            target_port = port

        if not target_port:
            return False

        # Open
        self.ser.port = target_port
        self.ser.open()
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        self._start_reader()

        # Remember serial number if known
        if device_meta:
            self.serial_number_save = device_meta.get('serial_number')
            self.device_type = device_meta.get('device_type')

        return True

    # ---------- Device Enumeration / Validation ----------
    def get_connected_devices(self) -> Dict[str, Any]:
        """
        Scan COM ports filtered by VID/PID, open each briefly, send echo,
        and validate response. Returns dict with 'validated_devices' and 'unvalidated_devices'.
        """
        validated_devices: List[Dict[str, Any]] = []
        unvalidated_devices: List[str] = []

        comports = list(serial.tools.list_ports.comports())
        valid_ports = [cp for cp in comports
                       if hasattr(cp, 'vid') and hasattr(cp, 'pid')
                       and cp.vid == self._valid_vid and cp.pid == self._valid_pid]

        for cp in valid_ports:
            ok, meta = self._try_handshake(cp.device)
            if ok and meta:
                meta['comport'] = cp.device
                validated_devices.append(meta)
            else:
                unvalidated_devices.append(cp.device)

        return {'validated_devices': validated_devices, 'unvalidated_devices': unvalidated_devices}

    def _try_handshake(self, port: str, timeout_s: float = 1.0) -> (bool, Optional[Dict[str, Any]]):
        """
        Open the port, flush, send echo, and synchronously read a single message (no worker thread).
        """
        s = serial.Serial()
        s.port = port
        s.baudrate = self.ser.baudrate
        s.timeout = 0.2
        s.write_timeout = 0.5
        try:
            s.open()
        except Exception:
            return False, None
        try:
            s.reset_input_buffer()
            s.reset_output_buffer()

            # Echo handshake
            check_byte = bytes([209])  # 0xD1
            s.write(transcode.encode_echo(check_byte))

            t0 = time.time()
            while time.time() - t0 < timeout_s:
                b = s.read(1)
                if not b:
                    continue
                msg_id, = struct.unpack('B', b)
                dinfo = transcode.msgin_decodeinfo.get(msg_id)
                if not dinfo:
                    # skip a stray byte
                    continue
                remaining = dinfo['message_length'] - 1
                payload = s.read(remaining)
                if len(payload) != remaining:
                    continue
                decoded = dinfo['decode_function'](payload)
                if dinfo['message_type'] == 'echo' and decoded.get('echoed_byte') == check_byte:
                    # Minimal metadata for the device list
                    return True, {
                        'device_type': decoded.get('device_type'),
                        'hardware_version': decoded.get('hardware_version'),
                        'firmware_version': decoded.get('firmware_version'),
                        'serial_number': decoded.get('serial_number'),
                    }
            return False, None
        finally:
            try:
                s.close()
            except Exception:
                pass

    # ---------- Writes (non-blocking; safe for GUI thread) ----------
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
        # If transcode has encode_instructions, prefer batching; otherwise write individually.
        if hasattr(transcode, 'encode_instructions'):
            self.write_command(transcode.encode_instructions(instructions))
        else:
            for instr in instructions:
                self.write_command(instr)


# ------------------------------------
# Main Window
# ------------------------------------
class MainWindow(QMainWindow):
    POLL_MS = 100

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pulse Generator Controller")
        self.resize(1100, 800)

        self.settings = QSettings("ndpulsegen", "gui")

        # Core I/O object
        self.pg = PulseGenerator(self)

        # Connect PG signals
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

        # --- Top toolbar actions ---
        toolbar = QToolBar("Main")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        self.refreshAction = QAction("Refresh Devices", self)
        self.refreshAction.triggered.connect(self.check_devices)
        toolbar.addAction(self.refreshAction)

        self.connectAction = QAction("Connect", self)
        self.connectAction.triggered.connect(self.connect_device)
        toolbar.addAction(self.connectAction)

        self.disconnectAction = QAction("Disconnect", self)
        self.disconnectAction.triggered.connect(self.disconnect_device)
        toolbar.addAction(self.disconnectAction)

        # --- Device chooser ---
        self.deviceComboBox = QComboBox()

        # --- Channel widgets: label above each button ---
        self.channelWidgets = []  # list of (QLineEdit, QPushButton)
        buttonsLayout = QGridLayout()
        for i in range(24):
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(2, 2, 2, 2)
            vbox.setSpacing(2)
            # Label editor
            edit = QLineEdit()
            edit.setPlaceholderText(f"Ch {i}")
            saved = self.settings.value(f"channels/{i}", "")
            edit.setText(saved)
            edit.editingFinished.connect(lambda i=i, e=edit: self.settings.setValue(f"channels/{i}", e.text()))
            vbox.addWidget(edit)
            # Toggle button
            btn = QPushButton(str(i))
            btn.setCheckable(True)
            btn.clicked.connect(self.make_toggle_handler(i))
            vbox.addWidget(btn)
            self.channelWidgets.append((edit, btn))
            row, col = divmod(i, 8)
            buttonsLayout.addWidget(container, row, col)

        topLayout = QVBoxLayout()
        topLayout.addWidget(self.deviceComboBox)
        topLayout.addLayout(buttonsLayout)

        # --- Status group ---
        statusBox = QGroupBox("Status")
        statusLayout = QGridLayout(statusBox)
        statusLayout.addWidget(QLabel("Running:"), 0, 0)
        self.runningIndicator = QLabel()
        self.runningIndicator.setFixedSize(16, 16)
        statusLayout.addWidget(self.runningIndicator, 0, 1)
        statusLayout.addWidget(QLabel("Run enable - Software:"), 1, 0)
        self.softwareRunEnable = QLabel(); self.softwareRunEnable.setFixedSize(16, 16)
        statusLayout.addWidget(self.softwareRunEnable, 1, 1)
        statusLayout.addWidget(QLabel("Run enable - Hardware:"), 2, 0)
        self.hardwareRunEnable = QLabel(); self.hardwareRunEnable.setFixedSize(16, 16)
        statusLayout.addWidget(self.hardwareRunEnable, 2, 1)
        statusLayout.addWidget(QLabel("Current address:"), 3, 0)
        self.currentAddrLabel = QLabel("—"); statusLayout.addWidget(self.currentAddrLabel, 3, 1)
        statusLayout.addWidget(QLabel("Final address:"), 4, 0)
        self.finalAddrLabel = QLabel("—"); statusLayout.addWidget(self.finalAddrLabel, 4, 1)
        statusLayout.addWidget(QLabel("Total run time:"), 5, 0)
        self.runTimeLabel = QLabel("—"); statusLayout.addWidget(self.runTimeLabel, 5, 1)

        # --- Trigger In group ---
        inBox = QGroupBox("Trigger in")
        inLayout = QGridLayout(inBox)
        inLayout.addWidget(QLabel("Accept hardware trigger:"), 0, 0)
        self.acceptHwCombo = QComboBox()
        self.acceptHwCombo.addItems(["never", "always", "single_run", "once"])
        self.acceptHwCombo.currentTextChanged.connect(self.on_accept_hw_changed)
        inLayout.addWidget(self.acceptHwCombo, 0, 1)
        inLayout.addWidget(QLabel("Wait for powerline:"), 1, 0)
        self.waitCheckbox = QCheckBox()
        self.waitCheckbox.stateChanged.connect(self.on_wait_changed)
        inLayout.addWidget(self.waitCheckbox, 1, 1)
        inLayout.addWidget(QLabel("Delay after powerline (ms):"), 2, 0)
        self.delaySpin = QDoubleSpinBox()
        self.delaySpin.setDecimals(3)
        self.delaySpin.setRange(0.0, 10000.0)
        self.delaySpin.valueChanged.connect(self.on_delay_changed)
        inLayout.addWidget(self.delaySpin, 2, 1)

        # --- Trigger Out group (basic) ---
        outBox = QGroupBox("Trigger out")
        outLayout = QGridLayout(outBox)
        outLayout.addWidget(QLabel("Notify when finished:"), 0, 0)
        self.notifyFinishedCheckbox = QCheckBox()
        self.notifyFinishedCheckbox.stateChanged.connect(self.on_notify_finished_changed)
        outLayout.addWidget(self.notifyFinishedCheckbox, 0, 1)

        # --- Info / Notifications ---
        infoBox = QGroupBox("Info")
        infoLayout = QGridLayout(infoBox)
        infoLayout.addWidget(QLabel("Incoming messages:"), 0, 0)
        self.notifLog = QTextEdit()
        self.notifLog.setReadOnly(True)
        infoLayout.addWidget(self.notifLog, 1, 0, 1, 2)

        # --- Arrange group boxes ---
        groupsLayout = QGridLayout()
        groupsLayout.addWidget(statusBox, 0, 0)
        groupsLayout.addWidget(inBox, 0, 1)
        groupsLayout.addWidget(outBox, 1, 0)
        groupsLayout.addWidget(infoBox, 1, 1)

        # --- Combine top + groups ---
        centralLayout = QVBoxLayout()
        centralLayout.addLayout(topLayout)
        centralLayout.addLayout(groupsLayout)
        central = QWidget()
        central.setLayout(centralLayout)
        self.setCentralWidget(central)

        # Timers
        self.request_timer = QTimer(self)
        self.request_timer.setInterval(self.POLL_MS)
        self.request_timer.timeout.connect(self.poll_status)

        # Initial device list
        self.check_devices()

    # ---------- UI Helpers ----------
    @staticmethod
    def _set_indicator(widget: QLabel, on: bool):
        widget.setStyleSheet(
            "background-color: green; border-radius: 8px;" if on else
            "background-color: red; border-radius: 8px;"
        )

    def _state_to_bools(self, state_val: int) -> List[bool]:
        # Convert a 24-bit state (LSB = ch0) to a list of booleans
        return [bool((state_val >> i) & 1) for i in range(24)]

    def _apply_state_to_buttons(self, state_bools: List[bool]):
        for i, (_, btn) in enumerate(self.channelWidgets):
            old = btn.blockSignals(True)
            btn.setChecked(bool(state_bools[i]))
            btn.blockSignals(old)

    # ---------- UI -> Device ----------
    def make_toggle_handler(self, channel: int):
        def handler(checked: bool):
            state = [btn.isChecked() for _, btn in self.channelWidgets]
            try:
                self.pg.write_static_state(state)
            except Exception as e:
                self.notifLog.append(f"Error sending static state: {e}")
        return handler

    def on_accept_hw_changed(self, text: str):
        try:
            self.pg.write_device_options(accept_hardware_trigger=text)
        except Exception as e:
            self.notifLog.append(f"Error setting accept_hardware_trigger: {e}")

    def on_wait_changed(self, state: int):
        try:
            self.pg.write_powerline_trigger_options(trigger_on_powerline=bool(state))
        except Exception as e:
            self.notifLog.append(f"Error setting wait for powerline: {e}")

    def on_delay_changed(self, value: float):
        try:
            # Assuming transcode expects this delay in milliseconds (adjust if it's in ticks)
            self.pg.write_powerline_trigger_options(powerline_trigger_delay=value)
        except Exception as e:
            self.notifLog.append(f"Error setting powerline delay: {e}")

    def on_notify_finished_changed(self, state: int):
        try:
            self.pg.write_device_options(notify_when_run_finished=bool(state))
        except Exception as e:
            self.notifLog.append(f"Error setting notify when finished: {e}")

    # ---------- Device / Connection actions ----------
    def check_devices(self):
        try:
            devs = self.pg.get_connected_devices().get('validated_devices', [])
            self.deviceComboBox.clear()
            for d in devs:
                label = f"SN {d.get('serial_number')} | FW {d.get('firmware_version')} | {d.get('comport')}"
                self.deviceComboBox.addItem(label, d)
            self.notifLog.append("Devices updated." if devs else "No devices found.")
        except Exception as e:
            self.notifLog.append(f"Error checking devices: {e}")

    def connect_device(self):
        idx = self.deviceComboBox.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Connect", "No device selected.")
            return
        dev = self.deviceComboBox.itemData(idx)
        try:
            ok = self.pg.connect(serial_number=dev.get('serial_number'))
            if ok:
                self.notifLog.append(f"Connected to {dev.get('comport')} (SN {dev.get('serial_number')}).")
                self.request_timer.start()
            else:
                self.notifLog.append("Connect failed: device not found.")
        except Exception as e:
            self.notifLog.append(f"Error connecting: {e}")

    def disconnect_device(self):
        try:
            self.request_timer.stop()
            self.pg.disconnect()
            self.notifLog.append("Disconnected.")
        except Exception as e:
            self.notifLog.append(f"Error disconnecting: {e}")

    def poll_status(self):
        # Fire-and-forget request; responses are handled by worker signals
        if not self.pg.is_open():
            return
        try:
            self.pg.write_action(
                request_state=True,
                request_powerline_state=True,
                request_state_extras=True
            )
        except Exception as e:
            self.notifLog.append(f"Error requesting state: {e}")

    # ---------- Worker signal slots (Device -> UI) ----------
    def on_connected(self, port: str):
        self.statusBar().showMessage(f"Connected on {port}", 3000)

    def on_disconnected(self):
        self.statusBar().showMessage("Disconnected", 3000)

    def on_error(self, message: str):
        self.notifLog.append(f"[ERROR] {message}")

    def on_bytes_dropped(self, msg_id: int, ts: float):
        self.notifLog.append(f"[DROP {msg_id}] at {ts:.3f}")

    def on_echo(self, msg: dict):
        self.notifLog.append(f"[ECHO] {msg}")

    def on_easyprint(self, msg: dict):
        self.notifLog.append(f"[PRINT] {msg.get('easy_printed_value', msg)}")

    def on_notification(self, msg: dict):
        # Example fields: address_notify / trigger_notify / finished_notify
        self.notifLog.append(f"[NOTIFY] {msg}")

    def on_powerlinestate(self, msg: dict):
        # Could update wait/period fields here if provided
        pass

    def on_devicestate_extras(self, msg: dict):
        # If extras include run time or other info, show it
        maybe_time = msg.get('total_run_time', None)
        if maybe_time is not None:
            self.runTimeLabel.setText(f"{maybe_time}")

    def on_devicestate(self, ds: dict):
        # Update lamps
        self._set_indicator(self.runningIndicator, bool(ds.get('running')))
        self._set_indicator(self.softwareRunEnable, bool(ds.get('software_run_enable')))
        self._set_indicator(self.hardwareRunEnable, bool(ds.get('hardware_run_enable')))

        # Update addresses
        if 'current_address' in ds:
            self.currentAddrLabel.setText(str(ds['current_address']))
        if 'final_address' in ds:
            self.finalAddrLabel.setText(str(ds['final_address']))

        # Update UI controls to reflect device settings, without echo/loop
        if 'accept_hardware_trigger' in ds:
            val = str(ds['accept_hardware_trigger'])
            idx = self.acceptHwCombo.findText(val)
            if idx >= 0:
                old = self.acceptHwCombo.blockSignals(True)
                self.acceptHwCombo.setCurrentIndex(idx)
                self.acceptHwCombo.blockSignals(old)

        # If 'state' is present, reflect channel button checks
        if 'state' in ds and isinstance(ds['state'], int):
            self._apply_state_to_buttons(self._state_to_bools(ds['state']))

    # ---------- Close handling ----------
    def closeEvent(self, ev):
        try:
            self.request_timer.stop()
            if self.pg and self.pg.is_open():
                self.pg.disconnect()
        finally:
            super().closeEvent(ev)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
