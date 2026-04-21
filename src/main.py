import sys
import queue
import multiprocessing

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QWidget,
    QProgressBar,
    QVBoxLayout,
    QFrame,
    QPushButton,
    QLabel
)
from PySide6.QtCore import Qt, QTimer
from qt_material import apply_stylesheet

import logic
from logic import BoardType, FilesystemType, BaudrateType, BaseType
from logic import serial_port_enumerator

from littlefs import LittleFS, UserContext

from widgets import SideBarMiniContainers, TextView, ErrorPage, FileExplorer

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

        self.default_settings = {
            "offset" : 0x8000,
            "baudrate": BaudrateType.FAST,
        }
        # This is the file explorer widget we can reference
        self.explorer= None

        # The progressbar at the bottom
        self.progress_bar = None

        # These are used to communicate with any spawned esptool process
        """
        Format for the communicate queue - 
        {
            'type':'LOG'/'FINISHED'/'PROGRESS'/'ERROR',
            'content' : "key for log messages",
            'payload' : 'final result of the operation , like bytearray',
            'value' : 'progress values , usually % in float or int'
            'error' : 'cant connect to board'
        }
        """
        self.communication_pipe = multiprocessing.Queue()
        self.process = None
        self.polling_timer = QTimer()

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
        button = QPushButton("Read")
        button.clicked.connect(self.handle_read_flash)
        layout = QHBoxLayout()
        layout.addWidget(button)
        bar.setLayout(layout)
        return bar

    def make_sidebar(self) -> QFrame:
        sidebar = QFrame()
        temp = QFrame()
        temp_layout = QHBoxLayout()
        heading = QLabel("Device configuration")
        button = QPushButton("Refresh")
        button.clicked.connect(self.handle_refresh)
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

    def make_explorer(self, fs) -> FileExplorer:
        self.explorer = FileExplorer(fs=fs)
        return self.explorer

    def make_mid_section(self) -> QFrame:
        sidebar = self.make_sidebar()
        explorer = self.make_explorer(None)
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
        self.progress_bar = QProgressBar(minimum=0, maximum=100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        layout.addWidget(self.progress_bar)
        bar.setLayout(layout)
        return bar

    def handle_refresh(self) -> None:
        """
        when user clicks the refresh button, this method will change the following things in the sidebar
            1. refresh the COM ports data in combobox
            2. Prepopulate the baud rate field to the default 921600 rate in combobox
            3. Prepopulate the offset field to the default 0x8000 address in spinbox
        """
        # refresh the ports list
        port_container = self.data_containers["port"]
        port_container.dropdown.clear()
        ports = serial_port_enumerator(True)
        for port in ports:
            insertable = BaseType(f"{port.device} - ({port.description})", port.device)
            port_container.dropdown.addItem(insertable.display_name,insertable)

        # set baud rate to default
        baud_container = self.data_containers["baudrate"]
        baud_index = baud_container.dropdown.findData(self.default_settings["baudrate"])
        if baud_index != -1:
            baud_container.dropdown.setCurrentIndex(baud_index)

        # set offset to 0x8000
        offset_container = self.data_containers["offset"]
        offset_container.spinbox.setValue(self.default_settings["offset"])

    def handle_read_flash_updates(self):
        try:
            data = self.communication_pipe.get(timeout=0.01)
        except queue.Empty:
            return

        if data['type'] == 'PROGRESS':
            self.progress_bar.setValue(data['value'])
        elif data['type'] == 'FINISHED':
            self.polling_timer.stop()
            self.polling_timer.timeout.disconnect()
            self.progress_bar.hide()
            fs = LittleFS(
                context=UserContext(buffer=data['payload'][0]),
                block_size=4096,
                block_count= data['payload'][1] // 4096,
                read_size=16,
                prog_size=16,
            )
            self.explorer.update_view(fs)
            self.top_bar.setEnabled(True)
        elif data['type'] == 'ERROR':
            self.polling_timer.stop()
            self.polling_timer.timeout.disconnect()
            self.progress_bar.reset()
            self.progress_bar.hide()
            self.explorer.show_error_page(data['error'])
            self.top_bar.setEnabled(True)
        elif data['type'] == 'LOG':
            print(data['content'])

    def handle_read_flash(self):
        """
        Reads and displays the filesystem information
        :return: None
        """
        self.top_bar.setDisabled(True)
        self.progress_bar.show()
        try:
            port = self.data_containers["port"].dropdown.currentData().command_value
            board = self.data_containers["board"].dropdown.currentData()
            baudrate = self.data_containers["baudrate"].dropdown.currentData()

            config = logic.ESPConfigType(board, baudrate, port)

            filesystem = self.data_containers["fstype"].dropdown.currentData()
            offset = self.data_containers["offset"].spinbox.value()

        except (AttributeError, ValueError) as e:
            self.explorer.show_error_page(f"Configuration Error - Make sure you have selected correct port and board configuartion")
            self.progress_bar.hide()
            self.top_bar.setEnabled(True)
            return

        self.process = multiprocessing.Process(target=logic.get_filesystem, args=(self.communication_pipe , config, offset, filesystem))
        self.process.start()
        self.polling_timer.start(100)
        self.polling_timer.timeout.connect(self.handle_read_flash_updates)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    apply_stylesheet(app, theme='dark_purple.xml')
    window.show()
    sys.exit(app.exec())
