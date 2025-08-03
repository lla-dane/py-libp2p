import argparse
import logging
import os

import multiaddr
from ping import handle_ping
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
from libp2p.transport.quic.utils import create_quic_multiaddr

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


async def run(transport: str) -> None:
    if transport == "tcp":
        listen_addr = multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/8000")
    else:
        listen_addr = create_quic_multiaddr("0.0.0.0", 8000, "/quic")

    host = new_host(listen_addrs=[listen_addr])

    async with host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
        nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)

        # DHT
        add_str = f"{host.get_addrs()[0]}"
        dht = KadDHT(host, DHTMode.SERVER)

        for peer_id in host.get_peerstore().peer_ids():
            await dht.routing_table.add_peer(peer_id)
        save_server_addr(add_str)

        nursery.start_soon(run_dht_service, dht)
        await trio.sleep(2)

        # Ping
        host.set_stream_handler(PING_PROTOCOL_ID, handle_ping)
        print("PING SETUP COMPLETE...")

        # Identify
        identify_handler = identify_handler_for(host, False)
        host.set_stream_handler(IDENTIFY_PROTOCOL_ID, identify_handler)
        print("IDENTIFY SETUP COMPLETE...")

        if transport == "tcp":
            print(f"python client.py -d {host.get_addrs()[0]} -p 10 -s 10")  # Local
            print(
                f"python client.py -d /ip4/15.188.49.159/tcp/8000/p2p/{host.get_id()} -b /ip4/15.188.49.159/tcp/8000/p2p/{host.get_id()} -p 10 -s 10"
            )  # AWS EC2 instance
        else:
            print(
                f"python client.py -t 1 -d {host.get_addrs()[0]} -p 10 -s 10"
            )  # Local
            print(
                f"python client.py -t 1 -d /ip4/15.188.49.159/udp/8000/quic/p2p/{host.get_id()} -b /ip4/15.188.49.159/udp/8000/quic/p2p/{host.get_id()} -p 10 -s 10"
            )
        await trio.sleep_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--transport",
        type=str,
        default="tcp",
        help="Destination multiaddr (/ip4/127.0.0.1/tcp/8000/p2p/...)",
    )

    args = parser.parse_args()

    try:
        trio.run(run, args.transport)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
