from esptool.logger import log, TemplateLogger
import sys

_log_queue = None

def set_logger_queue(queue):
    global _log_queue
    _log_queue = queue

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

# Dont instantiate manually / more than once
class CustomLogger(TemplateLogger):

    def print(self, message, *args, **kwargs):
        if _log_queue is None:
            print("NOLOGQ: ", message, args, kwargs)
            return

        if isinstance(message, dict):
            _log_queue.put(message)
        else:
            for arg in args:
                message += str(arg)
            _log_queue.put(
                {
                    'type':'LOG',
                    'content': message
                }
            )

    def note(self, message):
        if _log_queue is None:
            self.print(f" {message}")
        else:
            self.print(
                {
                    'type': 'LOG',
                    'content': message
                }
            )

    def warning(self, message):
        if _log_queue is None:
            self.print(f" {message}")
        else:
            self.print(
                {
                    'type': 'LOG',
                    'content': message
                }
            )

    def error(self, message):
        if _log_queue is None:
            self.print(f" {message}")
        else:
            self.print(
                {
                    'type': 'ERROR',
                    'error': message
                }
            )

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
        # Calculate percentage of progress
        percent = int(100 * (cur_iter / float(total_iters)))
        if _log_queue is None:
            self.print(f" {percent}%")
        else:
            self.print(
                {
                    'type': 'PROGRESS',
                    'value': percent
                }
            )


    def set_verbosity(self, verbosity):
        # Set verbosity level not needed in this example
        pass





# Replace the default logger with the custom logger
log.set_logger(CustomLogger())

# From now on, all esptool output will be redirected through the custom logger
# Your code here ...
