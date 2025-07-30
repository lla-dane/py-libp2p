import argparse
import logging
import os

import base58
import multiaddr
from ping import send_ping
import trio

from examples.kademlia.kademlia import connect_to_bootstrap_nodes
from libp2p import new_host
from libp2p.custom_types import TProtocol
from libp2p.identity.identify.identify import (
    ID as IDENTIFY_PROTOCOL_ID,
    parse_identify_response,
)
from libp2p.kad_dht.kad_dht import DHTMode, KadDHT
from libp2p.kad_dht.utils import create_key_from_binary
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.tools.async_service.trio_service import background_trio_service

logger = logging.getLogger("kademlia-example")
logging.disable(logging.CRITICAL)


PING_PROTOCOL_ID = TProtocol("/ipfs/ping/1.0.0")
NUM_CLIENTS = 5
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_ADDR_LOG = os.path.join(SCRIPT_DIR, "server_node_addr.txt")
FAILURE_LOG_FILE = os.path.join(SCRIPT_DIR, "client_failures.log")
GET_VALUE_LATENCY_LOG = os.path.join(SCRIPT_DIR, "get_value_latency.log")
FIND_PROVIDERS_LATENCY_LOG = os.path.join(SCRIPT_DIR, "find_providers_latency.log")


def log_failure(message: str) -> None:
    try:
        with open(FAILURE_LOG_FILE, "a") as f:
            f.write(f"{message}\n")
    except Exception as e:
        print(f"Failed to log error: {e}")


def log_latency(filepath: str, latency_ms: int) -> None:
    try:
        with open(filepath, "a") as f:
            f.write(f"{latency_ms}\n")
    except Exception as e:
        print(f"Failed to log latency to {filepath}: {e}")


def compute_average_latency(filepath: str) -> float:
    if not os.path.exists(filepath):
        return 0.0
    try:
        with open(filepath) as f:
            values = [int(line.strip()) for line in f if line.strip()]
        return sum(values) / len(values) if values else 0.0
    except Exception as e:
        print(f"Failed to compute average from {filepath}: {e}")
        return 0.0


def load_server_addrs() -> list[str]:
    """Load all server multiaddresses from the log file."""
    if not os.path.exists(SERVER_ADDR_LOG):
        return []
    try:
        with open(SERVER_ADDR_LOG) as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Failed to load server addresses: {e}")
        return []


async def run_single_client_dht(destination: str, bootstrap_addr: str = None) -> None:
    bootstrap_nodes = []

    server_addrs = load_server_addrs()
    if server_addrs:
        logger.info(f"Loaded {len(server_addrs)} server addresses from log")
        bootstrap_nodes.append(server_addrs[0])
    else:
        logger.warning("No server addresses found in the log file")

    if bootstrap_addr:
        bootstrap_nodes.append(bootstrap_addr)

    listen_addr = multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0")
    host = new_host(listen_addrs=[listen_addr])

    async with host.run(listen_addrs=[listen_addr]):
        await connect_to_bootstrap_nodes(host, bootstrap_nodes)
        dht = KadDHT(host, DHTMode.CLIENT)

        # Take all peer_ids from the host and add them to the dht
        for peer_id in host.get_peerstore().peer_ids():
            await dht.routing_table.add_peer(peer_id)

        logger.info(f"Connected to bootstrap nodes: {host.get_connected_peers()}")

        # Start the DHT service
        async with background_trio_service(dht):
            await trio.sleep(0.3)

            logger.info(f"DHT service started in {DHTMode.CLIENT} mode")
            val_key = create_key_from_binary(b"benchmark_key")
            val_in = b"Input value"
            content_key = create_key_from_binary(b"DHT_content_key")

            # retrieve the value
            logger.info("Looking up key: %s", base58.b58encode(val_key).decode())

            # GET_VALUE
            start = trio.current_time()
            val_out = await dht.get_value(val_key)
            get_latency = trio.current_time() - start
            get_latency_ms = int(get_latency * 1000)

            success = val_out == val_in

            if success is False:
                log_failure(
                    f"[DHT GET] Failed to retrieve correct value from {destination}"
                )

            log_latency(GET_VALUE_LATENCY_LOG, get_latency_ms)
            print(f"DHT GET success={success} with latency: {get_latency_ms}ms")

            # FIND PROVIDERS
            logger.info("Looking for servers of content: ", content_key.hex())
            start = trio.current_time()
            providers = await dht.provider_store.find_providers(content_key)
            find_latency = trio.current_time() - start
            find_latency_ms = int(find_latency * 1000)

            if len(providers) == 0:
                log_failure(
                    f"[DHT FIND_PROVIDERS] No providers found for content_key at {destination}"
                )

            log_latency(FIND_PROVIDERS_LATENCY_LOG, find_latency_ms)
            print(f"Found {len(providers)} providers, latency_ms={find_latency_ms}ms")


