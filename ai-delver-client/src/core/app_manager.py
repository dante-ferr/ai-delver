import pyglet
from runtime_view.game import Game
from typing import Optional
import logging
from loaders import level_loader
from runtime_view.replay import StateSyncReplay
from loaders import agent_loader
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app import EditorApp


class AppManager:
    """
    The central controller for the entire application. It manages the lifecycle
    of the main editor window, game runtime, and replay runtime, and orchestrates
    the main application tick that drives both tkinter and pyglet.
    """
    def __init__(self):
        self._game = None
        self._replay = None
        self._editor: Optional[EditorApp] = None
        self._is_running = True

    def master_tick(self):
        """
        The main application tick. This is driven by the tkinter event loop
        and is responsible for manually ticking the pyglet clock.
        """
        if not self._is_running:
            return

        try:
            # Process all pending pyglet events and call scheduled functions.
            pyglet.clock.tick(poll=True)
        except Exception as e:
            logging.error(
                "An unhandled exception occurred in the application loop.",
                exc_info=True,
            )
            from app.components.overlay.message_overlay import MessageOverlay

            MessageOverlay(
                f"An unexpected error occurred: {e}\n\n"
                "The application may be unstable. Please save your work and restart.\n"
                "See logs for more details.",
                subject="Error",
            )
            # We stop ticking to prevent an error loop, but leave the editor open.
            return

        # Reschedule this function to be called again by tkinter's loop.
        # This creates the continuous, non-blocking loop that drives pyglet.
        if self._editor:
            self._editor.after(16, self.master_tick)

    def start_editor(self):
        """
        Starts the editor, which is the master application.
        It will manage the main event loop.
        """
        from app import EditorApp

        if self._editor is None:
            self._editor = EditorApp()
            logging.info("Starting editor")

            # Handle the editor window closing cleanly
            self._editor.protocol("WM_DELETE_WINDOW", self._on_editor_close)

            # Start the master tick loop, which will drive pyglet.
            self.master_tick()

            # Run the tkinter main loop. This is a blocking call, but master_tick
            # is now integrated into its event chain.
            self._editor.mainloop()
        else:
            self._editor.deiconify()

    def _on_editor_close(self):
        """Handles the editor window closing, which shuts down everything."""
        logging.info("Editor closing, shutting down application.")
        self._is_running = False  # Stop the master_tick loop.
        self.stop_viewable_runtimes()
        if self._editor:
            self._editor.destroy()

    def _start_runtime(self, runtime_name, runtime_class, *args):
        if getattr(self, f"_{runtime_name}") is not None:
            logging.warning(
                f"{runtime_name.capitalize()} is already running. Stopping first."
            )
            self._stop_runtime(runtime_name)

        if self._editor is not None:
            self._editor.withdraw()

        runtime_instance = runtime_class(*args)
        setattr(self, f"_{runtime_name}", runtime_instance)

        # The runtime schedules its own update loop with pyglet's clock.
        runtime_instance.run()

    def _stop_runtime(self, runtime_name):
        runtime_instance = getattr(self, f"_{runtime_name}")
        if runtime_instance is not None:
            runtime_instance.stop()
        setattr(self, f"_{runtime_name}", None)

        # Bring the editor back into view when the game closes.
        if self._editor is not None:
            self._editor.deiconify()
            self._editor.focus_force()

    def start_game(self):
        self._start_runtime("game", Game, level_loader.level)

    def stop_game(self):
        self._stop_runtime("game")

    def start_replay(self):
        trajectory = agent_loader.agent.trajectory_loader.trajectory
        if trajectory is None:
            raise RuntimeError("No trajectory loaded")

        self._start_runtime("replay", StateSyncReplay, trajectory)

    def stop_replay(self):
        self._stop_runtime("replay")

    def stop_viewable_runtimes(self):
        self.stop_game()
        self.stop_replay()

    def stop_editor(self):
        if self._editor is not None:
            self._editor.withdraw()

    @property
    def editor_app(self):
        if self._editor is None:
            raise RuntimeError("Editor app not initialized")
        return self._editor


app_manager = AppManager()
