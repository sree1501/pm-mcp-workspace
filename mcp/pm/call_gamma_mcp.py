import sys, asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    if len(sys.argv) < 2:
        print('Usage: uv run python call_gamma_mcp.py "Deck Title" < deck.txt')
        return

    title = sys.argv[1]
    deck_text = sys.stdin.read()

    server = StdioServerParameters(command="uv", args=["run", "pm_server.py"])

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "gamma_generate_pptx",
                {"title": title, "deck_text": deck_text, "text_amount": "brief", "language": "en"},
            )
            out = []
            if hasattr(result, "content") and result.content:
                for c in result.content:
                    out.append(getattr(c, "text", str(c)))
                print("\n".join(out))
            else:
                print(result)

if __name__ == "__main__":
    asyncio.run(main())
