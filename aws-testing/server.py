import logging
import os

import multiaddr
from ping import handle_ping
from pubsub import setup_pubsub, PUBSUB_TOPIC
import trio

from libp2p import (
    new_host,
)
from libp2p.custom_types import (
    TProtocol,
)
from libp2p.identity.identify.identify import (
    ID as IDENTIFY_PROTOCOL_ID,
    identify_handler_for,
)
from libp2p.kad_dht.kad_dht import DHTMode, KadDHT
from libp2p.kad_dht.utils import create_key_from_binary
from libp2p.tools.async_service.trio_service import background_trio_service

PING_PROTOCOL_ID = TProtocol("/ipfs/ping/1.0.0")
PING_LENGTH = 32
RESP_TIMEOUT = 60
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_ADDR_LOG = os.path.join(SCRIPT_DIR, "server_node_addr.log")

logger = logging.getLogger("kademlia-example")
logging.disable(logging.CRITICAL)


def save_server_addr(addr: str) -> None:
    """Append the server's multiaddress to the log file."""
    try:
        with open(SERVER_ADDR_LOG, "w") as f:
            f.write(addr + "\n")
        logger.info(f"Saved server address to log: {addr}")
    except Exception as e:
        logger.error(f"Failed to save server address: {e}")


async def run_dht_service(dht: KadDHT) -> None:
    async with background_trio_service(dht):
        await trio.sleep(0.3)

        logger.info(f"DHT service started in {DHTMode.SERVER} mode")
        val_key = create_key_from_binary(b"benchmark_key")
        val_in = b"Input value"
        content_key = create_key_from_binary(b"DHT_content_key")

        # PUT_VALUE
        await dht.put_value(val_key, val_in)

        # CONTENT SERVER
        success = await dht.provider_store.provide(content_key)
        if success:
            logger.info(
                f"Successfully advertised as serverfor content: {content_key.hex()}"
            )
        else:
            logger.warning("Failed to advertise as content server")

        print("DHT SETUP COMPLETE...")
        await trio.sleep_forever()


async def run_pubsub_service(pubsub, router) -> None:
    async with background_trio_service(pubsub):
        async with background_trio_service(router):
            await pubsub.wait_until_ready()
            logger.info("Pubsub service started in server mode")
            
            # Subscribe to the benchmark topic to participate in the network
            subscription = await pubsub.subscribe(PUBSUB_TOPIC)
            logger.info(f"Subscribed to topic: {PUBSUB_TOPIC}")
            
            print("PUBSUB SETUP COMPLETE...")
            
            # Just listen and log incoming messages (no echoing)
            while True:
                try:
                    message = await subscription.get()
                    peer_id = message.from_id
                    data = message.data.decode('utf-8')
                    logger.info(f"Received pubsub message from {peer_id.hex()[:8]}: {data}")
                    
                except Exception as e:
                    logger.error(f"Error in pubsub message handling: {e}")
                    await trio.sleep(1)


async def run() -> None:
    listen_addr = multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/8000")
    host = new_host(listen_addrs=[listen_addr])

    async with host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
        nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)

        # DHT
        add_str = f"{listen_addr}/p2p/{host.get_id()}"
        dht = KadDHT(host, DHTMode.SERVER)

        for peer_id in host.get_peerstore().peer_ids():
            await dht.routing_table.add_peer(peer_id)
        save_server_addr(add_str)

        nursery.start_soon(run_dht_service, dht)
        await trio.sleep(2)

        # Pubsub
        pubsub, router = setup_pubsub(host, use_gossipsub=True)
        nursery.start_soon(run_pubsub_service, pubsub, router)
        await trio.sleep(1)

        # Ping
        host.set_stream_handler(PING_PROTOCOL_ID, handle_ping)
        print("PING SETUP COMPLETE...")

        # Identify
        identify_handler = identify_handler_for(host, False)
        host.set_stream_handler(IDENTIFY_PROTOCOL_ID, identify_handler)
        print("IDENTIFY SETUP COMPLETE...")

        print(
            f"python client.py -d /ip4/0.0.0.0/tcp/8000/p2p/{host.get_id()} -p 10"
        )  # Local
        print(
            f"python client.py -d /ip4/15.188.49.159/tcp/8000/p2p/{host.get_id()} -b /ip4/15.188.49.159/tcp/8000/p2p/{host.get_id()} -p 10"
        )  # AWS EC2 instance
        await trio.sleep_forever()


def main() -> None:
    try:
        trio.run(run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
