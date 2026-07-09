def get_children_height(master):
    total_height = 0
    for child in master.winfo_children():
        # Get height of child widget
        child_height = child.winfo_height()

        # Get the padding for the child widget (top, bottom)
        # padding_top = int(child.cget("padx").split()[0])  # Assuming padding is uniform
        # padding_bottom = int(child.cget("padx").split()[1])  # Adjust if needed

        total_height += child_height  # + padding_top + padding_bottom

    return total_height
