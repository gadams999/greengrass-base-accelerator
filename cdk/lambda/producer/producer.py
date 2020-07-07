# Greengrass lambda source
# Add events to local stream maanager

import os
import json
import logging
import time
import greengrasssdk
from greengrasssdk.stream_manager import (
    StreamManagerClient,
    ReadMessagesOptions,
    NotEnoughMessagesException,
    MessageStreamDefinition,
    StrategyOnFull,
    ExportDefinition,
    IoTAnalyticsConfig,
    InvalidRequestException,
    StreamManagerException,
    Persistence,
)

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

gg_client = greengrasssdk.client("iot-data")
client = StreamManagerClient()


try:
    # The LocalDataStream is low priority source for incoming sensor data and
    # aggregator function.
    client.create_message_stream(
        MessageStreamDefinition(
            name="LocalDataStream",  # Required.
            max_size=268435456,  # Default is 256 MB.
            stream_segment_size=16777216,  # Default is 16 MB.
            time_to_live_millis=None,  # By default, no TTL is enabled.
            strategy_on_full=StrategyOnFull.OverwriteOldestData,  # Required.
            persistence=Persistence.File,  # Default is File.
            flush_on_write=False,  # Default is false.
        )
    )
except StreamManagerException as e:
    logger.error(f"Error creating message stream: {e}")
    pass
except Exception as e:
    logger.error(f"General exception error: {e}")
    pass

# publish data to the stream

while True:
    try:
        # Incoming event is already byte encoded
        event = f"this is the data for the data a timestamp: {int(time.time())}"
        client.append_message(stream_name="LocalDataStream", data=event.encode("utf-8"))
        logger.info(f"appended message: {event}")
    except Exception as e:
        logger.error(f"Error appending: {e}")
    time.sleep(5)


def main(event, context):
    """Called per invoke of the function or delivery of message via subscription"""
    return
