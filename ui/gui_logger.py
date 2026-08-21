import sys
from PySide6.QtCore import QObject, Signal

class GuiOutput(QObject):
    """Captura stdout/stderr com buffer de linha e emite Sinais Qt thread-safe."""
    text_written = Signal(str)

    def __init__(self):
        super().__init__()
        self._buffer = ""

    def write(self, text):
        if not text:
            return

        self._buffer += str(text)
        if "\n" in self._buffer:
            lines = self._buffer.split("\n")
            # Emite todas as linhas completas antes do ultimo \n
            for line in lines[:-1]:
                clean_line = line.strip()
                if clean_line:
                    self.text_written.emit(clean_line)
            # Mantem o resto no buffer
            self._buffer = lines[-1]

    def flush(self):
        if self._buffer.strip():
            self.text_written.emit(self._buffer.strip())
            self._buffer = ""


_LOGGER_SINGLETON = None

def setup_global_logger(slot_callback):
    """Inicializa o redirecionador de stdout/stderr globalmente e conecta ao slot da interface."""
    global _LOGGER_SINGLETON
    if _LOGGER_SINGLETON is None:
        _LOGGER_SINGLETON = GuiOutput()
        sys.stdout = _LOGGER_SINGLETON
        sys.stderr = _LOGGER_SINGLETON

    try:
        _LOGGER_SINGLETON.text_written.disconnect()
    except Exception:
        pass

    _LOGGER_SINGLETON.text_written.connect(slot_callback)
    return _LOGGER_SINGLETON