import logging
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import Queue
import atexit
from pathlib import Path


class QueueFileLogger:
    def __init__(
        self,
        name: str = "my_app",
        log_file: str = "logs/app.log",
        level: int = logging.INFO,
        fmt: str = "%(asctime)s | %(levelname)s | %(process)d | %(name)s | %(message)s",
    ):
        self.log_queue = Queue(-1)

        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        self.file_handler = logging.FileHandler(log_file)
        self.file_handler.setFormatter(logging.Formatter(fmt))

        self.listener = QueueListener(
            self.log_queue,
            self.file_handler,
            respect_handler_level=True,
        )
        self.listener.start()

        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False

        self.queue_handler = QueueHandler(self.log_queue)
        self.logger.addHandler(self.queue_handler)

        # Graceful shutdown
        atexit.register(self.stop)

    def get_logger(self) -> logging.Logger:
        return self.logger

    def stop(self):
        if self.listener:
            self.listener.stop()

if __name__ == "__main__":
    logger = QueueFileLogger(
    name="my_app",
    log_file="logs/app.log",
    level=logging.INFO,
    ).get_logger()

    logger.info("Application started")
    logger.debug("This will not appear unless level=DEBUG")

