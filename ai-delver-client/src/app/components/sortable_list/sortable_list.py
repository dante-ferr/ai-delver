import customtkinter as ctk
from .draggable_box.draggable_box import DraggableBox
from app.components import MouseWheelScrollableFrame
from typing import Optional, cast


class SortableList(MouseWheelScrollableFrame):
    """
    A list container that allows reordering its children via drag and drop.
    Inherits scroll capabilities from MouseWheelScrollableFrame.
    """

    def __init__(self, master, remove_box_button=False, **kwargs):
        super().__init__(master, **kwargs)

        self.remove_box_button = remove_box_button
        self.boxes = []

        self.dragged_item: Optional[DraggableBox] = None
        self.drag_start_y_offset = 0
        self.placeholder_index = -1

        self.scroll_zone_height = 50
        self.scroll_interval = 50
        self.scroll_step = 2
        self._is_dragging_scroll = False
        self._drag_scroll_direction = 0

        self.placeholder = ctk.CTkFrame(
            self,
            fg_color="transparent",
            border_width=2,
            border_color=("gray60", "gray40"),
        )

    def add_box(self, name: str, **kwargs):
        new_box = DraggableBox(
            self, name, remove_box_button=self.remove_box_button, **kwargs
        )
        self.boxes.append(new_box)
        new_box.pack(fill="x", pady=4, padx=(0, 8))

        # DraggableBox handles its own scroll binding to manage hover states,
        # so we don't use bind_scroll_events_recursively here to avoid double-scrolling.

        self.after(50, self._check_scroll_visibility)

    def remove_box(self, name: str):
        for box in self.boxes:
            if box.name == name:
                box.destroy()
                self.boxes.remove(box)
                # Wait for destroy to propagate before checking scroll
                self.after(50, self._check_scroll_visibility)
                return
        print(f"Box '{name}' not found.")

    def get_order(self) -> list[str]:
        return [box.name for box in self.boxes]

    def start_drag(self, item: DraggableBox, event):
        if self.dragged_item:
            return

        self.dragged_item = item
        self.placeholder_index = self.boxes.index(item)

        self.winfo_toplevel().bind("<ButtonRelease-1>", self.stop_drag, add="+")

        canvas = self._parent_canvas
        mouse_y_screen_relative = event.y_root - canvas.winfo_rooty()
        mouse_y_content = canvas.canvasy(mouse_y_screen_relative)
        self.drag_start_y_offset = mouse_y_content - item.winfo_y()

        self.placeholder.configure(height=item.winfo_height(), width=item.winfo_width())

        self.repack_layout(with_placeholder=True)
        item.lift()
        self._update_dragged_item_position(event)

    def perform_drag(self, event):
        if not self.dragged_item:
            return

        self._update_drag_scroll_direction(event)
        self._update_dragged_item_position(event)
        self._calculate_placeholder_index(event)

    def stop_drag(self, event):
        self.winfo_toplevel().unbind("<ButtonRelease-1>")

        if not self.dragged_item:
            return

        self._is_dragging_scroll = False
        self._drag_scroll_direction = 0

        self.placeholder.pack_forget()
        self.dragged_item.place_forget()

        old_index = self.boxes.index(self.dragged_item)
        self.boxes.pop(old_index)

        target_index = self.placeholder_index
        if target_index > len(self.boxes):
            target_index = len(self.boxes)

        self.boxes.insert(target_index, self.dragged_item)

        self.dragged_item = None
        self.placeholder_index = -1

        self.repack_layout(with_placeholder=False)

    def _update_drag_scroll_direction(self, event):
        if not self._scrollbar.winfo_viewable():
            self._drag_scroll_direction = 0
            return

        canvas = self._parent_canvas
        mouse_y_viewport = event.y_root - canvas.winfo_rooty()
        visible_height = canvas.winfo_height()

        if mouse_y_viewport < self.scroll_zone_height:
            self._drag_scroll_direction = -1
        elif mouse_y_viewport > visible_height - self.scroll_zone_height:
            self._drag_scroll_direction = 1
        else:
            self._drag_scroll_direction = 0

        if self._drag_scroll_direction != 0 and not self._is_dragging_scroll:
            self._is_dragging_scroll = True
            self._auto_scroll_loop(event)

    def _auto_scroll_loop(self, last_event):
        if not self.dragged_item or self._drag_scroll_direction == 0:
            self._is_dragging_scroll = False
            return

        self._parent_canvas.yview_scroll(
            self._drag_scroll_direction * self.scroll_step, "units"
        )
        self._update_dragged_item_position(last_event)
        self._calculate_placeholder_index(last_event)

        self.after(self.scroll_interval, lambda: self._auto_scroll_loop(last_event))

    def _update_dragged_item_position(self, event):
        if not self.dragged_item:
            return

        canvas = self._parent_canvas
        mouse_y_viewport = event.y_root - canvas.winfo_rooty()
        mouse_y_content = canvas.canvasy(mouse_y_viewport)
        final_y = mouse_y_content - self.drag_start_y_offset
        self.dragged_item.place(x=10, y=final_y, relwidth=0.9)

    def _calculate_placeholder_index(self, event):
        mouse_y = event.y_root
        static_boxes = [b for b in self.boxes if b is not self.dragged_item]

        if not static_boxes:
            self._update_placeholder_if_changed(0)
            return

        if self._is_dragging_scroll:
            if self._drag_scroll_direction == 1:
                self._update_placeholder_if_changed(len(static_boxes))
                return
            elif self._drag_scroll_direction == -1:
                self._update_placeholder_if_changed(0)
                return

        viewport_top = self.winfo_rooty()
        viewport_bottom = viewport_top + self.winfo_height()

        if mouse_y < viewport_top:
            self._update_placeholder_if_changed(0)
            return
        elif mouse_y > viewport_bottom:
            self._update_placeholder_if_changed(len(static_boxes))
            return

        new_index = len(static_boxes)
        for i, box in enumerate(static_boxes):
            center = box.winfo_rooty() + (box.winfo_height() / 2)
            if mouse_y < center:
                new_index = i
                break

        self._update_placeholder_if_changed(new_index)

    def _update_placeholder_if_changed(self, new_index):
        if new_index != self.placeholder_index:
            self.placeholder_index = new_index
            self.repack_layout(with_placeholder=True)

    def repack_layout(self, with_placeholder: bool):
        for child in self.winfo_children():
            child = cast("DraggableBox", child)
            if child is not self.dragged_item:
                child.pack_forget()

        visual_boxes = [b for b in self.boxes if b is not self.dragged_item]

        if with_placeholder:
            idx = max(0, min(self.placeholder_index, len(visual_boxes)))
            visual_boxes.insert(idx, self.placeholder)

        for widget in visual_boxes:
            widget.pack(fill="x", padx=10, pady=5)

        self.after(50, self._check_scroll_visibility)
