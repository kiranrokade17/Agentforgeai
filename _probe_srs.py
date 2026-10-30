import asyncio

from app.agents.factory import get_llm_provider
from app.schemas.specification import SRSContent


async def main() -> None:
    provider = get_llm_provider("openrouter")
    text = await provider._call(
        "You are the AgentForge AI Lead Software Architect.",
        "### User Requirements:\nBuild a simple todo list REST API with FastAPI and PostgreSQL.\n\n"
        "Compile the complete, schema-valid SRS.",
        SRSContent,
    )
    with open("_raw_srs.txt", "w", encoding="utf-8") as handle:
        handle.write(text)
    print("LEN:", len(text))


asyncio.run(main())
