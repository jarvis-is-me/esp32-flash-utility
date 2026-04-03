import sys

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QMainWindow,
    QFrame,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from qt_material import apply_stylesheet

from serial.tools.list_ports_common import ListPortInfo

from logic import BoardType, FilesystemType, BaudrateType, BaseType
from logic import serial_port_enumerator


class SideBarMiniContainers(QFrame):
    def __init__(self, label_string: str, dropdown_selections: list[BaseType], is_hex: bool = False):
        super().__init__()

        self.layout = QVBoxLayout()

        self.label = QLabel(label_string)
        self.layout.addWidget(self.label)

        if is_hex:
            self.spinbox = QSpinBox()
            self.spinbox.setDisplayIntegerBase(16)
            self.spinbox.setPrefix("0x")
            self.spinbox.setRange(0, 0x7FFFFFF)  # Supports 0 - 128MB flash sizes
            self.layout.addWidget(self.spinbox)

        else:
            self.dropdown = QComboBox()
            self.dropdown.setPlaceholderText(" ")
            for item in dropdown_selections:
                self.dropdown.addItem(item.display_name, item)
            self.layout.addWidget(self.dropdown)

            if len(dropdown_selections) > 0:
                self.dropdown.setCurrentIndex(0)

        self.setLayout(self.layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ESP flash utility")
        self.resize(1280, 720)

        # This will store reference to relevant widgets so we can extract their values
        self.data_containers = {
            "board": None,
            "port": None,
            "fstype": None,
            "offset": None,
            "baudrate": None,
        }

        self.main_container = QWidget()

        self.top_bar = self.make_top_bar()
        self.mid_section = self.make_mid_section()
        self.bottom_bar = self.make_bottom_bar()

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.top_bar)
        main_layout.addWidget(self.mid_section)
        main_layout.addWidget(self.bottom_bar)

        self.main_container.setLayout(main_layout)
        self.setCentralWidget(self.main_container)

    def make_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(60)
        return bar

    def make_sidebar(self) -> QFrame:
        sidebar = QFrame()
        temp = QFrame()
        temp_layout = QHBoxLayout()
        heading = QLabel("Device configuration")
        button = QPushButton("Refresh")
        button.pressed.connect(self.handle_refresh)
        temp_layout.addWidget(heading)
        temp_layout.addWidget(button)
        temp.setLayout(temp_layout)

        board_container = SideBarMiniContainers("Board Type", [board for board in BoardType])
        com_container = SideBarMiniContainers("COM Port", serial_port_enumerator())
        filesystem_container = SideBarMiniContainers("Filesystem", [fstype for fstype in FilesystemType])
        offset_container = SideBarMiniContainers("Offset (in hex)", [], True)
        baud_container = SideBarMiniContainers("Baudrate", [baud for baud in BaudrateType])

        self.data_containers["board"] = board_container
        self.data_containers["port"] = com_container
        self.data_containers["fstype"] = filesystem_container
        self.data_containers["offset"] = offset_container
        self.data_containers["baudrate"] = baud_container

        layout = QVBoxLayout()
        layout.addWidget(temp)
        layout.addWidget(com_container)
        layout.addWidget(board_container)
        layout.addWidget(filesystem_container)
        layout.addWidget(baud_container)
        layout.addWidget(offset_container)

        sidebar.setLayout(layout)
        return sidebar

    def make_explorer(self) -> QFrame:
        explorer = QFrame()
        return explorer

    def make_mid_section(self) -> QFrame:
        sidebar = self.make_sidebar()
        explorer = self.make_explorer()
        layout = QHBoxLayout()
        layout.addWidget(sidebar, 20)
        layout.addWidget(explorer, 80)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        container = QFrame()
        container.setLayout(layout)
        return container

    def make_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(30)
        return bar

    def handle_refresh(self) -> None:
        """
        when user clicks the refresh button, this method will change the following things in the sidebar
            1. refresh the COM ports data
            2. Prepopulate the offset field to the default 0x8000 address
            3. Prepopulate the baud rate field to the default 921600 rate
        """
        # refresh the ports list
        port_container = self.data_containers["port"]
        port_container.dropdown.clear()
        ports = serial_port_enumerator(True)
        for port in ports:
            insertable = BaseType(f"{port.device} - ({port.description})", port.device)
            port_container.dropdown.addItem(insertable.display_name,insertable)



app = QApplication(sys.argv)
window = MainWindow()

apply_stylesheet(app, theme='dark_purple.xml')

window.show()
app.exec()
