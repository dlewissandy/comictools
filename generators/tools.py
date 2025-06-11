from loguru import logger
from agents import function_tool
from gui.state import APPState




    
def wrap_render_logo(state: APPState):
    """
    Render the logo for a publisher.
    
    Args:
        state: The GUI elements to interact with.
    
    Returns:
        The rendered logo image.
    """
    @function_tool
    def render_logo() -> str:
        """
        Render the logo.
        
        Returns:
            A status message indicating the result of the rendering.
        """
        from models.publisher import Publisher
        selection = state.selection
        kind = selection[-1].kind
        if kind != "publisher":
            msg = f"The selection is not a publisher: {kind}"
            logger.error(msg)
            return msg
        
        publisher_id = selection[-1].id
        publisher = Publisher.read(id=publisher_id)
        if publisher is None:
            msg = f"Publisher with ID '{publisher_id}' not found."
            logger.error(msg)
            return msg
        
        img = publisher.render()
        if img is None:
            msg = f"Logo for publisher '{publisher.name}' could not be rendered."
            logger.error(msg)
            return msg
        
        state["is_dirty"] = True        
        return f"The logo for publisher '{publisher.name}' has been rendered and is saved to {img}.jpg"
    
    return render_logo