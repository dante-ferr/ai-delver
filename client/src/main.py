from bootstrap import *
from app_manager import app_manager
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

def main():
    app_manager.start_editor()


if __name__ == "__main__":
    main()
