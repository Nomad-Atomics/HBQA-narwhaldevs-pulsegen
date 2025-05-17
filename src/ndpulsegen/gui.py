import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QComboBox, QLabel,
    QAction, QToolBar, QGroupBox, QCheckBox,
    QTextEdit, QDoubleSpinBox, QLineEdit
)
from PyQt5.QtCore import QTimer, QSettings
from serial.serialutil import PortNotOpenError

# Relative imports from within the package
from .comms import PulseGenerator
from .transcode import encode_instruction  # If needed by users

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Signal Generator GUI")
        self.pg = PulseGenerator()
        # QSettings for persistent channel labels
        self.settings = QSettings("YourOrgName", "PulseGenGUI")
        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        # --- Toolbar & device selection ---
        checkDevicesAction = QAction("Check Devices", self)
        checkDevicesAction.triggered.connect(self.check_devices)
        connectAction = QAction("Connect", self)
        connectAction.triggered.connect(self.connect_device)
        disconnectAction = QAction("Disconnect", self)
        disconnectAction.triggered.connect(self.disconnect_device)

        toolbar = QToolBar("Main Toolbar")
        for act in (checkDevicesAction, connectAction, disconnectAction):
            toolbar.addAction(act)
        self.addToolBar(toolbar)

        self.deviceComboBox = QComboBox()

        # --- Channel widgets: label above each button ---
        self.channelWidgets = []  # list of (QLineEdit, QPushButton)
        buttonsLayout = QGridLayout()
        for i in range(24):
            container = QWidget()
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(2,2,2,2)
            vbox.setSpacing(2)
            # Label editor
            edit = QLineEdit()
            edit.setPlaceholderText(f"Ch {i}")
            # Load saved label
            saved = self.settings.value(f"channels/{i}", "")
            edit.setText(saved)
            # Save on edit finished
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
        self.runningIndicator.setFixedSize(16,16)
        statusLayout.addWidget(self.runningIndicator, 0, 1)
        statusLayout.addWidget(QLabel("Run enable - Software:"), 1, 0)
        self.softwareRunEnable = QLabel()
        self.softwareRunEnable.setFixedSize(16,16)
        statusLayout.addWidget(self.softwareRunEnable, 1, 1)
        statusLayout.addWidget(QLabel("Run enable - Hardware:"), 2, 0)
        self.hardwareRunEnable = QLabel()
        self.hardwareRunEnable.setFixedSize(16,16)
        statusLayout.addWidget(self.hardwareRunEnable, 2, 1)
        statusLayout.addWidget(QLabel("Current address:"), 3, 0)
        self.currentAddrLabel = QLabel("—")
        statusLayout.addWidget(self.currentAddrLabel, 3, 1)
        statusLayout.addWidget(QLabel("Final address:"), 4, 0)
        self.finalAddrLabel = QLabel("—")
        statusLayout.addWidget(self.finalAddrLabel, 4, 1)
        statusLayout.addWidget(QLabel("Total run time:"), 5, 0)
        self.runTimeLabel = QLabel("—")
        statusLayout.addWidget(self.runTimeLabel, 5, 1)

        # --- Trigger In group ---
        inBox = QGroupBox("Trigger in")
        inLayout = QGridLayout(inBox)
        inLayout.addWidget(QLabel("Accept hardware trigger:"), 0, 0)
        self.acceptHwCombo = QComboBox()
        self.acceptHwCombo.addItems(["never","always","single_run","once"])
        self.acceptHwCombo.currentTextChanged.connect(self.on_accept_hw_changed)
        inLayout.addWidget(self.acceptHwCombo, 0, 1)
        inLayout.addWidget(QLabel("Wait for powerline:"), 1, 0)
        self.waitCheckbox = QCheckBox()
        self.waitCheckbox.stateChanged.connect(self.on_wait_changed)
        inLayout.addWidget(self.waitCheckbox, 1, 1)
        inLayout.addWidget(QLabel("Delay after powerline (ms):"), 2, 0)
        self.delaySpin = QDoubleSpinBox()
        self.delaySpin.setDecimals(5)
        self.delaySpin.setRange(0.0,10000.0)
        self.delaySpin.valueChanged.connect(self.on_delay_ms_changed)
        inLayout.addWidget(self.delaySpin, 2, 1)

        # --- Synchronisation group ---
        syncBox = QGroupBox("Synchronisation")
        syncLayout = QGridLayout(syncBox)
        syncLayout.addWidget(QLabel("Reference clock:"), 0, 0)
        self.refClockLabel = QLabel("—")
        syncLayout.addWidget(self.refClockLabel, 0, 1)
        syncLayout.addWidget(QLabel("Powerline frequency:"), 1, 0)
        self.plFreqLabel = QLabel("—")
        syncLayout.addWidget(self.plFreqLabel, 1, 1)

        # --- Trigger Out group ---
        outBox = QGroupBox("Trigger out")
        outLayout = QGridLayout(outBox)
        outLayout.addWidget(QLabel("Duration (µs):"), 0, 0)
        self.durationSpin = QDoubleSpinBox()
        self.durationSpin.setDecimals(3)
        self.durationSpin.setRange(0.0,1e6)
        self.durationSpin.valueChanged.connect(self.on_duration_us_changed)
        outLayout.addWidget(self.durationSpin, 0, 1)
        outLayout.addWidget(QLabel("Delay (s):"), 1, 0)
        self.delayOutSpin = QDoubleSpinBox()
        self.delayOutSpin.setDecimals(9)
        self.delayOutSpin.setRange(0.0,1e3)
        self.delayOutSpin.valueChanged.connect(self.on_delay_s_changed)
        outLayout.addWidget(self.delayOutSpin, 1, 1)

        # --- Device info group ---
        infoBox = QGroupBox("Device info")
        infoLayout = QGridLayout(infoBox)
        infoLayout.addWidget(QLabel("Serial Number:"), 0, 0)
        self.serialLabel = QLabel("—")
        infoLayout.addWidget(self.serialLabel, 0, 1)
        infoLayout.addWidget(QLabel("Firmware version:"), 1, 0)
        self.fwLabel = QLabel("—")
        infoLayout.addWidget(self.fwLabel, 1, 1)
        infoLayout.addWidget(QLabel("Hardware version:"), 2, 0)
        self.hwLabel = QLabel("—")
        infoLayout.addWidget(self.hwLabel, 2, 1)
        infoLayout.addWidget(QLabel("Comport:"), 3, 0)
        self.comportLabel = QLabel("—")
        infoLayout.addWidget(self.comportLabel, 3, 1)

        # --- Notifications group ---
        notifBox = QGroupBox("Notifications")
        notifLayout = QGridLayout(notifBox)
        self.notifyTrigCheckbox = QCheckBox("Notify on trigger out")
        self.notifyTrigCheckbox.stateChanged.connect(self.on_notify_trig_changed)
        notifLayout.addWidget(self.notifyTrigCheckbox, 0, 0, 1, 2)
        self.notifyFinishedCheckbox = QCheckBox("Notify when finished")
        self.notifyFinishedCheckbox.stateChanged.connect(self.on_notify_finished_changed)
        notifLayout.addWidget(self.notifyFinishedCheckbox, 1, 0, 1, 2)
        notifLayout.addWidget(QLabel("Incoming Notifications:"), 2, 0)
        self.notifLog = QTextEdit()
        self.notifLog.setReadOnly(True)
        notifLayout.addWidget(self.notifLog, 3, 0, 1, 2)

        # --- Arrange group boxes ---
        groupsLayout = QGridLayout()
        groupsLayout.addWidget(statusBox, 0, 0)
        groupsLayout.addWidget(inBox,     0, 1)
        groupsLayout.addWidget(syncBox,   1, 0)
        groupsLayout.addWidget(outBox,    1, 1)
        groupsLayout.addWidget(infoBox,   2, 0)
        groupsLayout.addWidget(notifBox,  2, 1)

        # --- Combine top + groups ---
        centralLayout = QVBoxLayout()
        centralLayout.addLayout(topLayout)
        centralLayout.addLayout(groupsLayout)
        central = QWidget()
        central.setLayout(centralLayout)
        self.setCentralWidget(central)

    # --- UI -> device handlers ---
    def on_accept_hw_changed(self, text):
        try:
            self.pg.write_device_options(accept_hardware_trigger=text)
        except Exception as e:
            self.notifLog.append(f"Error setting accept_hardware_trigger: {e}")

    def on_wait_changed(self, state):
        try:
            self.pg.write_powerline_trigger_options(trigger_on_powerline=bool(state))
        except Exception as e:
            self.notifLog.append(f"Error setting wait for powerline: {e}")

    def on_delay_ms_changed(self, val):
        try:
            self.pg.write_powerline_trigger_options(powerline_trigger_delay=int(val))
        except Exception as e:
            self.notifLog.append(f"Error setting powerline delay: {e}")

    def on_duration_us_changed(self, val):
        try:
            self.pg.write_device_options(trigger_out_length=int(val))
        except Exception as e:
            self.notifLog.append(f"Error setting trigger out duration: {e}")

    def on_delay_s_changed(self, val):
        try:
            self.pg.write_device_options(trigger_out_delay=int(val))
        except Exception as e:
            self.notifLog.append(f"Error setting trigger out delay: {e}")

    def on_notify_trig_changed(self, state):
        try:
            self.pg.write_device_options(notify_on_main_trig_out=bool(state))
        except Exception as e:
            self.notifLog.append(f"Error setting notify on trigger out: {e}")

    def on_notify_finished_changed(self, state):
        try:
            self.pg.write_device_options(notify_when_run_finished=bool(state))
        except Exception as e:
            self.notifLog.append(f"Error setting notify when finished: {e}")

    def make_toggle_handler(self, channel):
        def handler(checked):
            state = [btn.isChecked() for _, btn in self.channelWidgets]
            try:
                self.pg.write_static_state(state)
            except Exception as e:
                self.notifLog.append(f"Error sending static state: {e}")
        return handler

    def check_devices(self):
        try:
            devs = self.pg.get_connected_devices().get('validated_devices', [])
            self.deviceComboBox.clear()
            for d in devs:
                self.deviceComboBox.addItem(f"SN: {d['serial_number']} on {d['comport']}", d)
            self.notifLog.append("Devices updated." if devs else "No devices found.")
        except Exception as e:
            self.notifLog.append(f"Error checking devices: {e}")

    def connect_device(self):
        idx = self.deviceComboBox.currentIndex()
        if idx >= 0:
            dev = self.deviceComboBox.itemData(idx)
            try:
                self.pg.connect(dev['serial_number'])
                self.notifLog.append("Connected.")
            except Exception as e:
                self.notifLog.append(f"Error connecting: {e}")

    def disconnect_device(self):
        try:
            self.pg.disconnect()
            self.notifLog.append("Disconnected.")
        except Exception as e:
            self.notifLog.append(f"Error disconnecting: {e}")

    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(100)

    def update_status(self):
        try:
            if not self.pg.ser.is_open:
                return
            self.pg.write_action(
                request_state=True,
                request_powerline_state=True,
                request_state_extras=True
            )
        except Exception as e:
            self.notifLog.append(f"Error requesting state: {e}")
            return

        # Process devicestate
        ds = None
        while not self.pg.msgin_queues['devicestate'].empty():
            ds = self.pg.msgin_queues['devicestate'].get_nowait()
        if ds:
            self.runningIndicator.setStyleSheet(
                "background-color: green; border-radius: 8px;" if ds.get('running') else
                "background-color: red; border-radius: 8px;"
            )
            self.softwareRunEnable.setStyleSheet(
                "background-color: green; border-radius: 8px;" if ds.get('software_run_enable') else
                "background-color: red; border-radius: 8px;"
            )
            self.hardwareRunEnable.setStyleSheet(
                "background-color: green; border-radius: 8px;" if ds.get('hardware_run_enable') else
                "background-color: red; border-radius: 8px;"
            )
            # Update Trigger In & Out controls from devicestate
            self.acceptHwCombo.setCurrentText(ds.get('accept_hardware_trigger', 'never'))
            self.durationSpin.setValue(ds.get('trigger_out_length', 0))
            self.delayOutSpin.setValue(ds.get('trigger_out_delay', 0))
            self.currentAddrLabel.setText(str(ds.get('current_address', '—')))
            self.finalAddrLabel.setText(str(ds.get('final_address', '—')))

        # Process powerlinestate
        ps = None
        while not self.pg.msgin_queues['powerlinestate'].empty():
            ps = self.pg.msgin_queues['powerlinestate'].get_nowait()
        if ps:
            self.refClockLabel.setText(ps.get('clock_source', '—'))
            self.plFreqLabel.setText(str(ps.get('powerline_period', '—')))
            self.waitCheckbox.setChecked(ps.get('trig_on_powerline', False))
            self.delaySpin.setValue(ps.get('powerline_trigger_delay', 0))

        # Process devicestate_extras
        de = None
        while not self.pg.msgin_queues['devicestate_extras'].empty():
            de = self.pg.msgin_queues['devicestate_extras'].get_nowait()
        if de:
            self.runTimeLabel.setText(str(de.get('run_time', '—')))

        # Process echo (device info)
        echo = None
        while not self.pg.msgin_queues['echo'].empty():
            echo = self.pg.msgin_queues['echo'].get_nowait()
        if echo:
            self.serialLabel.setText(str(echo.get('serial_number', '—')))
            self.fwLabel.setText(echo.get('firmware_version', '—'))
            self.hwLabel.setText(str(echo.get('hardware_version', '—')))
            self.comportLabel.setText(self.pg.ser.port or "—")

        # Notifications & errors
        while not self.pg.msgin_queues['notification'].empty():
            n = self.pg.msgin_queues['notification'].get_nowait()
            self.notifLog.append(str(n))
        while not self.pg.msgin_queues['error'].empty():
            err = self.pg.msgin_queues['error'].get_nowait()
            self.notifLog.append(str(err))
        while not self.pg.msgin_queues['bytes_dropped'].empty():
            bd = self.pg.msgin_queues['bytes_dropped'].get_nowait()
            self.notifLog.append(f"Bytes dropped: {bd}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
