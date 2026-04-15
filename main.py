import sys
import queue
import multiprocessing

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QHBoxLayout,
    QMainWindow,
    QFrame,
    QVBoxLayout,
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QProgressBar,
    QPlainTextEdit
)
from PySide6.QtCore import Qt, QTimer
from qt_material import apply_stylesheet

from serial import SerialException
from esptool import FatalError
from littlefs.errors import LittleFSError

import logic
from logic import BoardType, FilesystemType, BaudrateType, BaseType
from logic import serial_port_enumerator

from littlefs import LittleFS, UserContext

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
            self.spinbox.clear()
            self.layout.addWidget(self.spinbox)

        else:
            self.dropdown = QComboBox()
            self.dropdown.setPlaceholderText(" ")
            for item in dropdown_selections:
                self.dropdown.addItem(item.display_name, item)
            self.layout.addWidget(self.dropdown)


        self.setLayout(self.layout)

class TextView(QFrame):
    def __init__(self, back_button_callback):
        super().__init__()

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(back_button_callback)

        layout = QVBoxLayout()
        layout.addWidget(self.back_button)
        layout.addWidget(self.preview)

        self.setLayout(layout)

class ErrorPage(QFrame):
    """
    A simple class to show raised exceptions as errors in our stack view widget
    and an option to go back
    """
    def __init__(self, button_callback):
        super().__init__()

        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)

        self.button = QPushButton("ok")
        self.button.clicked.connect(button_callback)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)

class FileExplorer(QStackedWidget):
    """
    Class that combines the tree view of filesystem as well as
    the page that shows the actual file text and manages the switching between them
    """
    def __init__(self, fs: LittleFS|None):
        super().__init__()
        self.fs = fs

        # Make a tree to view the whole filesyste
        self.tree = QTreeWidget()
        self.addWidget(self.tree) # add tree at index 0
        self.tree.setHeaderLabels(["Name", "Size"])

        self.populate_tree()
        self.tree.itemDoubleClicked.connect(self.handle_file_show)

        # Make a page to view the contents of a clicked file
        self.file_viewer = TextView(self.handle_back_button)
        self.addWidget(self.file_viewer) # add file viewer at index 1

        # Make a default page to be shown at the start of the app
        self.blank = QLabel("""
        No file system read yet.\n Configure the board settings in the sidebar and press Read to read the flash and show the filesystem 
        """)
        self.blank.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(self.blank) # add a blank page at index 2

        self.error_page = ErrorPage(self.handle_back_button)
        self.addWidget(self.error_page) # add an error page at index 3

    def populate_tree(self):
        """
        Populates the tree view if filesystem exists and sets the index to 1
        If we don't yet have a filesystem (start of the program) , show blank page
        :return: None
        """
        if self.fs is not None:
            # This dict stores a reference to all QTreeWidgetItems that are folders
            # so later when we are doing fs.walk in the loop , we can grab the parent widget and
            # add children to it (The fs.walk is top down , so we read all top level files and folders before
            # we go inside any folder on the next iterations)
            ref_dict = {}
            for root, dirs, files in self.fs.walk("."):

                if root == ".":
                    parent_widget = self.tree
                else:
                    parent_widget = ref_dict[root]

                for d in dirs:
                    item = QTreeWidgetItem(parent_widget)
                    item.setText(0, d)
                    full_path = f"{root}/{d}"
                    ref_dict[full_path] = item
                    # data format ( dir/file , absolute path to dir/file)
                    item.setData(0, Qt.ItemDataRole.UserRole, ('dir', full_path) )

                for f in files:
                    item = QTreeWidgetItem(parent_widget)
                    full_path = f"{root}/{f}"
                    item.setText( 0, f )
                    file_size = self.fs.stat(full_path).size
                    item.setText( 1, f"{file_size/1000:.3f} kb" )
                    # data format ( dir/file , absolute path to dir/file)
                    item.setData(0, Qt.ItemDataRole.UserRole, ('file', full_path))
            self.tree.expandAll()
            self.setCurrentIndex(0) # shows tree view
        else:
            self.setCurrentIndex(2) # shows blank page


    def handle_file_show(self, widget_item, index):
        """
        slot that handles switching between the file tree view and showing the clicked file contents
        :param widget_item: implicit slot argument which is the QTreeWidgetItem
        :param index: the index of the clicked part
        :return:
        """
        item_type, full_path = widget_item.data(0,Qt.ItemDataRole.UserRole)
        if item_type == 'dir':
            print(f"directory {full_path} was clicked")
        else:
            print(f"file {full_path} was clicked")

            # Read the file and switch to the file text view
            with self.fs.open(full_path, 'r') as f:
                self.file_viewer.preview.setPlainText(f.read())
            self.setCurrentIndex(1)

    def handle_back_button(self):
        """
        callback function that switches from individual file view back to tree view of all files
        :return: None
        """
        self.setCurrentIndex(0)

    def update_view(self, fs):
        """
        Function to be called when the filesystem is done fetching from the ESP32
        and we need to show it in the tree view.
        :param fs: the filesystem to be shown
        :return:
        """
        self.fs = fs
        self.tree.clear()
        self.populate_tree()

    def show_error_page(self, error_message):
        """
        handles the process of showing any raised exception as error on the error page
        :param error_message: user friendly string stating what went wrong
        :return: None
        """
        self.error_page.label.setText(error_message)
        self.setCurrentIndex(3)


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
        # This is the explorer widget we can reference
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

        self.process = multiprocessing.Process(target=logic.get_filesystem, args=(self.communication_pipe ,config, offset, filesystem))
        self.process.start()
        self.polling_timer.start(100)
        self.polling_timer.timeout.connect(self.handle_read_flash_updates)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    apply_stylesheet(app, theme='dark_purple.xml')
    window.show()
    sys.exit(app.exec())