async def run_single_client_ping(destination: str) -> None:
    listen_addr = multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0")
    host = new_host(listen_addrs=[listen_addr])

    async with host.run(listen_addrs=[listen_addr]):
        try:
            maddr = multiaddr.Multiaddr(destination)
            info = info_from_p2p_addr(maddr)

            await host.connect(info)

            stream = await host.new_stream(info.peer_id, [PING_PROTOCOL_ID])
            await send_ping(stream)

        except Exception as e:
            print(f"[Client Error: {e}")
            err_msg = f"[Ping Error] Could not connect or ping {destination}: {str(e)}"
            log_failure(err_msg)


async def run_single_client_identify(destination: str) -> None:
    listen_addr = multiaddr.Multiaddr("ip4/0.0.0.0/tcp/0")
    host = new_host()

    async with host.run(listen_addrs=[listen_addr]):
        maddr = multiaddr.Multiaddr(destination)
        info = info_from_p2p_addr(maddr)

        await host.connect(info)

        stream = await host.new_stream(info.peer_id, (IDENTIFY_PROTOCOL_ID,))
        try:
            from libp2p.utils.varint import read_length_prefixed_protobuf

            response = await read_length_prefixed_protobuf(stream, False)
            full_response = response

            await stream.close()

            identify_msg = parse_identify_response(full_response)
            assert identify_msg is not None
            print("IDENTIFY SUCCESS")
        except Exception as e:
            print(f"Identify protocol error: {str(e)}")
            err_msg = f"[Identify Error] Could not identify {destination}: {str(e)}"
            log_failure(err_msg)


async def run(destination: str, peer_count: int) -> None:
    if os.path.exists(FAILURE_LOG_FILE):
        os.remove(FAILURE_LOG_FILE)

    async with trio.open_nursery() as nursery:
        for i in range(peer_count):
            nursery.start_soon(run_single_client_ping, destination)
            nursery.start_soon(run_single_client_identify, destination)
            nursery.start_soon(run_single_client_dht, destination)

    # This block only runs AFTER all nursery tasks finish
    if os.path.exists(FAILURE_LOG_FILE):
        print("\n=== CLIENT FAILURES ===")
        with open(FAILURE_LOG_FILE) as f:
            for line in f:
                print(line.strip())
        print("========================\n")
    else:
        print("\n✅ All client operations succeeded.\n")

    # Compute and print average latencies
    avg_get = compute_average_latency(GET_VALUE_LATENCY_LOG)
    avg_find = compute_average_latency(FIND_PROVIDERS_LATENCY_LOG)

    print(f"\n📊 Averaged over {peer_count} peers:")
    print(f"➡️  Average get_value latency: {avg_get:.2f} ms")
    print(f"➡️  Average find_providers latency: {avg_find:.2f} ms\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--destination",
        type=str,
        required=True,
        help="Destination multiaddr (/ip4/127.0.0.1/tcp/8000/p2p/...)",
    )

    parser.add_argument(
        "-p",
        "--peer_count",
        type=int,
        required=False,
        default=NUM_CLIENTS,
        help="Destination multiaddr (/ip4/127.0.0.1/tcp/8000/p2p/...)",
    )
    args = parser.parse_args()

    try:
        trio.run(run, args.destination, args.peer_count)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
