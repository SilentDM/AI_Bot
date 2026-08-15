# gui_logger.py
import sys

class GuiOutput:
    def __init__(self, callback):
        self.callback = callback

    def write(self, text):
        text = text.strip()
        if text:
            try:
                self.callback(text)
            except Exception:
                pass  

    def flush(self):
        pass