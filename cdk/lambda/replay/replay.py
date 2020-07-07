# Greengrass lambda source
# Replay NNN seconds of messages
import json
import logging
import greengrasssdk

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.WARN)

client = greengrasssdk.client("iot-data")


def startup():
    """Commands to execute during the initial launch of the function"""
    logger.info("Running starting commands")
    # Commands go here


startup()


def main(event, context):
    """Called per invoke of the function or delivery of message via subscription"""
    return
