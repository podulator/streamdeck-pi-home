import json
import logging
import os
import signal
import sys
import threading
import time
import traceback
import tracemalloc

from app import App
from dotenv import load_dotenv
from envsubst import envsubst
from StreamDeck.DeviceManager import DeviceManager, StreamDeckPlus

profiling : bool = False

def signal_handler(sig, frame):
    try:
        deck.reset()
        deck.close()
        app.destroy()
    finally:
        sys.exit(1)

def read_config(path : str = "config.json") -> dict:
    try:
        with open(path, "r") as f:
            log.info(f"Reading config from {path}")
            confstr = f.read()
            confstr = envsubst(confstr)
            return json.loads(confstr)
    except:
        log.info(f"Couldn't load config from {path}, using a default config.")
        return {
            "creds_path": ".creds",
            "plugins": [
            ], 
            "scrollers": [
                {
                    "name": "my-greeeting", 
                    "class": "text",
                    "config": {
                        "lines": [
                            "Hello,\nHow are you?"
                        ]
                    }
                }
            ]
        }

TEXT_DEFAULTS = {
    "font_path": r"font/terminator.otf", 
    "font_size": 80,
    "background_color": "black",
}

if __name__ == "__main__":

    signal.signal(signal.SIGINT, signal_handler)
    load_dotenv()
    log_level : str = os.environ.get("LOGLEVEL", "INFO")
    logging.basicConfig(level = log_level)
    log = logging.getLogger()

    sys.argv.pop(0)
    if len(sys.argv) > 0:
        config = read_config(sys.argv[0])
    else:
        config = read_config()

    font = config.get("font", None)
    if font is None:
        config["font"] = TEXT_DEFAULTS

    brightness = config.get("brightness", None)
    if brightness is None:
        config["brightness"] = {
            "minimum": 10,
            "press_to_wake": 30
        }

    if profiling:
        tracemalloc.start()

    try:

        creds_path : str = config.get("creds_path", ".creds")
        if not os.path.isdir(creds_path):
            os.mkdir(config["creds_path"])

        deck : StreamDeckPlus = None
        while deck is None:
            streamdecks = DeviceManager().enumerate()
            log.info(f"Found {len(streamdecks)} Stream Deck(s)")

            for i, d in enumerate(streamdecks):
                # This example only works with devices that have screens.
                if (d.DECK_TYPE != 'Stream Deck +'):
                    log.info(deck.DECK_TYPE)
                    log.info("Sorry, this only works with Stream Deck +")
                    continue
                deck = d
                break
            if deck is None:
                log.info("No deck found, sleeping")
                time.sleep(5)
            else:
                try:
                    app = App(deck, config)
                    app.run()
                    # Wait until all application threads have terminated (for this example,
                    # this is when all deck handles are closed).
                    for t in threading.enumerate():
                        if t.name.lower() == "mainthread": continue
                        try:
                            if t._is_stopped:
                                t.join()
                            else: time.sleep(1)
                        except RuntimeError:
                            pass
                        except Exception as ex:
                            log.error(ex.args)

                except Exception as ex:
                    log.error(f"generic error of type : {type(ex.args)}")
                    traceback.print_exc()
                    if (deck and deck.is_open()):
                        deck.reset()
                        deck.close()
                    deck = None
                    time.sleep(5)

        log.info("Deck detection exiting")

    except Exception as ex:
        log.error(ex)
    finally:
        if profiling:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            num_stats = min(10, len(top_stats))
            if num_stats:
                print("[ Top 10 ]")
                for stat in top_stats[:num_stats]:
                    print(stat)
