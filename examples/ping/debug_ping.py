import argparse
import logging

import multiaddr
import trio

from libp2p import (
    new_host,
)
from libp2p.custom_types import (
    TProtocol,
)
from libp2p.network.stream.net_stream import (
    INetStream,
)
from libp2p.peer.peerinfo import (
    info_from_p2p_addr,
)

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ping_debug.log", mode="w"),
    ],
)
logger = logging.getLogger("ping-debug")

PING_PROTOCOL_ID = TProtocol("/ipfs/ping/1.0.0")
PING_LENGTH = 32
RESP_TIMEOUT = 60


async def handle_ping(stream: INetStream) -> None:
    peer_id = stream.muxed_conn.peer_id
    logger.info(f"[SERVER] New ping stream opened by {peer_id}")
    print(f"[SERVER] New ping stream opened by {peer_id}")

    ping_count = 0
    while True:
        try:
            logger.debug(f"[SERVER] Waiting for ping data from {peer_id}...")
            payload = await stream.read(PING_LENGTH)

            if payload is None or len(payload) == 0:
                logger.info(
                    f"[SERVER] No data received, connection closed by {peer_id}"
                )
                print(f"[SERVER] No data received, connection closed by {peer_id}")
                break

            ping_count += 1
            logger.info(
                f"[SERVER] Received ping {ping_count} from {peer_id}: "
                f"{len(payload)} bytes"
            )
            print(
                f"[SERVER] Received ping {ping_count} from {peer_id}: "
                f"{len(payload)} bytes"
            )

            await stream.write(payload)
            logger.info(f"[SERVER] Responded with pong {ping_count} to {peer_id}")
            print(f"[SERVER] Responded with pong {ping_count} to {peer_id}")

        except Exception as e:
            logger.error(f"[SERVER] Error handling ping from {peer_id}: {e}")
            print(f"[SERVER] Error handling ping from {peer_id}: {e}")
            await stream.reset()
            break

    logger.info(f"[SERVER] Ping session completed with {peer_id} ({ping_count} pings)")
    print(f"[SERVER] Ping session completed with {peer_id} ({ping_count} pings)")


async def send_ping(stream: INetStream) -> None:
    peer_id = stream.muxed_conn.peer_id
    logger.info(f"[CLIENT] Starting ping to {peer_id}")
    print(f"[CLIENT] Starting ping to {peer_id}")

    try:
        payload = b"\x01" * PING_LENGTH
        logger.info(f"[CLIENT] Sending ping to {peer_id}")
        print(f"[CLIENT] Sending ping to {peer_id}")

        await stream.write(payload)
        logger.debug("[CLIENT] Ping data sent, waiting for response...")

        with trio.fail_after(RESP_TIMEOUT):
            response = await stream.read(PING_LENGTH)

        if response == payload:
            logger.info(f"[CLIENT] ✅ Received pong from {peer_id}")
            print(f"[CLIENT] ✅ Received pong from {peer_id}")
        else:
            logger.error(f"[CLIENT] ❌ Invalid pong response from {peer_id}")
            print(f"[CLIENT] ❌ Invalid pong response from {peer_id}")

    except Exception as e:
        logger.error(f"[CLIENT] Error occurred during ping: {e}")
        print(f"[CLIENT] Error occurred during ping: {e}")


async def run(port: int, destination: str) -> None:
    listen_addr = multiaddr.Multiaddr(f"/ip4/0.0.0.0/tcp/{port}")
    logger.info(f"Creating host with listen address: {listen_addr}")

    host = new_host()
    logger.info(f"Host created with peer ID: {host.get_id()}")
    print(f"Host created with peer ID: {host.get_id()}")

    async with host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
        logger.info("Host started successfully")
        print("Host started successfully")

        if not destination:
            # Server mode
            logger.info("Running in SERVER mode")
            print("Running in SERVER mode")

            host.set_stream_handler(PING_PROTOCOL_ID, handle_ping)
            logger.info(f"Registered ping handler for protocol: {PING_PROTOCOL_ID}")

            addrs = host.get_addrs()
            logger.info(f"Listening on addresses: {addrs}")
            print(f"Listening on addresses: {addrs}")

            print(
                "Run this from the same folder in another console:\n\n"
                f"python debug_ping.py -p 8002 "
                f"-d {addrs[0]}\n"
            )
            print("Waiting for incoming connection...")

            await trio.sleep_forever()
        else:
            # Client mode
            logger.info(f"Running in CLIENT mode, connecting to: {destination}")
            print(f"Running in CLIENT mode, connecting to: {destination}")

            try:
                maddr = multiaddr.Multiaddr(destination)
                logger.info(f"Parsed multiaddr: {maddr}")

                info = info_from_p2p_addr(maddr)
                logger.info(
                    f"Extracted peer info - ID: {info.peer_id}, Addrs: {info.addrs}"
                )
                print(f"Target peer ID: {info.peer_id}")

                logger.info("Attempting to connect to peer...")
                print("Attempting to connect to peer...")
                await host.connect(info)
                logger.info("✅ Connected to peer successfully!")
                print("✅ Connected to peer successfully!")

                logger.info(f"Opening stream with protocol: {PING_PROTOCOL_ID}")
                print("Opening stream for ping protocol...")
                stream = await host.new_stream(info.peer_id, [PING_PROTOCOL_ID])
                logger.info("✅ Stream opened successfully!")
                print("✅ Stream opened successfully!")

                nursery.start_soon(send_ping, stream)

                # Wait a bit for the ping to complete
                await trio.sleep(5)

                logger.info("Closing stream")
                await stream.close()
                logger.info("Stream closed")

            except Exception as e:
                logger.error(f"Client error: {e}")
                print(f"Client error: {e}")
                import traceback

                traceback.print_exc()


def main() -> None:
    description = """
    Debug version of ping demo with extensive logging.
    """

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-p", "--port", default=8001, type=int, help="source port number"
    )
    parser.add_argument(
        "-d",
        "--destination",
        type=str,
        help="destination multiaddr string",
    )
    args = parser.parse_args()

    logger.info(
        f"Starting ping debug with port={args.port}, destination={args.destination}"
    )
    print(f"Starting ping debug with port={args.port}, destination={args.destination}")

    try:
        trio.run(run, *(args.port, args.destination))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("Interrupted by user")


if __name__ == "__main__":
    main()
