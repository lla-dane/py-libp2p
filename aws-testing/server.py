import multiaddr
from ping import handle_ping
import trio

from libp2p import (
    new_host,
)
from libp2p.custom_types import (
    TProtocol,
)

PING_PROTOCOL_ID = TProtocol("/ipfs/ping/1.0.0")
PING_LENGTH = 32
RESP_TIMEOUT = 60


async def run() -> None:
    listen_addr = multiaddr.Multiaddr("/ip4/0.0.0.0/tcp/8000")
    host = new_host(listen_addrs=[listen_addr])

    async with host.run(listen_addrs=[listen_addr]), trio.open_nursery() as nursery:
        nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)

        host.set_stream_handler(PING_PROTOCOL_ID, handle_ping)

        print(f"Server running at /ip4/0.0.0.0/tcp/8000/p2p/{host.get_id()}")
        # print(f"Server running at /ip4/15.188.49.159/tcp/8000/p2p/{host.get_id()}")
        await trio.sleep_forever()


def main() -> None:
    try:
        trio.run(run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
