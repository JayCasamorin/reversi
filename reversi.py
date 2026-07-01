import logging
import random
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# --- Flip animation constants ---
FLIP_ANIM_STEPS: int = 12
FLIP_ANIM_INTERVAL_MS: int = 24
FLIP_ANIM_AXIS: str = "vertical"  # "vertical" or "horizontal"

# Directions for Reversi (Othello) moves: 8 surrounding directions
DIRECTIONS: List[Tuple[int, int]] = [
    (0, 1),
    (1, 0),
    (0, -1),
    (-1, 0),
    (1, 1),
    (-1, -1),
    (1, -1),
    (-1, 1),
]

# Visual tuning constants
PIECE_MARGIN: int = 2  # Margin inside a cell for drawing a piece
HINT_SIZE_RATIO: float = 0.8  # Hint diameter relative to piece diameter (<= 1.0)
HINT_OUTLINE_COLOR: str = "gray70"  # Subtle hint color
HINT_OUTLINE_WIDTH: int = 1  # Hint outline thickness

# Last-move highlight
LAST_MOVE_OUTLINE_COLOR: str = "red"
LAST_MOVE_OUTLINE_WIDTH: int = 2
LAST_MOVE_OUTLINE_INSET: int = 1

# AI difficulty defaults
DEFAULT_AI_DIFFICULTY: str = "medium"  # "easy" | "medium" | "hard"


