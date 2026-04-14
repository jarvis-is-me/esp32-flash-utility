import threading

from esptool.logger import log, TemplateLogger
import sys
import queue

from PySide6.QtCore import QObject, Signal

class _LoggerSignals(QObject):
    """
    Class to emit signals to which our GUI can connect slots to lets say update a progress bar
    """
    log_emit = Signal(str, tuple, dict)
    update_progress_bar = Signal(float)

signal = _LoggerSignals()

# Dont instantiate manually / more than once
class CustomLogger(TemplateLogger):

    def print(self, message="", *args, **kwargs):
        _log_queue.put((message,args,kwargs))
        # signal.log_emit.emit(message, args, kwargs)

    def note(self, message):
        self.print(f"NOTE: {message}")

    def warning(self, message):
        self.print(f"WARNING: {message}")

    def error(self, message):
        self.print(message, file=sys.stderr)

    def stage(self, finish=False):
        # Collapsible stages not needed in this example
        pass

    def progress_bar(
            self,
            cur_iter,
            total_iters,
            prefix = "",
            suffix = "",
            bar_length: int = 30,
    ):
        # Progress bars replaced with simple percentage output in this example
        percent = 100 * (cur_iter / float(total_iters))
        # signal.update_progress_bar.emit(percent)
        percent_string = f"{percent:.1f}"
        if percent >= 100:
            self.print(f"Finished: {percent_string}%")
        else:
            self.print(f"{prefix} {suffix} {percent_string}%")

    def set_verbosity(self, verbosity):
        # Set verbosity level not needed in this example
        pass

_log_queue = queue.Queue()

def _printer_thread():
    while True:
        message, args, kwargs = _log_queue.get()
        print(f"{message}", *args, **kwargs)

_printer_worker = threading.Thread(target=_printer_thread, daemon=True)
_printer_worker.start()
print("logging worker thread started")

# Replace the default logger with the custom logger
log.set_logger(CustomLogger())

# From now on, all esptool output will be redirected through the custom logger
# Your code here ...
