import sys, asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    if len(sys.argv) < 5:
        print('ERROR: Usage: call_sky_native_mcp.py "<title>" "<detail>" "<language>" "<audience>" < deck.txt')
        return

    title = sys.argv[1]
    detail = sys.argv[2]
    language = sys.argv[3]
    audience = sys.argv[4]
    deck_text = sys.stdin.read()

    server = StdioServerParameters(command="uv", args=["run", "pm_server.py"])

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            res = await session.call_tool(
                "skywork_run_slides_phase2_native",
                {"title": title, "deck_text": deck_text, "audience": audience, "detail": detail, "language": language},
            )

            # Print only the FINAL text line from the tool response (avoid dumping prompts)
            out_lines = []
            for c in getattr(res, "content", []) or []:
                t = getattr(c, "text", "")
                if t:
                    out_lines.extend(t.splitlines())

            if out_lines:
                print(out_lines[-1])
            else:
                print("OK")

if __name__ == "__main__":
    asyncio.run(main())
