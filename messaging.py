"""
This module handles the messaging functionality for the application, including sending messages,
and updating the message history in the user interface.   The one complexity to this is that
If the agent needs to call a tool, then multiple internal messages will be generated.   These
are posed to a special "thoughts" container that can be expanded by the user to see the details.
"""

import asyncio
from agents import Runner, ItemHelpers
from loguru import logger
from nicegui import ui
from openai.types.responses import ResponseTextDeltaEvent
from agents import AgentUpdatedStreamEvent, RunItemStreamEvent
from gui.state import APPState



ROLE_MAP = {
    "you": "user",
    "bot": "assistant",
    "tool output": "assistant",
    "tool call": "assistant",
}

def append_history(sender: str, content: ui.element, sent: bool = True):
    """
    Append a message to the chat history in the user interface.
    """
    with ui.chat_message(name=sender, sent=sent).classes('w-full') as message:
        ui.markdown(content)
    return message


def thoughts_container(parent: ui.row) -> ui.expansion:
    """
    If there is a expansion in the parent, return it, otherwise create a new one.
    """
    # if we’ve already created it, reuse it
    if hasattr(parent, "_thoughts_expand"):
        return parent._thoughts_expand

    # otherwise create it and stash it on the parent
    with parent:
        parent._thoughts_expand = (
            ui.expansion("Thoughts", value=False)
              .classes("w-full text-sm")
        )
    return parent._thoughts_expand

def create_spinner() -> ui.spinner:
    """
    Create a spinner element for indicating loading or processing.
    """
    return 


async def handle_text_delta_event(state: APPState,event: ResponseTextDeltaEvent, response_markdown: ui.markdown):
    """
    Handle a text delta event by updating the response markdown and scrolling the history.
    """
    response_markdown.content += event.data.delta
    state.history.scroll_to(percent=100)
    await asyncio.sleep(0)

async def handle_handoff_event(state: APPState, event: AgentUpdatedStreamEvent, divider: ui.row):
    logger.info(f"\n[Agent switched to: {event.new_agent.name}]")
    # TODO: If we use handoffs, then this needs to be updated so that we get a history of the handoffs

async def handle_tool_call_event(state: APPState, event: RunItemStreamEvent, divider: ui.row):
    """
    This event occurs when the agent calls a tool.   Handle a tool call event by updating the response
    markdown with the tool call details.
    """
    raw_item = event.item.raw_item
    tool_name = raw_item.name
    args = raw_item.arguments
    thought = f"🔧 Calling tool **{tool_name}** with arguments:\n```\n{args}\n```"
    logger.debug(thought)
    with thoughts_container(divider):
        with ui.chat_message(name='Tool Call', sent=False).classes('w-full'):
            ui.markdown(f"{tool_name}({args})")

async def handle_tool_output_event(state: APPState, event: RunItemStreamEvent, divider: ui.row):
    """
    This event occurs when a tool responds to a tool call event.   Handle the event by updating the 
    "thoughts" container with the tool output.
    """
    item = event.item
    output = item.output
    thought = f"📤 Tool responded with:\n```\n{output}\n```"
    logger.debug(thought)
    with thoughts_container(divider):
        with ui.chat_message(name='Tool Output', sent=False).classes('w-full'):
            ui.markdown(str(output))


async def handle_message_output_event(state: APPState, event: RunItemStreamEvent, divider: ui.row):
    """
    This event occurs after a tool output is received and the agent generates a message based on the tool ouput.
    Handle the event by updating the response markdown with the final message.
    """
    item = event.item
    text = ItemHelpers.text_message_output(item)
    thought = f"🧠 Using tool output to generate message"
    logger.debug(thought)

async def handle_agent_events(state: APPState, messages: list[dict], response_markdown: ui.markdown, divider: ui.row):
    agents = state.agents
    selection = state.selection
    kind = "home" if not selection else selection[-1].kind
    agent = agents.get(kind, None)
    if agent is None:
        raise ValueError(f"Agent not found for kind: {kind}")
    stream = Runner.run_streamed(agent, input=messages, context=state)
    streamed_events = stream.stream_events()
    async for event in streamed_events:
        # --- RAW TEXT TOKENS ---
        if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
            await handle_text_delta_event(state, event, response_markdown)
        elif event.type == "agent_updated_stream_event":
            await handle_handoff_event(state, event, response_markdown)

        # --- TOOL USAGE EVENTS ---
        elif event.type == "run_item_stream_event":
            item = event.item

            if item.type == "tool_call_item":
                await handle_tool_call_event(state, event, divider)
                
            # Tool output
            elif item.type == "tool_call_output_item":
                await handle_tool_output_event(state, event, divider)

            # Completed LLM message (post-tool or final)
            elif item.type == "message_output_item":
                await handle_message_output_event(state, event, divider)
            else:
                msg = f"Unhandled item type: {item.type} while using tools"
                logger.critical(item.type)
                
    return stream.to_input_list()


async def send(state: APPState):
    # Dereference state variables
    history = state.history
    text_input = state.user_input
    question = text_input.value
    text_input.value = ''

    # TODO: Disable the "send button" while the response is being generated

    # Build The Message History
    messages = state.get_messages(role_map=ROLE_MAP)
    messages.append({"role": "user", "content": question})

    # Post the question to the message history
    with state.history:
        append_history('You', question, sent=True)

    # Create a container for internal thoughts
        divider = ui.row().classes('w-full')

    # Initialize the UI elements for the response message handling
        with ui.chat_message(name='Bot', sent=False).classes('w-full'):
            with ui.column().classes('w-full'):
                response_markdown = ui.markdown("").classes('w-full')
                spinner = ui.spinner('dots', size="2em")
    
    history.scroll_to(percent=100)
    
    # Stream the responses from the agent, updating the UI as we go
    responses = await handle_agent_events(state, messages, response_markdown, divider)

    # Now that we are done, celan up the ui.
    # TODO: RE-enable "send button" after the response is complete
    spinner.delete()
    
    state.write()
    if state.is_dirty:
        state.refresh_details()
        state.is_dirty = False
