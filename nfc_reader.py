import errno
import logging
import ndef
import nfc
import os

class NfcDevice():

    def __init__(self, device : str, read_callback: callable = None, write_callback: callable = None) -> None:
        self._read_callback = read_callback
        self._write_callback = write_callback
        self._frontend: nfc.ContactlessFrontend = None
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
        self._device_name = device

    def _listen(self):
        if self._frontend:
            try:
                self._log.debug("Setting NFC frontend to listen.")
                ## this is blocking
                self._frontend.connect(rdwr={"on-connect": self._on_tag_read, "beep-on-connect": False, "on-release": self._on_tag_release})
            except Exception as ex:
                self._log.error(f"Error connecting to NFC frontend: {ex}")

    def _detect_device(self) -> bool:
        try:
            if not self._frontend:
                self._log.debug(f"Attempting to connect to nfc reader :: {self._device_name}")
                self._frontend = nfc.ContactlessFrontend(self._device_name)
                if self._frontend is None:
                    self._log.error("No NFC device found.")
                else:
                    self._log.debug(f"Found NFC device at {self._device_name}")

            return None != self._frontend

        except Exception as ex:
            self._log.error(ex)
            self._frontend = None
            return False

    def _on_tag_read(self, tag):
        success : bool = False
        messages : Array[str] = []
        try:

            if tag.ndef is None:
                self._log.error("NFC Tag has no NDEF data or is not NDEF formatted.")
            else:
                success = True
                self._log.debug("NFC Tag has correct NDEF format")
                for i, record in enumerate(tag.ndef.records):
                    self._log.debug(f"Record {i}: {record}")
                    if isinstance(record, ndef.TextRecord):
                        messages.append(record.text)
                    else:
                        self._log.error(f"[{i + 1}] (non-text record: type={record.type})")

        except Exception as ex:
            self._log.error(ex)

        finally:
            self._read_callback(os.linesep.join(messages))
            return success

    def _on_tag_release(self, tag):
        self._log.debug("NFC Tag removed")

    def destroy(self):
        try:
            self._log.debug("Closing NFC frontend connection.")
            if None != self._frontend:
                self._frontend.close()
            self._log.debug("NFC frontend connection closed.")
        except Exception as ex:
            self._log.error(f"Error closing NFC frontend: {ex}")
    
    def read(self):
        try:
            if not self._read_callback:
                self._log.error("No NFC read callback method defined.")
            elif self._detect_device():
                self._listen()

        except OSError as e:
            if e.errno == errno.ENODEV:
                self._log.error("No NFC device found.")
            else:
                self._log.error(e)
