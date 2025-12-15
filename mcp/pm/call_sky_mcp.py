import sys, asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    if len(sys.argv) < 5:
        print('Usage: call_sky_mcp.py "<title>" "<detail>" "<language>" "<audience>" < deck.txt')
        return

    title = sys.argv[1]
    detail = sys.argv[2]
    language = sys.argv[3]
    audience = sys.argv[4]
    deck_text = sys.stdin.read()

    server = StdioServerParameters(
        command="uv",
        args=["run", "pm_server.py"]
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "skywork_prepare_slides",
                {
                    "title": title,
                    "deck_text": deck_text,
                    "audience": audience,
                    "detail": detail,
                    "language": language,
                    "open_browser": True
                },
            )

            if hasattr(result, "content") and result.content:
                for c in result.content:
                    print(getattr(c, "text", str(c)))
            else:
                print(result)

if __name__ == "__main__":
    asyncio.run(main())
