import logging
import ndef
import nfc
import os
import threading

class NfcDevice():

    # pause between attempts to (re)open the reader, after it is missing or has dropped out
    RETRY_SECONDS : float = 5.0
    # nfcpy checks terminate() between sense rounds; this bounds how long destroy() waits for the thread
    STOP_TIMEOUT : float = 5.0

    def __init__(self, device : str, read_callback: callable = None, write_callback: callable = None) -> None:
        self._read_callback = read_callback
        self._write_callback = write_callback
        self._frontend: nfc.ContactlessFrontend = None
        self._log : logging.Logger = logging.getLogger(__name__)
        self._log.setLevel(os.environ.get("LOGLEVEL", "INFO"))
        self._device_name = device
        self._listening : bool = False
        self._stop : threading.Event = threading.Event()
        self._thread : threading.Thread = None
        self._missing_logged : bool = False

    @property
    def is_listening(self):
        return self._listening

    def start(self) -> None:
        """Start listening on a background thread, reopening the reader whenever it fails or goes missing."""
        if not self._read_callback:
            self._log.error("No NFC read callback method defined.")
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target = self._run, name = "nfc-reader", daemon = True)
        self._thread.start()

    def destroy(self):
        self._log.debug("Stopping NFC reader.")
        self._stop.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout = NfcDevice.STOP_TIMEOUT)
            if self._thread.is_alive():
                self._log.warning("NFC reader thread did not stop in time, closing the reader under it")
        self._close()
        self._log.debug("NFC reader stopped.")

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._open():
                self._listen()
                # connect() only returns when the reader failed or we are stopping; start from a fresh handle
                self._close()
            self._stop.wait(NfcDevice.RETRY_SECONDS)

    def _open(self) -> bool:
        if self._frontend is not None:
            return True
        # nfcpy logs "searching for reader" / "no reader available" itself on every attempt; once we have
        # reported the reader missing, quieten it so retries every few seconds don't flood the log
        clf_log : logging.Logger = logging.getLogger("nfc.clf")
        previous_level : int = clf_log.level
        if self._missing_logged:
            clf_log.setLevel(logging.CRITICAL)
        try:
            if not self._missing_logged:
                self._log.debug(f"Attempting to connect to nfc reader :: {self._device_name}")
            self._frontend = nfc.ContactlessFrontend(self._device_name)
            self._log.info(f"Found NFC device at {self._device_name}")
            self._missing_logged = False
            return True
        except Exception as ex:
            self._frontend = None
            # the reader may be unplugged for a long time: say so once, then keep retrying quietly
            if not self._missing_logged:
                self._log.error(f"No NFC reader available on {self._device_name}, will keep retrying :: {ex}")
                self._missing_logged = True
            return False
        finally:
            clf_log.setLevel(previous_level)

    def _listen(self) -> None:
        try:
            self._log.debug("Setting NFC frontend to listen.")
            self._listening = True
            # blocks until the reader fails (nfcpy logs and returns False on IOError rather than raising)
            # or terminate() returns True
            result = self._frontend.connect(
                rdwr = {"on-connect": self._on_tag_read, "beep-on-connect": False, "on-release": self._on_tag_release},
                terminate = self._stop.is_set,
            )
            if not self._stop.is_set():
                self._log.warning(f"NFC reader stopped listening (connect returned {result!r}), reopening")
        except Exception as ex:
            self._log.error(f"Error listening on NFC frontend: {ex}")
        finally:
            self._listening = False

    def _close(self) -> None:
        frontend, self._frontend = self._frontend, None
        if frontend is None:
            return
        try:
            frontend.close()
        except Exception as ex:
            self._log.error(f"Error closing NFC frontend: {ex}")

    def _on_tag_read(self, tag) -> bool:
        messages : list[str] = []
        try:
            if tag.ndef is None:
                self._log.error("NFC Tag has no NDEF data or is not NDEF formatted.")
            else:
                self._log.debug("NFC Tag has correct NDEF format")
                for i, record in enumerate(tag.ndef.records):
                    self._log.debug(f"Record {i}: {record}")
                    if isinstance(record, ndef.TextRecord):
                        payload : str = record.text.strip()
                        if len(payload) > 0:
                            messages.append(payload)
                    else:
                        self._log.error(f"[{i + 1}] (non-text record: type={record.type})")
        except Exception as ex:
            self._log.error(ex)

        if len(messages) > 0:
            try:
                self._read_callback(os.linesep.join(messages))
            except Exception as ex:
                self._log.error(f"NFC read callback failed: {ex}")

        # Always True: nfcpy then waits for the tag to be removed and carries on listening. Returning False
        # (as for an unreadable / non-NDEF tag) makes connect() return, which used to stop NFC for good.
        return True

    def _on_tag_release(self, tag):
        self._log.debug("NFC Tag removed")
        # falsy, so connect() keeps listening for the next tag
        return None
