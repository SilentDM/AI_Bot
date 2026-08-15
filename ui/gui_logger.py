from PySide6.QtCore import QObject, Signal

class GuiOutput(QObject):
    """Captura stdout/stderr e emite um Sinal Qt seguro para a interface."""
    text_written = Signal(str)

    def __init__(self):
        super().__init__()

    def write(self, text):
        text_str = str(text).strip()
        if text_str:
            self.text_written.emit(text_str)

    def flush(self):
        pass