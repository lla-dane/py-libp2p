import trio
import logging

from libp2p.custom_types import TProtocol
from libp2p.network.stream.net_stream import INetStream
from libp2p.pubsub.floodsub import FloodSub
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub
from libp2p.tools.async_service.trio_service import background_trio_service

PUBSUB_PROTOCOL_ID = TProtocol("/meshsub/1.0.0")
PUBSUB_TOPIC = "benchmark-topic"
MESSAGE_TIMEOUT = 5

logger = logging.getLogger("pubsub-benchmark")


def setup_pubsub(host, use_gossipsub=True):
    """Set up pubsub with either GossipSub or FloodSub router."""
    if use_gossipsub:
        # Use simpler GossipSub configuration suitable for basic testing
        router = GossipSub(
            [PUBSUB_PROTOCOL_ID],
            degree=1,  # Reduced degree for simpler mesh
            degree_low=1,
            degree_high=2,
            time_to_live=60,  # Longer TTL
            gossip_window=3,
            gossip_history=5,
            heartbeat_initial_delay=1.0,  # Longer initial delay
            heartbeat_interval=60,  # Longer heartbeat interval
        )
    else:
        router = FloodSub([PUBSUB_PROTOCOL_ID])
    
    pubsub = Pubsub(host, router)
    return pubsub, router


async def handle_pubsub_messages(subscription, received_messages, expected_count=1):
    """Handle incoming pubsub messages and track them."""
    count = 0
    while count < expected_count:
        try:
            with trio.fail_after(MESSAGE_TIMEOUT):
                message = await subscription.get()
                received_messages.append(message.data.decode('utf-8'))
                peer_id = message.from_id
                logger.info(f"Received message from {peer_id.hex()[:8]}: {message.data.decode('utf-8')}")
                count += 1
        except trio.TooSlowError:
            logger.warning(f"Timeout waiting for message {count + 1}/{expected_count}")
            break
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            break


async def send_pubsub_message(pubsub, topic, message):
    """Send a message to a pubsub topic."""
    try:
        await pubsub.publish(topic, message.encode('utf-8'))
        logger.info(f"Published message: {message}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish message: {e}")
        return False


async def test_pubsub_communication(pubsub, topic, test_message="Hello from pubsub test"):
    """Test pubsub communication by subscribing and publishing."""
    received_messages = []
    
    # Subscribe to the topic
    subscription = await pubsub.subscribe(topic)
    logger.info(f"Subscribed to topic: {topic}")
    
    # Wait a bit for subscription to propagate
    await trio.sleep(0.5)
    
    # Start message handler in background
    async with trio.open_nursery() as nursery:
        nursery.start_soon(handle_pubsub_messages, subscription, received_messages, 1)
        
        # Wait a bit more then publish
        await trio.sleep(0.2)
        success = await send_pubsub_message(pubsub, topic, test_message)
        
        # Wait for message to be received
        await trio.sleep(1.0)
        nursery.cancel_scope.cancel()
    
    return success and len(received_messages) > 0 and received_messages[0] == test_message 