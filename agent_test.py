import datetime
import dotenv
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool, ItemHelpers
from openai.types.responses import ResponseTextDeltaEvent

dotenv.load_dotenv()


@function_tool
def create_new_style(description: str) -> str:
    """
    Create a new comic book art style based on the description, or examples.
    """
    from style.comic import ComicStyle
    # This is a placeholder for the actual implementation
    style = ComicStyle.generate(description)
    if not style:
        return "I couldn't generate a new style from your description."
    style.write()
    return style.format()

@function_tool
def revise_existing_style(feedback:str) -> str:
    """
    Revise the current comic book art style based on the feedback.

    args:
        feedback (str): The feedback to revise the style.
    """
    from style.comic import ComicStyle
    # This is a placeholder for the actual implementation
    style = ComicStyle.read(feedback)
    if not style:
        return "I couldn't find the style to revise."
    revised_style = style.revise(feedback)
    return revised_style.format()

math_agent = Agent(
    name="Art Styles Assistant",
    instructions="You are an interactive artistic assistant. Take user descriptions and feedback to generate concise artistic style descriptions that artists can use to create cohesive pieces. Focus on maintaining a consistent look and feel based on user input, providing suggestions for style elements such as media, color palettes, textures, and themes. Engage in a collaborative dialogue to refine the artistic vision.",
    model="gpt-4o-mini",
    input_guardrails={"The request must be related to art styles."},
    tools=[create_new_style, revise_existing_style]
)

# 1) Define a simple tool
@function_tool
def get_current_time() -> str:
    return datetime.datetime.now().isoformat()



async def main(question: str) -> str:
    # 2) Create your agent with the tool attached
    agent = Agent(
        name="TimeAgent",
        instructions="You are a helpful assistant. Answer the user's questions.",
        tools=[get_current_time, create_new_style],
    )

    # 3) Kick off a streamed run
    result = Runner.run_streamed(agent, input=question)

    print("=== Stream start ===")
    async for event in result.stream_events():
        # --- RAW TEXT TOKENS ---
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            print(event.data.delta, end="", flush=True)

        # --- AGENT HANDOFFS (if any) ---
        elif event.type == "agent_updated_stream_event":
            print(f"\n[Agent switched to: {event.new_agent.name}]")

        # --- TOOL USAGE EVENTS ---
        elif event.type == "run_item_stream_event":
            item = event.item
            raw_item = item.raw_item

            # Tool invocation
            if item.type == "tool_call_item":
                print(item)
                print(f"\n[Tool call → {raw_item.name} with input {raw_item.arguments}]")

            # Tool output
            elif item.type == "tool_call_output_item":
                print(f"\n[Tool output → {item.output}]")

            # Completed LLM message (post-tool or final)
            elif item.type == "message_output_item":
                text = ItemHelpers.text_message_output(item)
                print(f"\n[Message output → {text}]")

        # (You can handle other event types here…)
    return result
    print("\n=== Stream complete ===")




if __name__ == "__main__":
    import asyncio
    question = "Are you familiar with the art style of Rakin and Bass?"
    print(f"👴: {question}")
    result = asyncio.run(main(question))
    print(f"🤖: {result}")

    # question = "Create a new art style based on origami.   Instead of drawings, it should use folded paper."
    # print(f"👴: {question}")
    # result = asyncio.run(main(question))
    # print(result)