class ReversiBoard:
    def __init__(
        self,
        master: tk.Tk,
        size: int = 8,
        cell_size: int = 25,
        single_player: bool = False,
        ai_difficulty: str = DEFAULT_AI_DIFFICULTY,
    ) -> None:
        """Initialize the Reversi board."""
        self.master = master
        self.size = max(2, size)
        self.cell_size = max(10, cell_size)
        self.single_player = single_player
        self.ai_difficulty = ai_difficulty.lower().strip()
        if self.ai_difficulty not in {"easy", "medium", "hard"}:
            logging.warning("Invalid AI difficulty; defaulting to 'medium'.")
            self.ai_difficulty = DEFAULT_AI_DIFFICULTY

        # Board representation: board[x][y] where x is column, y is row.
        # Values: None for empty, 1 for black, 0 for white.
        self.board: List[List[Optional[int]]] = [[None] * self.size for _ in range(self.size)]
        self.current_player: int = 1  # 1 = black (starts), 0 = white
        self.ai_player: Optional[int] = 0 if self.single_player else None

        # Track the last placed move for highlighting.
        self.last_move: Optional[Tuple[int, int]] = None

        # Precompute positional weights for evaluation (for hard difficulty)
        self.positional_weights: List[List[int]] = self.compute_position_weights()

        # UI setup
        self.frame = tk.Frame(master)
        self.frame.pack()
        self.canvas = tk.Canvas(
            self.frame,
            width=self.size * self.cell_size,
            height=self.size * self.cell_size,
            highlightthickness=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.click)

        self.turn_label = tk.Label(self.frame, text="Black's turn")
        self.turn_label.pack(pady=(8, 2))

        self.count_label = tk.Label(self.frame, text="Black: 0, White: 0")
        self.count_label.pack(pady=(0, 8))

        # Animation state
        self.animating: bool = False
        self._anim_items: List[int] = []
        self._anim_bounds: List[Tuple[int, int, int, int]] = []
        self._anim_flips: List[Tuple[int, int]] = []
        self._anim_step: int = 0

        self.reset()

    def reset(self) -> None:
        """Reset the board to the initial Reversi setup."""
        logging.info("Resetting the game board.")
        self.current_player = 1
        self.last_move = None
        self.board = [[None] * self.size for _ in range(self.size)]

        mid = self.size // 2
        # Standard starting position (orientation preserved from original code)
        self.board[mid - 1][mid - 1] = 1  # Black
        self.board[mid][mid] = 1  # Black
        self.board[mid - 1][mid] = 0  # White
        self.board[mid][mid - 1] = 0  # White

        self.draw_board()
        self.update_turn_label()
        self.update_count_label()

        if self.is_game_over():
            self.game_over()

    def draw_board(self) -> None:
        """Draw the grid and pieces on the canvas."""
        self.canvas.delete("all")
        for x in range(self.size):
            for y in range(self.size):
                x1, y1 = x * self.cell_size, y * self.cell_size
                x2, y2 = x1 + self.cell_size, y1 + self.cell_size
                self.canvas.create_rectangle(x1, y1, x2, y2, fill="green", outline="black")

                value = self.board[x][y]
                if value is not None:
                    color = "black" if value == 1 else "white"
                    self.canvas.create_oval(
                        x1 + PIECE_MARGIN,
                        y1 + PIECE_MARGIN,
                        x2 - PIECE_MARGIN,
                        y2 - PIECE_MARGIN,
                        fill=color,
                        outline="gray",
                        width=1,
                    )
                elif self.valid_move(x, y, self.current_player):
                    # Hint: outline-only circle, sized relative to the piece
                    cx = x1 + self.cell_size // 2
                    cy = y1 + self.cell_size // 2
                    piece_diameter = self.cell_size - (2 * PIECE_MARGIN)
                    hint_diameter = max(3, int(piece_diameter * HINT_SIZE_RATIO))
                    hr = hint_diameter / 2
                    self.canvas.create_oval(
                        int(cx - hr),
                        int(cy - hr),
                        int(cx + hr),
                        int(cy + hr),
                        fill="",
                        outline=HINT_OUTLINE_COLOR,
                        width=HINT_OUTLINE_WIDTH,
                    )

        # Draw last-move highlight on top of everything else.
        if self.last_move is not None:
            lx, ly = self.last_move
            if 0 <= lx < self.size and 0 <= ly < self.size:
                x1 = lx * self.cell_size + LAST_MOVE_OUTLINE_INSET
                y1 = ly * self.cell_size + LAST_MOVE_OUTLINE_INSET
                x2 = (lx + 1) * self.cell_size - LAST_MOVE_OUTLINE_INSET
                y2 = (ly + 1) * self.cell_size - LAST_MOVE_OUTLINE_INSET
                self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill="",
                    outline=LAST_MOVE_OUTLINE_COLOR,
                    width=LAST_MOVE_OUTLINE_WIDTH,
                )

    def click(self, event: tk.Event) -> None:
        """Handle a canvas click for placing a piece. Defers updates during animation."""
        if self.animating:
            return

        i = event.x // self.cell_size
        j = event.y // self.cell_size

        if not (0 <= i < self.size and 0 <= j < self.size):
            logging.debug("Click outside the board ignored.")
            return
        if self.is_invalid_click(i, j):
            return

        self.make_move(i, j)

        # If an animation started, finalize move after animation completes.
        if self.animating:
            return

        self.switch_player()
        self.update_game_state()

    def is_invalid_click(self, i: int, j: int) -> bool:
        """Determine if the click at (i, j) is invalid for the current player."""
        if self.board[i][j] is not None:
            return True
        if not self.valid_move(i, j, self.current_player):
            messagebox.showerror("Invalid move", "That's not a valid move!")
            return True
        return False

    def make_move(self, i: int, j: int) -> None:
        """Place a piece for the current player and flip bracketed opponent pieces."""
        logging.debug("Making move at (%s, %s) for player %s.", i, j, self.current_player)
        self.board[i][j] = self.current_player
        self.last_move = (i, j)
        self.flip_pieces(i, j)

    def switch_player(self) -> None:
        """
        Switch to the next player if they have a valid move.
        If not, the current player continues (skip turn mechanic).
        """
        next_player = 1 - self.current_player
        has_next_moves = any(
            self.valid_move(x, y, next_player) for x in range(self.size) for y in range(self.size)
        )
        if has_next_moves:
            self.current_player = next_player
        else:
            logging.info("Next player has no valid moves. Turn is skipped.")

    def update_game_state(self) -> None:
        """Refresh the board and labels, then check for game end. Schedule AI if needed."""
        if self.animating:
            # Avoid clearing canvas or changing state during animation.
            return

        self.draw_board()
        self.update_turn_label()
        self.update_count_label()

        if self.is_game_over():
            self.game_over()
            return

        # Auto-run AI if single-player and it's AI's turn
        if self.single_player and self.current_player == 0:
            if any(
                self.valid_move(x, y, self.current_player)
                for x in range(self.size)
                for y in range(self.size)
            ):
                # Schedule AI move to keep UI responsive
                self.master.after(150, self.ai_move)

    def flip_pieces(self, x: int, y: int) -> None:
        """
        Flip opponent pieces bracketed by the current player's piece at (x, y).
        If flips exist, animate the flipping.
        """
        flips_set: set[Tuple[int, int]] = set()
        for dx, dy in DIRECTIONS:
            i, j = x + dx, y + dy
            line: List[Tuple[int, int]] = []
            while (
                0 <= i < self.size
                and 0 <= j < self.size
                and self.board[i][j] == 1 - self.current_player
            ):
                line.append((i, j))
                i += dx
                j += dy
            if (
                0 <= i < self.size
                and 0 <= j < self.size
                and self.board[i][j] == self.current_player
                and line
            ):
                flips_set.update(line)

        flips = list(flips_set)
        if not flips:
            return

        # Prepare animation: temporarily clear flipped discs from the logical board.
        self.animating = True
        for fx, fy in flips:
            self.board[fx][fy] = None

        # Redraw without the soon-to-flip discs, then start overlay animation.
        self.draw_board()
        self._start_flip_animation(flips)

    def _start_flip_animation(self, flips: List[Tuple[int, int]]) -> None:
        """Create overlay ovals and start the flip animation."""
        old_color = "black" if (1 - self.current_player) == 1 else "white"
        self._anim_items = []
        self._anim_bounds = []
        self._anim_flips = flips
        self._anim_step = 0

        for fx, fy in flips:
            x1 = fx * self.cell_size + PIECE_MARGIN
            y1 = fy * self.cell_size + PIECE_MARGIN
            x2 = x1 + self.cell_size - (2 * PIECE_MARGIN)
            y2 = y1 + self.cell_size - (2 * PIECE_MARGIN)
            item = self.canvas.create_oval(
                x1,
                y1,
                x2,
                y2,
                fill=old_color,
                outline="gray",
                width=1,
            )
            self._anim_items.append(item)
            self._anim_bounds.append((x1, y1, x2, y2))

        # Begin animation loop.
        self.master.after(FLIP_ANIM_INTERVAL_MS, self._animate_flip_frame)

    def _animate_flip_frame(self) -> None:
        """Advance one animation frame for all flipping discs."""
        total = FLIP_ANIM_STEPS
        half = max(1, total // 2)
        step = self._anim_step
        new_color = "black" if self.current_player == 1 else "white"

        for idx, item in enumerate(self._anim_items):
            x1, y1, x2, y2 = self._anim_bounds[idx]

            if step <= half:
                scale = max(0.05, 1.0 - (step / half))
            else:
                denom = max(1, total - half)
                scale = min(1.0, (step - half) / denom)

            if FLIP_ANIM_AXIS == "vertical":
                full_h = y2 - y1
                h = max(1, int(full_h * scale))
                cy = (y1 + y2) // 2
                ny1 = cy - (h // 2)
                ny2 = cy + (h // 2)
                nx1, nx2 = x1, x2
            else:
                full_w = x2 - x1
                w = max(1, int(full_w * scale))
                cx = (x1 + x2) // 2
                nx1 = cx - (w // 2)
                nx2 = cx + (w // 2)
                ny1, ny2 = y1, y2

            # Update bounding box.
            self.canvas.coords(item, nx1, ny1, nx2, ny2)

            # Swap color at midpoint to simulate flip.
            if step == half:
                self.canvas.itemconfig(item, fill=new_color)

        self._anim_step += 1
        if self._anim_step <= total:
            self.master.after(FLIP_ANIM_INTERVAL_MS, self._animate_flip_frame)
        else:
            self._finalize_flip_animation()

    def _finalize_flip_animation(self) -> None:
        """Cleanup animation overlays, apply flips to board, and update game state."""
        for item in self._anim_items:
            self.canvas.delete(item)

        for fx, fy in self._anim_flips:
            self.board[fx][fy] = self.current_player

        self._anim_items = []
        self._anim_bounds = []
        self._anim_flips = []
        self._anim_step = 0
        self.animating = False

        self.switch_player()
        self.update_game_state()

    def valid_move(self, x: int, y: int, player: int) -> bool:
        """Check if placing a piece for 'player' at (x, y) is valid."""
        if self.board[x][y] is not None:
            return False
        for dx, dy in DIRECTIONS:
            i, j = x + dx, y + dy
            pieces_to_flip: List[Tuple[int, int]] = []
            while 0 <= i < self.size and 0 <= j < self.size and self.board[i][j] == 1 - player:
                pieces_to_flip.append((i, j))
                i += dx
                j += dy
            if (
                0 <= i < self.size
                and 0 <= j < self.size
                and self.board[i][j] == player
                and len(pieces_to_flip) > 0
            ):
                return True
        return False

    def update_turn_label(self) -> None:
        """Update the turn label to indicate the current player."""
        color = "Black" if self.current_player == 1 else "White"
        self.turn_label.config(text=f"{color}'s turn")

    def update_count_label(self) -> None:
        """Update the piece counts for both players."""
        black_count = sum(col.count(1) for col in self.board)
        white_count = sum(col.count(0) for col in self.board)
        self.count_label.config(text=f"Black: {black_count}, White: {white_count}")

    def game_over(self) -> None:
        """Handle the end-of-game logic and offer to restart."""
        black_count = sum(col.count(1) for col in self.board)
        white_count = sum(col.count(0) for col in self.board)

        if black_count > white_count:
            winner = "Black"
        elif white_count > black_count:
            winner = "White"
        else:
            winner = "No one, it's a draw"

        messagebox.showinfo("Game Over", f"Game Over! {winner} wins!")
        restart = messagebox.askyesno("Game Over", "Do you want to play again?")
        if restart:
            self.reset()
        else:
            self.master.quit()

    def ai_move(self) -> None:
        """
        Perform an AI move for the current player (white, if single-player).
        Difficulty:
            - easy: random valid move
            - medium: flip-most heuristic
            - hard: alpha-beta minimax with positional/mobility heuristic
        """
        valid_moves = self.get_valid_moves_on_board(self.board, self.current_player)
        if not valid_moves:
            logging.info("AI has no valid moves.")
            self.switch_player()
            self.update_game_state()
            return

        if self.ai_difficulty == "easy":
            move = random.choice([(x, y) for x, y, _ in valid_moves])
        elif self.ai_difficulty == "medium":
            best_score = -float("inf")
            best_move: Optional[Tuple[int, int]] = None
            for x, y, _ in valid_moves:
                score = self.evaluate_move(x, y)
                if score > best_score:
                    best_score = score
                    best_move = (x, y)
            move = best_move if best_move is not None else random.choice([(x, y) for x, y, _ in valid_moves])
        else:
            depth = self.get_hard_depth()
            _score, best_move = self.minimax(
                board=self.board,
                player=self.current_player,
                depth=depth,
                alpha=-float("inf"),
                beta=float("inf"),
                ai_player=self.current_player,
            )
            if best_move is None:
                best_move = random.choice([(x, y) for x, y, _ in valid_moves])
            move = best_move

        if move:
            self.make_move(*move)

            # If an animation is in progress, defer turn switching and UI updates.
            if self.animating:
                return

            self.switch_player()
            self.update_game_state()

    def evaluate_move(self, x: int, y: int) -> int:
        """Score a move by counting bracketed opponent pieces across all directions."""
        score = 0
        for dx, dy in DIRECTIONS:
            i, j = x + dx, y + dy
            local_score = 0
            while 0 <= i < self.size and 0 <= j < self.size and self.board[i][j] == 1 - self.current_player:
                local_score += 1
                i += dx
                j += dy
            if 0 <= i < self.size and 0 <= j < self.size and self.board[i][j] == self.current_player:
                score += local_score
        return score

    def is_game_over(self) -> bool:
        """Return True if neither player has a valid move."""
        black_has = any(self.valid_move(x, y, 1) for x in range(self.size) for y in range(self.size))
        white_has = any(self.valid_move(x, y, 0) for x in range(self.size) for y in range(self.size))
        return not (black_has or white_has)

    # ---------- AI Helper Methods (board-agnostic variants) ----------

    def valid_move_on_board(self, board: List[List[Optional[int]]], x: int, y: int, player: int) -> bool:
        """Check valid move against a given board snapshot."""
        if board[x][y] is not None:
            return False
        for dx, dy in DIRECTIONS:
            i, j = x + dx, y + dy
            pieces_to_flip: List[Tuple[int, int]] = []
            while 0 <= i < self.size and 0 <= j < self.size and board[i][j] == 1 - player:
                pieces_to_flip.append((i, j))
                i += dx
                j += dy
            if (
                0 <= i < self.size
                and 0 <= j < self.size
                and board[i][j] == player
                and len(pieces_to_flip) > 0
            ):
                return True
        return False

    def get_valid_moves_on_board(
        self, board: List[List[Optional[int]]], player: int
    ) -> List[Tuple[int, int, List[Tuple[int, int]]]]:
        """Return valid moves and associated flips for 'player' on 'board'."""
        moves: List[Tuple[int, int, List[Tuple[int, int]]]] = []
        for x in range(self.size):
            for y in range(self.size):
                if board[x][y] is None:
                    flips = self.collect_flips_on_board(board, x, y, player)
                    if flips:
                        moves.append((x, y, flips))
        return moves

    def collect_flips_on_board(
        self, board: List[List[Optional[int]]], x: int, y: int, player: int
    ) -> List[Tuple[int, int]]:
        """Collect coordinates that would be flipped if 'player' moves at (x, y)."""
        if board[x][y] is not None:
            return []
        flips: List[Tuple[int, int]] = []
        for dx, dy in DIRECTIONS:
            i, j = x + dx, y + dy
            line: List[Tuple[int, int]] = []
            while 0 <= i < self.size and 0 <= j < self.size and board[i][j] == 1 - player:
                line.append((i, j))
                i += dx
                j += dy
            if 0 <= i < self.size and 0 <= j < self.size and board[i][j] == player and line:
                flips.extend(line)
        return flips

    def apply_move_on_board(
        self,
        board: List[List[Optional[int]]],
        x: int,
        y: int,
        player: int,
        flips: List[Tuple[int, int]],
    ) -> List[List[Optional[int]]]:
        """Return a new board with 'player' moved at (x, y) and flips applied."""
        new_board = [col[:] for col in board]
        new_board[x][y] = player
        for fx, fy in flips:
            new_board[fx][fy] = player
        return new_board

    def compute_position_weights(self) -> List[List[int]]:
        """Compute positional weights for evaluation for current board size."""
        n = self.size
        weights = [[1 for _ in range(n)] for _ in range(n)]

        corners = [(0, 0), (0, n - 1), (n - 1, 0), (n - 1, n - 1)]
        for cx, cy in corners:
            weights[cx][cy] = 100

        adjacent_offsets = [(1, 0), (0, 1), (1, 1), (-1, 0), (0, -1), (-1, -1)]
        for cx, cy in corners:
            for ox, oy in adjacent_offsets:
                nx = cx + (ox if cx == 0 else -ox if cx == n - 1 else ox)
                ny = cy + (oy if cy == 0 else -oy if cy == n - 1 else oy)
                if 0 <= nx < n and 0 <= ny < n and (nx, ny) not in corners:
                    weights[nx][ny] = -25

        for i in range(n):
            for j in range(n):
                if i in (0, n - 1) or j in (0, n - 1):
                    if weights[i][j] == 1:
                        weights[i][j] = 10

        for i in range(n):
            for j in range(n):
                if (
                    (i == 1 or i == n - 2 or j == 1 or j == n - 2)
                    and weights[i][j] == 1
                    and (i, j) not in corners
                ):
                    weights[i][j] = 3
        return weights

    def evaluate_board(self, board: List[List[Optional[int]]], pov_player: int) -> int:
        """
        Evaluate 'board' from the point of view of 'pov_player'.
        Combines disc difference, mobility, and positional weights.
        """
        opp = 1 - pov_player

        my_discs = sum(col.count(pov_player) for col in board)
        opp_discs = sum(col.count(opp) for col in board)
        disc_diff = my_discs - opp_discs

        my_moves = len(self.get_valid_moves_on_board(board, pov_player))
        opp_moves = len(self.get_valid_moves_on_board(board, opp))
        mobility_diff = my_moves - opp_moves

        pos_score_my = 0
        pos_score_opp = 0
        for x in range(self.size):
            for y in range(self.size):
                if board[x][y] == pov_player:
                    pos_score_my += self.positional_weights[x][y]
                elif board[x][y] == opp:
                    pos_score_opp += self.positional_weights[x][y]
        pos_diff = pos_score_my - pos_score_opp

        return (1 * disc_diff) + (5 * mobility_diff) + (1 * pos_diff)

    def minimax(
        self,
        board: List[List[Optional[int]]],
        player: int,
        depth: int,
        alpha: float,
        beta: float,
        ai_player: int,
    ) -> Tuple[int, Optional[Tuple[int, int]]]:
        """Alpha-beta minimax search."""
        opp = 1 - player
        moves = self.get_valid_moves_on_board(board, player)

        no_moves_current = len(moves) == 0
        no_moves_opponent = len(self.get_valid_moves_on_board(board, opp)) == 0
        if depth == 0 or (no_moves_current and no_moves_opponent):
            return self.evaluate_board(board, ai_player), None

        if no_moves_current:
            return self.minimax(board, opp, depth - 1, alpha, beta, ai_player)

        def move_order_key(item: Tuple[int, int, List[Tuple[int, int]]]) -> int:
            mx, my, flips = item
            corner_bonus = (
                1000
                if (mx, my)
                in [
                    (0, 0),
                    (0, self.size - 1),
                    (self.size - 1, 0),
                    (self.size - 1, self.size - 1),
                ]
                else 0
            )
            edge_bonus = 200 if (mx in (0, self.size - 1) or my in (0, self.size - 1)) else 0
            return corner_bonus + edge_bonus + len(flips)

        moves.sort(key=move_order_key, reverse=True)

        maximizing = player == ai_player
        best_move: Optional[Tuple[int, int]] = None

        if maximizing:
            value = -float("inf")
            for x, y, flips in moves:
                new_board = self.apply_move_on_board(board, x, y, player, flips)
                child_value, _ = self.minimax(new_board, opp, depth - 1, alpha, beta, ai_player)
                if child_value > value:
                    value = child_value
                    best_move = (x, y)
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return int(value), best_move

        value = float("inf")
        for x, y, flips in moves:
            new_board = self.apply_move_on_board(board, x, y, player, flips)
            child_value, _ = self.minimax(new_board, opp, depth - 1, alpha, beta, ai_player)
            if child_value < value:
                value = child_value
                best_move = (x, y)
            beta = min(beta, value)
            if beta <= alpha:
                break
        return int(value), best_move

    def get_hard_depth(self) -> int:
        """
        Choose a minimax depth appropriate for board size and state to keep UI responsive.
        Larger boards get shallower search.
        """
        remaining_empty = sum(cell is None for col in self.board for cell in col)
        if self.size <= 8:
            if remaining_empty <= 12:
                return 4
            return 3
        if self.size <= 12:
            return 3
        if self.size <= 16:
            return 2
        return 2


def main_menu() -> None:
    """Create the main menu window with options to start the game."""
    root = tk.Tk()
    root.title("Reversi")

    menu_frame = tk.Frame(root)
    menu_frame.pack(padx=12, pady=12)

    def start_game(single_player: bool, difficulty: str = DEFAULT_AI_DIFFICULTY) -> None:
        """Start a new game after asking the user for the board size."""
        size = simpledialog.askinteger(
            "Input",
            "Enter the size of the board (even number between 8 and 60):",
            minvalue=8,
            maxvalue=60,
            parent=root,
        )
        if size is None:
            return
        if size % 2 != 0:
            messagebox.showerror("Error", "Size must be an even number.")
            return

        menu_frame.pack_forget()
        ReversiBoard(root, size=size, cell_size=13, single_player=single_player, ai_difficulty=difficulty)

    tk.Label(menu_frame, text="Reversi").pack(pady=(0, 8))

    tk.Button(menu_frame, text="Single Player (Easy)", command=lambda: start_game(True, "easy")).pack(
        fill="x", pady=4
    )
    tk.Button(menu_frame, text="Single Player (Medium)", command=lambda: start_game(True, "medium")).pack(
        fill="x", pady=4
    )
    tk.Button(menu_frame, text="Single Player (Hard)", command=lambda: start_game(True, "hard")).pack(
        fill="x", pady=4
    )

    tk.Button(menu_frame, text="Local Multiplayer", command=lambda: start_game(False)).pack(fill="x", pady=4)
    tk.Button(menu_frame, text="Quit", command=root.quit).pack(fill="x", pady=4)

    root.mainloop()


if __name__ == "__main__":
    main_menu()