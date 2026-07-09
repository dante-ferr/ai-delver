import sys


def get_available_space(screen):
    if sys.platform == "win32":
        avail_width = screen.width
        avail_height = screen.height
        try:
            import ctypes

            user32 = ctypes.windll.user32
            avail_width = user32.GetSystemMetrics(78)
            avail_height = user32.GetSystemMetrics(79)
        except:
            pass
    elif sys.platform == "darwin":
        avail_width = screen.width
        avail_height = screen.height
    else:
        avail_width = screen.width
        avail_height = screen.height
        try:
            from Xlib.display import Display

            d = Display()
            screen = d.screen()
            avail_width = screen.width_in_pixels
            avail_height = screen.height_in_pixels
            root = d.screen().root
            for atom in ["_NET_WORKAREA", "_WIN_WORKAREA"]:
                try:
                    workarea = root.get_full_property(d.intern_atom(atom), 0).value
                    if workarea and len(workarea) >= 4:
                        avail_width = workarea[2]
                        avail_height = workarea[3]
                        break
                except:
                    continue
        except ImportError:
            pass

    return (avail_width, avail_height)
