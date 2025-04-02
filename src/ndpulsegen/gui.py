import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout,
    QPushButton, QComboBox, QTextEdit, QAction, QToolBar
)
from PyQt5.QtCore import QTimer
import ndpulsegen  # your module that provides PulseGenerator
from serial.serialutil import PortNotOpenError  # to catch serial errors

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Signal Generator GUI")
        # Create an instance of your PulseGenerator.
        self.pg = ndpulsegen.PulseGenerator()
        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        # Create actions for checking devices, connecting, and disconnecting.
        checkDevicesAction = QAction("Check Devices", self)
        checkDevicesAction.triggered.connect(self.check_devices)
        connectAction = QAction("Connect", self)
        connectAction.triggered.connect(self.connect_device)
        disconnectAction = QAction("Disconnect", self)
        disconnectAction.triggered.connect(self.disconnect_device)

        # Add actions to a toolbar.
        toolbar = QToolBar("Main Toolbar")
        toolbar.addAction(checkDevicesAction)
        toolbar.addAction(connectAction)
        toolbar.addAction(disconnectAction)
        self.addToolBar(toolbar)

        # Device selection combo box.
        self.deviceComboBox = QComboBox()

        # Create a grid layout with 24 toggle buttons (outputs 0 to 23).
        self.outputButtons = []
        grid = QGridLayout()
        for i in range(24):
            btn = QPushButton(str(i))
            btn.setCheckable(True)
            btn.clicked.connect(self.make_toggle_handler(i))
            self.outputButtons.append(btn)
            row = i // 6  # arrange buttons in a grid (6 per row)
            col = i % 6
            grid.addWidget(btn, row, col)

        # Text edit to display state and additional info.
        self.stateTextEdit = QTextEdit()
        self.stateTextEdit.setReadOnly(True)

        # Assemble the central widget.
        centralWidget = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.deviceComboBox)
        layout.addLayout(grid)
        layout.addWidget(self.stateTextEdit)
        centralWidget.setLayout(layout)
        self.setCentralWidget(centralWidget)

    def make_toggle_handler(self, channel):
        # Returns a handler function for toggling a specific channel.
        def handler(checked):
            # When the user clicks a button, build the overall output state.
            # (Assumes that write_static_state accepts a list of booleans or 0/1 values.)
            state = [btn.isChecked() for btn in self.outputButtons]
            try:
                self.pg.write_static_state(state)
            except Exception as e:
                self.stateTextEdit.append("Error sending state: " + str(e))
        return handler

    def check_devices(self):
        # Call get_connected_devices() and update the combo box with validated devices.
        try:
            devices_info = self.pg.get_connected_devices()
            validated = devices_info.get('validated_devices', [])
            self.deviceComboBox.clear()
            for dev in validated:
                # For display, show the serial number and COM port.
                display_text = f"SN: {dev['serial_number']} on {dev['comport']}"
                self.deviceComboBox.addItem(display_text, dev)
            if not validated:
                self.stateTextEdit.append("No validated devices found.")
            else:
                self.stateTextEdit.append("Devices updated.")
        except Exception as e:
            self.stateTextEdit.append("Error checking devices: " + str(e))

    def connect_device(self):
        # Connect to the device selected in the combo box.
        index = self.deviceComboBox.currentIndex()
        if index >= 0:
            device = self.deviceComboBox.itemData(index)
            serial_number = device['serial_number']
            try:
                self.pg.connect(serial_number)
                self.stateTextEdit.append("Connected to device.")
            except Exception as e:
                self.stateTextEdit.append(f"Error connecting: {e}")

    def disconnect_device(self):
        try:
            self.pg.disconnect()
            self.stateTextEdit.append("Disconnected.")
        except Exception as e:
            self.stateTextEdit.append("Error during disconnect: " + str(e))

    def setup_timer(self):
        # Use a QTimer to periodically update the state.
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(100)  # update every 100 ms

    def update_status(self):
        try:
            # Only try to get state if the port is open.
            if not self.pg.ser.is_open:
                return

            # Poll the pulse generator for new state information.
            state = self.pg.get_state()
            powerline = self.pg.get_powerline_state()
            extras = self.pg.get_state_extras()

            # Update the text display (you might format this better in your final version).
            if state:
                self.stateTextEdit.append(f"State: {state}")
                # If state contains a key (say 'state') representing the digital outputs:
                if 'state' in state:
                    bit_array = state['state']
                    for i, btn in enumerate(self.outputButtons):
                        btn.blockSignals(True)
                        btn.setChecked(bool(bit_array[i]))
                        btn.blockSignals(False)
            if powerline:
                self.stateTextEdit.append(f"Powerline: {powerline}")
            if extras:
                self.stateTextEdit.append(f"Extras: {extras}")
        except PortNotOpenError:
            # If the port is not open, ignore this update cycle.
            pass
        except Exception as e:
            self.stateTextEdit.append("Error during status update: " + str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
