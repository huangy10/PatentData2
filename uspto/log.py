import os

import logging
import logging.config
import yaml

base_dir = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(base_dir, "config/log_config.yaml")) as f:
    global_config = yaml.load(f.read())
    logging.config.dictConfig(global_config)


if __name__ == '__main__':
    logger = logging.getLogger()
    logging.debug("debug")
    logging.warning("warning")
    logging.error("error")

