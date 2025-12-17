# stockfish_bot.py - Updated with time control delay ranges

import multiprocess
from stockfish import Stockfish
import pyautogui
import random
import time
import sys
import os
import chess
import re
from grabbers.chesscom_grabber import ChesscomGrabber
from grabbers.lichess_grabber import LichessGrabber
from utilities import char_to_num
import keyboard


class StockfishBot(multiprocess.Process):
    def __init__(
        self,
        chrome_url,
        chrome_session_id,
        website,
        pipe,
        overlay_queue,
        stockfish_path,
        enable_manual_mode,
        enable_mouseless_mode,
        enable_non_stop_puzzles,
        enable_non_stop_matches,
        mouse_latency,
        bongcloud,
        slow_mover,
        skill_level,
        stockfish_depth,
        memory,
        cpu_threads,
        enable_random_delay,
        delay_min=1,  # New parameter for minimum delay
        delay_max=20,  # New parameter for maximum delay
    ):
        multiprocess.Process.__init__(self)
        self.chrome_url = chrome_url
        self.chrome_session_id = chrome_session_id
        self.website = website
        self.pipe = pipe
        self.overlay_queue = overlay_queue
        self.stockfish_path = stockfish_path
        self.enable_manual_mode = enable_manual_mode
        self.enable_mouseless_mode = enable_mouseless_mode
        self.enable_non_stop_puzzles = enable_non_stop_puzzles
        self.enable_non_stop_matches = enable_non_stop_matches
        self.mouse_latency = mouse_latency
        self.bongcloud = bongcloud
        self.slow_mover = slow_mover
        self.skill_level = skill_level
        self.stockfish_depth = stockfish_depth
        self.grabber = None
        self.memory = memory
        self.cpu_threads = cpu_threads
        self.enable_random_delay = enable_random_delay
        self.delay_min = delay_min  # Store delay range
        self.delay_max = delay_max
        self.is_white = None

    def move_to_screen_pos(self, move):
        """Convert chess move to screen coordinates"""
        canvas_x_offset, canvas_y_offset = self.grabber.get_top_left_corner()
        board_x = canvas_x_offset + self.grabber.get_board().location["x"]
        board_y = canvas_y_offset + self.grabber.get_board().location["y"]
        square_size = self.grabber.get_board().size['width'] / 8
        
        if self.is_white:
            x = board_x + square_size * (char_to_num(move[0]) - 1) + square_size / 2
            y = board_y + square_size * (8 - int(move[1])) + square_size / 2
        else:
            x = board_x + square_size * (8 - char_to_num(move[0])) + square_size / 2
            y = board_y + square_size * (int(move[1]) - 1) + square_size / 2
        return x, y

    def get_move_pos(self, move):
        """Get start and end positions for a move"""
        start_pos_x, start_pos_y = self.move_to_screen_pos(move[0:2])
        end_pos_x, end_pos_y = self.move_to_screen_pos(move[2:4])
        return (start_pos_x, start_pos_y), (end_pos_x, end_pos_y)

    def make_move(self, move):
        """Execute a chess move on screen"""
        start_pos, end_pos = self.get_move_pos(move)
        pyautogui.moveTo(start_pos[0], start_pos[1])
        time.sleep(self.mouse_latency)
        pyautogui.dragTo(end_pos[0], end_pos[1])
        
        # Handle pawn promotion
        if len(move) == 5:
            time.sleep(0.1)
            end_pos_x = None
            end_pos_y = None
            if move[4] == "n":
                end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 1))
            elif move[4] == "r":
                end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 2))
            elif move[4] == "b":
                end_pos_x, end_pos_y = self.move_to_screen_pos(move[2] + str(int(move[3]) - 3))
            pyautogui.moveTo(x=end_pos_x, y=end_pos_y)
            pyautogui.click(button='left')

    def wait_for_gui_to_delete(self):
        """Wait for GUI confirmation"""
        while self.pipe.recv() != "DELETE":
            pass

    def human_delay(self):
        """Add human-like delay between moves"""
        if self.enable_random_delay:
            delay = random.uniform(self.delay_min, self.delay_max)
            time.sleep(delay)

    def go_to_next_puzzle(self):
        """Navigate to next puzzle"""
        self.grabber.click_puzzle_next()
        self.pipe.send("RESTART")
        self.wait_for_gui_to_delete()

    def find_new_online_match(self):
        """Start new online match"""
        time.sleep(2)
        self.grabber.click_game_next()
        self.pipe.send("RESTART")
        self.wait_for_gui_to_delete()

    def run(self):
        """Main bot execution loop"""
        # Initialize grabber
        if self.website == "chesscom":
            self.grabber = ChesscomGrabber(self.chrome_url, self.chrome_session_id)
        else:
            self.grabber = LichessGrabber(self.chrome_url, self.chrome_session_id)

        self.grabber.reset_moves_list()
        
        # Initialize Stockfish
        parameters = {
            "Threads": self.cpu_threads,
            "Hash": self.memory,
            "Ponder": "true",
            "Slow Mover": self.slow_mover,
            "Skill Level": self.skill_level,
        }
        
        try:
            stockfish = Stockfish(path=self.stockfish_path, depth=self.stockfish_depth, parameters=parameters)
        except PermissionError:
            self.pipe.send("ERR_PERM")
            return
        except OSError:
            self.pipe.send("ERR_EXE")
            return

        try:
            # Verify board element exists
            self.grabber.update_board_elem()
            if self.grabber.get_board() is None:
                self.pipe.send("ERR_BOARD")
                return
            
            # Determine player color
            self.is_white = self.grabber.is_white()
            if self.is_white is None:
                self.pipe.send("ERR_COLOR")
                return
            
            # Get starting position
            move_list = self.grabber.get_move_list()
            if move_list is None:
                self.pipe.send("ERR_MOVES")
                return
            
            # Check if game is already over
            score_pattern = r"([0-9]+)\-([0-9]+)"
            if len(move_list) > 0 and re.match(score_pattern, move_list[-1]):
                self.pipe.send("ERR_GAMEOVER")
                return
            
            # Initialize board state
            board = chess.Board()
            for move in move_list:
                board.push_san(move)
            move_list_uci = [move.uci() for move in board.move_stack]
            stockfish.set_position(move_list_uci)

            # Track moves for accuracy calculation
            white_moves = []
            white_best_moves = []
            black_moves = []
            black_best_moves = []

            # Send initial evaluation
            self.send_eval_data(stockfish, board)
            self.pipe.send("START")
            
            if len(move_list) > 0:
                self.pipe.send("M_MOVE" + ",".join(move_list))

            # Main game loop
            while True:
                # Bot's turn
                if (self.is_white and board.turn == chess.WHITE) or (not self.is_white and board.turn == chess.BLACK):
                    # Calculate move
                    move = None
                    move_count = len(board.move_stack)
                    
                    # Bongcloud opening logic
                    if self.bongcloud and move_count <= 3:
                        bongcloud_moves = ["e2e3", "e7e6", "e1e2", "e8e7"]
                        move = bongcloud_moves[move_count]
                        if not board.is_legal(chess.Move.from_uci(move)):
                            move = stockfish.get_best_move()
                    else:
                        move = stockfish.get_best_move()

                    # Store best move for accuracy
                    if board.turn == chess.WHITE:
                        white_best_moves.append(move)
                    else:
                        black_best_moves.append(move)

                    # Manual mode handling
                    self_moved = False
                    if self.enable_manual_mode:
                        move_start_pos, move_end_pos = self.get_move_pos(move)
                        self.overlay_queue.put([
                            (
                                (int(move_start_pos[0]), int(move_start_pos[1])),
                                (int(move_end_pos[0]), int(move_end_pos[1])),
                            ),
                        ])
                        
                        while True:
                            if keyboard.is_pressed("3"):
                                break
                            if len(move_list) != len(self.grabber.get_move_list()):
                                self_moved = True
                                move_list = self.grabber.get_move_list()
                                move_san = move_list[-1]
                                move = board.parse_san(move_san).uci()
                                
                                if board.turn == chess.WHITE:
                                    white_moves.append(move)
                                else:
                                    black_moves.append(move)
                                    
                                board.push_uci(move)
                                stockfish.make_moves_from_current_position([move])
                                break

                    if not self_moved:
                        # Add human-like delay
                        self.human_delay()
                        
                        move_san = board.san(
                            chess.Move(
                                chess.parse_square(move[0:2]),
                                chess.parse_square(move[2:4]),
                            )
                        )
                        
                        if board.turn == chess.WHITE:
                            white_moves.append(move)
                        else:
                            black_moves.append(move)
                            
                        board.push_uci(move)
                        stockfish.make_moves_from_current_position([move])
                        move_list.append(move_san)
                        
                        if self.enable_mouseless_mode and not self.grabber.is_game_puzzles():
                            self.grabber.make_mouseless_move(move, move_count + 1)
                        else:
                            self.make_move(move)

                    self.overlay_queue.put([])
                    
                    # Send evaluation update
                    self.send_eval_data(
                        stockfish,
                        board,
                        white_moves,
                        white_best_moves,
                        black_moves,
                        black_best_moves,
                    )
                    self.pipe.send("S_MOVE" + move_san)
                    
                    # Check for checkmate
                    if board.is_checkmate():
                        if self.enable_non_stop_puzzles and self.grabber.is_game_puzzles():
                            self.go_to_next_puzzle()
                        elif self.enable_non_stop_matches and not self.enable_non_stop_puzzles:
                            self.find_new_online_match()
                        return
                    
                    time.sleep(0.1)

                # Wait for opponent's move
                previous_move_list = move_list.copy()
                while True:
                    if self.grabber.is_game_over():
                        if self.enable_non_stop_puzzles and self.grabber.is_game_puzzles():
                            self.go_to_next_puzzle()
                        elif self.enable_non_stop_matches and not self.enable_non_stop_puzzles:
                            self.find_new_online_match()
                        return

                    new_move_list = self.grabber.get_move_list()
                    if new_move_list is None:
                        return

                    # Check for new game
                    if len(new_move_list) == 0 and len(move_list) > 0:
                        move_list = []
                        board = chess.Board()
                        stockfish.set_position([])
                        white_moves = []
                        white_best_moves = []
                        black_moves = []
                        black_best_moves = []
                        self.is_white = self.grabber.is_white()
                        self.pipe.send("RESTART")
                        self.wait_for_gui_to_delete()
                        self.send_eval_data(stockfish, board)
                        self.pipe.send("START")
                        break

                    # Opponent made a move
                    if len(new_move_list) > len(previous_move_list):
                        move_list = new_move_list
                        break

                # Process opponent's move
                move = move_list[-1]
                prev_board = board.copy()
                board.push_san(move)
                move_uci = prev_board.parse_san(move).uci()

                # Store move for accuracy
                if prev_board.turn == chess.WHITE:
                    white_moves.append(move_uci)
                else:
                    black_moves.append(move_uci)

                # Get best move for comparison
                best_move = stockfish.get_best_move_time(300)
                if prev_board.turn == chess.WHITE:
                    white_best_moves.append(best_move)
                else:
                    black_best_moves.append(best_move)

                stockfish.make_moves_from_current_position([str(board.peek())])
                self.send_eval_data(
                    stockfish,
                    board,
                    white_moves,
                    white_best_moves,
                    black_moves,
                    black_best_moves,
                )
                self.pipe.send("S_MOVE" + move)

                if board.is_checkmate():
                    if self.enable_non_stop_puzzles and self.grabber.is_game_puzzles():
                        self.go_to_next_puzzle()
                    elif self.enable_non_stop_matches and not self.enable_non_stop_puzzles:
                        self.find_new_online_match()
                    return

        except Exception as e:
            print(e)
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print(exc_type, fname, exc_tb.tb_lineno)

    def send_eval_data(
        self,
        stockfish,
        board,
        white_moves=None,
        white_best_moves=None,
        black_moves=None,
        black_best_moves=None,
    ):
        """Send evaluation and statistics to GUI"""
        try:
            eval_data = stockfish.get_evaluation()
            eval_type = eval_data["type"]
            eval_value = eval_data["value"]

            # Convert to player's perspective
            player_perspective_eval_value = eval_value
            if not self.is_white:
                player_perspective_eval_value = -eval_value

            # Get WDL statistics
            try:
                wdl_stats = stockfish.get_wdl_stats()
            except Exception:
                wdl_stats = [0, 0, 0]

            # Calculate material advantage
            material = self.calculate_material_advantage(board)

            # Calculate accuracy
            white_accuracy = "-"
            black_accuracy = "-"
            
            if white_moves and white_best_moves and len(white_moves) > 0 and len(white_moves) == len(white_best_moves):
                matches = sum(1 for a, b in zip(white_moves, white_best_moves) if a == b)
                white_accuracy = f"{matches / len(white_moves) * 100:.1f}%"

            if black_moves and black_best_moves and len(black_moves) > 0 and len(black_moves) == len(black_best_moves):
                matches = sum(1 for a, b in zip(black_moves, black_best_moves) if a == b)
                black_accuracy = f"{matches / len(black_moves) * 100:.1f}%"

            # Format evaluation
            if eval_type == "cp":
                eval_str = f"{player_perspective_eval_value / 100:.2f}"
                eval_value_decimal = player_perspective_eval_value / 100
            else:
                eval_str = f"M{player_perspective_eval_value}"
                eval_value_decimal = player_perspective_eval_value

            # Format WDL
            total = sum(wdl_stats)
            if total > 0:
                is_bot_turn = (self.is_white and board.turn == chess.WHITE) or (
                    not self.is_white and board.turn == chess.BLACK
                )

                if is_bot_turn:
                    win_pct = wdl_stats[0] / total * 100
                    draw_pct = wdl_stats[1] / total * 100
                    loss_pct = wdl_stats[2] / total * 100
                else:
                    win_pct = wdl_stats[2] / total * 100
                    draw_pct = wdl_stats[1] / total * 100
                    loss_pct = wdl_stats[0] / total * 100

                wdl_str = f"{win_pct:.1f}/{draw_pct:.1f}/{loss_pct:.1f}"
            else:
                wdl_str = "?/?/?"

            # Determine bot and opponent accuracies
            bot_accuracy = white_accuracy if self.is_white else black_accuracy
            opponent_accuracy = black_accuracy if self.is_white else white_accuracy

            # Send to GUI
            data = f"EVAL|{eval_str}|{wdl_str}|{material}|{bot_accuracy}|{opponent_accuracy}"
            self.pipe.send(data)

            # Send to overlay
            overlay_data = {
                "eval": eval_value_decimal,
                "eval_type": eval_type,
            }

            board_elem = self.grabber.get_board()
            if board_elem:
                canvas_x_offset, canvas_y_offset = self.grabber.get_top_left_corner()
                overlay_data["board_position"] = {
                    "x": canvas_x_offset + board_elem.location["x"],
                    "y": canvas_y_offset + board_elem.location["y"],
                    "width": board_elem.size["width"],
                    "height": board_elem.size["height"],
                }

            overlay_data["is_white"] = self.is_white
            self.overlay_queue.put(overlay_data)

        except Exception as e:
            print(f"Error sending evaluation: {e}")

    def calculate_material_advantage(self, board):
        """Calculate material balance"""
        piece_values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
        }

        white_material = 0
        black_material = 0

        for piece_type in piece_values:
            white_material += len(board.pieces(piece_type, chess.WHITE)) * piece_values[piece_type]
            black_material += len(board.pieces(piece_type, chess.BLACK)) * piece_values[piece_type]

        advantage = white_material - black_material
        if advantage > 0:
            return f"+{advantage}"
        elif advantage < 0:
            return str(advantage)
        else:
            return "0"
