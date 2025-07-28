import argparse

import multiaddr
from ping import send_ping
import trio

from libp2p import (
    new_host,
)
from libp2p.custom_types import (
    TProtocol,
)
from libp2p.peer.peerinfo import (
    info_from_p2p_addr,
)

PING_PROTOCOL_ID = TProtocol("/ipfs/ping/1.0.0")
PING_LENGTH = 32
RESP_TIMEOUT = 60


async def run(destination: str) -> None:
    async with trio.open_nursery() as nursery:
        for i in range(5):
            listen_addr = multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/0")
            host = new_host(listen_addrs=[listen_addr])

            async with host.run(listen_addrs=[listen_addr]):
                nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)

                maddr = multiaddr.Multiaddr(destination)
                info = info_from_p2p_addr(maddr)
                await host.connect(info)
                stream = await host.new_stream(info.peer_id, [PING_PROTOCOL_ID])

                nursery.start_soon(send_ping, stream)
                await trio.sleep(1)

                print(f"Peer {host.get_id} PING SUCCESSFULL")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-d",
        "--destination",
        type=str,
        help="destination multiaddr string",
    )
    args = parser.parse_args()

    try:
        trio.run(run, args.destination)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
