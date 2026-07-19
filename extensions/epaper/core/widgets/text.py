
from extensions.epaper.models.screenmodel import TextWidgetModel
from ..drawingcontext import DrawingContext
from .base import Widget


class TextWidget(Widget):

    def __init__(self, id: str, config: TextWidgetModel):
        super().__init__(id, config)


    async def draw(self, ctx: DrawingContext):
        await super().draw(ctx)

        text = self.config.text
        ctx.draw_text(position=(0,0),
                        size=self.config.size, 
                        text=text, 
                        alignment=self.config.alignment,
                        font=self.font)
