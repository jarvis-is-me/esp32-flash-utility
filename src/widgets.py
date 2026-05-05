from enum import Enum, IntEnum

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImageReader
from PySide6.QtWidgets import QFrame, QStackedWidget, QPlainTextEdit, QPushButton, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QSpinBox, QComboBox, QLabel, QScrollArea

from littlefs import LittleFS

from logic import BaseType

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
        layout.addWidget(self.preview)
        layout.addWidget(self.back_button)

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

    def show_error(self, error_message):
        self.label.setText(error_message)

class FileExplorer(QStackedWidget):
    """
    Class that combines the tree view of filesystem as well as
    the page that shows the actual file text and manages the switching between them
    """
    class Index(IntEnum):
        ERROR = 0
        BLANK = 1
        TREE = 2
        TEXT_VIEW = 3
        IMAGE_VIEW = 4
        # Any new view will be appended


    def __init__(self, fs: LittleFS|None):
        super().__init__()
        self.fs = fs

        # Error page to show any errors during filesystem navigation
        self.error_page = ErrorPage(self.handle_back_button)
        self.addWidget(self.error_page) # Error page at index 0

        # Make a default page to be shown at the start of the app
        self.blank = QLabel("""
                No file system read yet.\n Configure the board settings in the sidebar and press Read to read the flash and show the filesystem.\n Or upload an existing file system 
                """)
        self.blank.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(self.blank)  # add a blank page at index 1

        # Make a tree to view the whole filesyste
        self.tree = QTreeWidget()
        self.addWidget(self.tree) # add tree at index 2
        self.tree.setHeaderLabels(["Name", "Size"])
        self.populate_tree()
        self.tree.itemDoubleClicked.connect(self.handle_file_show)

        # Make a page to view the contents of a clicked file
        self.text_viewer = TextView(self.handle_back_button)
        self.addWidget(self.text_viewer) # add file viewer at index 3

        self.image_viewer = ImageViewer(self.handle_back_button)
        self.addWidget(self.image_viewer) # Add image viewer at index 4

        self.setCurrentIndex(FileExplorer.Index.BLANK)


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
            self.tree.resizeColumnToContents(0)
            self.setCurrentIndex(FileExplorer.Index.TREE) # shows tree view
        else:
            self.setCurrentIndex(FileExplorer.Index.BLANK) # shows blank page

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

            supported_formats = [ bytes(f.data()).decode().lower() for f in QImageReader.supportedImageFormats() ]
            file_format = full_path.split(".")[-1]

            if file_format in supported_formats:
                # File is an image, show it as image
                with self.fs.open(full_path, 'rb') as f:
                    try:
                        self.image_viewer.set_image(f.read())
                        self.setCurrentIndex(FileExplorer.Index.IMAGE_VIEW)
                    except InvalidImage:
                        self.show_error_page(f"Image format .{file_format} is not supported.")
            else:
                # Read the file and switch to the file text view
                with self.fs.open(full_path, 'r') as f:
                    self.text_viewer.preview.setPlainText(f.read())
                self.setCurrentIndex(FileExplorer.Index.TEXT_VIEW)

    def handle_back_button(self):
        """
        callback function that switches from individual file view back to tree view of all files
        :return: None
        """
        if self.fs is None:
            self.setCurrentIndex(FileExplorer.Index.BLANK)
        else:
            self.setCurrentIndex(FileExplorer.Index.TREE)

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
        self.error_page.show_error(error_message)
        self.setCurrentIndex(FileExplorer.Index.ERROR)

class InvalidImage(Exception):
    pass

class ImageViewer(QFrame):

    def __init__(self, back_button_callback):
        super().__init__()
        self.scrollarea = QScrollArea()

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pixmap = QPixmap()

        self.scrollarea.setWidget(self.label)
        self.scrollarea.setWidgetResizable(True)

        self.button = QPushButton("Back")
        self.button.pressed.connect(back_button_callback)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.scrollarea)
        self.layout.addWidget(self.button)

        self.setLayout(self.layout)

    def set_image(self, image):
        success = self.pixmap.loadFromData(image)
        if not success:
            raise InvalidImage()
        self.label.setPixmap(self.pixmap)

