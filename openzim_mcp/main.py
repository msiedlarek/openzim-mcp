"""Main entry point for OpenZIM MCP server."""

import argparse
import atexit
import sys
from typing import Any

from .config import OpenZimMcpConfig
from .constants import TOOL_MODE_SIMPLE, VALID_TOOL_MODES, VALID_TRANSPORT_TYPES
from .exceptions import OpenZimMcpConfigurationError
from .instance_tracker import InstanceTracker
from .server import OpenZimMcpServer


def main() -> None:
    """Run the OpenZIM MCP server."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="OpenZIM MCP Server - Access ZIM files through MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simple mode with stdio transport (default)
  python -m openzim_mcp /path/to/zim/files

  # Advanced mode
  python -m openzim_mcp --mode advanced /path/to/zim/files

  # SSE transport on custom host and port
  python -m openzim_mcp --transport sse --host 0.0.0.0 --port 9000 /path/to/zim/files

  # Streamable HTTP transport with IPv6
  python -m openzim_mcp --transport streamable-http --host :: --port 8080 /path/to/zim/files

Environment Variables:
  OPENZIM_MCP_TOOL_MODE  - Set tool mode (advanced or simple)
  OPENZIM_MCP_TRANSPORT  - Set transport (stdio, sse, streamable-http)
  OPENZIM_MCP_HOST       - Set listen host (default: ::)
  OPENZIM_MCP_PORT       - Set listen port (default: 8000)
        """,
    )
    parser.add_argument(
        "directories",
        nargs="+",
        help="One or more directories containing ZIM files",
    )
    parser.add_argument(
        "--mode",
        choices=list(VALID_TOOL_MODES),
        default=None,
        help=(
            f"Tool mode: 'advanced' for all 18 tools, 'simple' for 1 "
            f"intelligent NL tool + underlying tools "
            f"(default: {TOOL_MODE_SIMPLE}, or from OPENZIM_MCP_TOOL_MODE env var)"
        ),
    )
    parser.add_argument(
        "--transport",
        choices=sorted(VALID_TRANSPORT_TYPES),
        default=None,
        help=(
            "Transport protocol: 'stdio' for standard I/O, "
            "'sse' for Server-Sent Events, "
            "'streamable-http' for Streamable HTTP "
            "(default: stdio, or from OPENZIM_MCP_TRANSPORT env var)"
        ),
    )
    parser.add_argument(
        "--host",
        default=None,
        help=(
            "Host address to bind to for SSE/streamable-http transports. "
            "Use '0.0.0.0' for all IPv4, '::' for all IPv4+IPv6, "
            "'::1' for IPv6 localhost "
            "(default: ::, or from OPENZIM_MCP_HOST env var)"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            "Port to listen on for SSE/streamable-http transports "
            "(default: 8000, or from OPENZIM_MCP_PORT env var)"
        ),
    )

    # Handle case where no arguments provided
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    try:
        # Create configuration with tool mode
        config_kwargs: dict = {"allowed_directories": args.directories}
        if args.mode:
            config_kwargs["tool_mode"] = args.mode
        if args.transport:
            config_kwargs["transport"] = args.transport
        if args.host:
            config_kwargs["host"] = args.host
        if args.port is not None:
            config_kwargs["port"] = args.port

        config = OpenZimMcpConfig(**config_kwargs)

        # Initialize instance tracker
        instance_tracker = InstanceTracker()

        # Register this server instance
        instance_tracker.register_instance(
            config_hash=config.get_config_hash(),
            allowed_directories=config.allowed_directories,
            server_name=config.server_name,
        )

        # Register cleanup function
        def cleanup_instance() -> None:
            # Use silent mode - logging may be closed during shutdown
            instance_tracker.unregister_instance(silent=True)

        atexit.register(cleanup_instance)

        # Create and run server
        server = OpenZimMcpServer(config, instance_tracker)

        mode_desc = (
            "SIMPLE mode (1 intelligent tool + all underlying tools)"
            if config.tool_mode == TOOL_MODE_SIMPLE
            else "ADVANCED mode (18 specialized tools)"
        )
        transport_desc = config.transport.upper()
        if config.transport != "stdio":
            host_display = f"[{config.host}]" if ":" in config.host else config.host
            transport_desc += f" on {host_display}:{config.port}"

        print(
            f"OpenZIM MCP server started in {mode_desc}",
            file=sys.stderr,
        )
        print(
            f"Transport: {transport_desc}",
            file=sys.stderr,
        )
        print(
            f"Allowed directories: {', '.join(args.directories)}",
            file=sys.stderr,
        )

        server.run(transport=config.transport)

    except OpenZimMcpConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Server startup error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
