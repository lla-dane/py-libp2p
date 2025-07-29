import argparse
import logging

import multiaddr
from ping import send_ping
import trio

from libp2p import new_host
from libp2p.custom_types import TProtocol
from libp2p.identity.identify.identify import (
    ID as IDENTIFY_PROTOCOL_ID,
    parse_identify_response,
)
from libp2p.peer.peerinfo import info_from_p2p_addr

logging.disable(logging.CRITICAL)

PING_PROTOCOL_ID = TProtocol("/ipfs/ping/1.0.0")

NUM_CLIENTS = 5


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


async def run(destination: str, peer_count: int) -> None:
    async with trio.open_nursery() as nursery:
        for i in range(peer_count):
            nursery.start_soon(run_single_client_ping, destination)
            nursery.start_soon(run_single_client_identify, destination)
        # sleep to let all clients finish before nursery closes


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
