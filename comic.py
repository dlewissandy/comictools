import os
from agents import Agent, Runner
    
if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()

    myagent = Agent(
        name="Helpful Agent",
        instructions="You are surly and unhelpful (Think hormonal teen scrolling on phone).   Whatever.",
        tools=[],
        model="gpt-4o-mini"
    )

    response = Runner.run_sync(
        myagent,
        input="What do you want for dinner?"
    )

    print(response)