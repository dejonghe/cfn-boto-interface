import logging

# Setup logger
logger = logging.getLogger('CfnBotoInterface')
logger.setLevel(logging.DEBUG)
console_logger = logging.StreamHandler()
console_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_logger.setFormatter(formatter)
logger.addHandler(console_logger)

