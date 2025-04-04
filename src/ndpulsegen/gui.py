import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QComboBox, QTextEdit, QLabel, QAction, QToolBar, QScrollArea
)
from PyQt5.QtCore import QTimer
from serial.serialutil import PortNotOpenError

# Relative imports from within the package.
from .comms import PulseGenerator
from .transcode import encode_instruction  # Exposed for end users if needed

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Signal Generator GUI")
        # Create an instance of PulseGenerator.
        self.pg = PulseGenerator()
        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        # Toolbar actions.
        checkDevicesAction = QAction("Check Devices", self)
        checkDevicesAction.triggered.connect(self.check_devices)
        connectAction = QAction("Connect", self)
        connectAction.triggered.connect(self.connect_device)
        disconnectAction = QAction("Disconnect", self)
        disconnectAction.triggered.connect(self.disconnect_device)

        toolbar = QToolBar("Main Toolbar")
        toolbar.addAction(checkDevicesAction)
        toolbar.addAction(connectAction)
        toolbar.addAction(disconnectAction)
        self.addToolBar(toolbar)

        # Device selection combo box.
        self.deviceComboBox = QComboBox()

        # Create a grid layout with 24 toggle buttons.
        self.outputButtons = []
        grid = QGridLayout()
        for i in range(24):
            btn = QPushButton(str(i))
            btn.setCheckable(True)
            btn.clicked.connect(self.make_toggle_handler(i))
            self.outputButtons.append(btn)
            row = i // 6  # 6 buttons per row.
            col = i % 6
            grid.addWidget(btn, row, col)

        # Create text areas for different message types.
        # Device Info (Echo): Overwritten on each update.
        self.deviceInfoTextEdit = QTextEdit()
        self.deviceInfoTextEdit.setReadOnly(True)
        # Device State.
        self.deviceStateTextEdit = QTextEdit()
        self.deviceStateTextEdit.setReadOnly(True)
        # Powerline State.
        self.powerlineStateTextEdit = QTextEdit()
        self.powerlineStateTextEdit.setReadOnly(True)
        # Extras.
        self.extrasTextEdit = QTextEdit()
        self.extrasTextEdit.setReadOnly(True)
        # Notifications.
        self.notificationsTextEdit = QTextEdit()
        self.notificationsTextEdit.setReadOnly(True)
        # Print messages.
        self.printTextEdit = QTextEdit()
        self.printTextEdit.setReadOnly(True)
        # Errors.
        self.errorLogTextEdit = QTextEdit()
        self.errorLogTextEdit.setReadOnly(True)

        # Layout for message displays with labels.
        messageLayout = QVBoxLayout()
        messageLayout.addWidget(QLabel("Device Info (Echo)"))
        messageLayout.addWidget(self.deviceInfoTextEdit)
        messageLayout.addWidget(QLabel("Device State"))
        messageLayout.addWidget(self.deviceStateTextEdit)
        messageLayout.addWidget(QLabel("Powerline State"))
        messageLayout.addWidget(self.powerlineStateTextEdit)
        messageLayout.addWidget(QLabel("Extras"))
        messageLayout.addWidget(self.extrasTextEdit)
        messageLayout.addWidget(QLabel("Notifications"))
        messageLayout.addWidget(self.notificationsTextEdit)
        messageLayout.addWidget(QLabel("Print Messages"))
        messageLayout.addWidget(self.printTextEdit)
        messageLayout.addWidget(QLabel("Errors"))
        messageLayout.addWidget(self.errorLogTextEdit)

        # Put the message area inside a scrollable widget.
        messageWidget = QWidget()
        messageWidget.setLayout(messageLayout)
        scrollArea = QScrollArea()
        scrollArea.setWidget(messageWidget)
        scrollArea.setWidgetResizable(True)

        # Assemble the upper part: device selection and toggle buttons.
        upperLayout = QVBoxLayout()
        upperLayout.addWidget(self.deviceComboBox)
        upperLayout.addLayout(grid)

        # Main layout: upper part and scrollable message area.
        mainLayout = QVBoxLayout()
        mainLayout.addLayout(upperLayout)
        mainLayout.addWidget(scrollArea)

        centralWidget = QWidget()
        centralWidget.setLayout(mainLayout)
        self.setCentralWidget(centralWidget)

    def make_toggle_handler(self, channel):
        def handler(checked):
            state = [btn.isChecked() for btn in self.outputButtons]
            try:
                self.pg.write_static_state(state)
            except Exception as e:
                self.errorLogTextEdit.append("Error sending static state: " + str(e))
        return handler

    def check_devices(self):
        try:
            devices_info = self.pg.get_connected_devices()
            validated = devices_info.get('validated_devices', [])
            self.deviceComboBox.clear()
            for dev in validated:
                display_text = f"SN: {dev['serial_number']} on {dev['comport']}"
                self.deviceComboBox.addItem(display_text, dev)
            if not validated:
                self.errorLogTextEdit.append("No validated devices found.")
            else:
                self.notificationsTextEdit.append("Devices updated.")
        except Exception as e:
            self.errorLogTextEdit.append("Error checking devices: " + str(e))

    def connect_device(self):
        index = self.deviceComboBox.currentIndex()
        if index >= 0:
            device = self.deviceComboBox.itemData(index)
            serial_number = device['serial_number']
            try:
                self.pg.connect(serial_number)
                self.notificationsTextEdit.append("Connected to device.")
            except Exception as e:
                self.errorLogTextEdit.append("Error connecting: " + str(e))

    def disconnect_device(self):
        try:
            self.pg.disconnect()
            self.notificationsTextEdit.append("Disconnected.")
        except Exception as e:
            self.errorLogTextEdit.append("Error during disconnect: " + str(e))

    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(100)  # Update every 100 ms

    def update_status(self):
        try:
            if not self.pg.ser.is_open:
                return
            # Request all state messages in one command.
            self.pg.write_action(request_state=True, request_powerline_state=True, request_state_extras=True)
        except Exception as e:
            self.errorLogTextEdit.append("Error requesting state: " + str(e))
            return

        # Process each queue.
        # Device State
        latest_devicestate = None
        while not self.pg.msgin_queues['devicestate'].empty():
            latest_devicestate = self.pg.msgin_queues['devicestate'].get_nowait()
        if latest_devicestate:
            if 'state' in latest_devicestate:
                bit_array = latest_devicestate['state']
                for i, btn in enumerate(self.outputButtons):
                    btn.blockSignals(True)
                    btn.setChecked(bool(bit_array[i]))
                    btn.blockSignals(False)
            self.deviceStateTextEdit.setText(str(latest_devicestate))
        
        # Powerline State
        latest_powerline = None
        while not self.pg.msgin_queues['powerlinestate'].empty():
            latest_powerline = self.pg.msgin_queues['powerlinestate'].get_nowait()
        if latest_powerline:
            self.powerlineStateTextEdit.setText(str(latest_powerline))

        # Extras
        latest_extras = None
        while not self.pg.msgin_queues['devicestate_extras'].empty():
            latest_extras = self.pg.msgin_queues['devicestate_extras'].get_nowait()
        if latest_extras:
            self.extrasTextEdit.setText(str(latest_extras))
        
        # Device Info (Echo): Overwrite with the most recent echo message.
        latest_echo = None
        while not self.pg.msgin_queues['echo'].empty():
            latest_echo = self.pg.msgin_queues['echo'].get_nowait()
        if latest_echo:
            comport = self.pg.ser.port if self.pg.ser.is_open else "Not connected"
            info_str = (f"Comport: {comport}\n"
                        f"Echoed Byte: {latest_echo.get('echoed_byte')}\n"
                        f"Device Type: {latest_echo.get('device_type')}\n"
                        f"Hardware Version: {latest_echo.get('hardware_version')}\n"
                        f"Firmware Version: {latest_echo.get('firmware_version')}\n"
                        f"Serial Number: {latest_echo.get('serial_number')}")
            self.deviceInfoTextEdit.setText(info_str)

        # Notifications: Append all new notifications.
        while not self.pg.msgin_queues['notification'].empty():
            notif = self.pg.msgin_queues['notification'].get_nowait()
            self.notificationsTextEdit.append(str(notif))

        # Print messages: Append.
        while not self.pg.msgin_queues['print'].empty():
            msg = self.pg.msgin_queues['print'].get_nowait()
            self.printTextEdit.append(str(msg))

        # Error messages: Append from the 'error' queue.
        while not self.pg.msgin_queues['error'].empty():
            err = self.pg.msgin_queues['error'].get_nowait()
            self.errorLogTextEdit.append(str(err))

        # Bytes dropped: Append as errors.
        while not self.pg.msgin_queues['bytes_dropped'].empty():
            bd = self.pg.msgin_queues['bytes_dropped'].get_nowait()
            self.errorLogTextEdit.append("Bytes Dropped: " + str(bd))

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
