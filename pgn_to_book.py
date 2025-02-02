import chess
import chess.pgn
import struct
from collections import defaultdict
import os
from tqdm import tqdm
import random

# Generate deterministic Zobrist keys (matching your engine's keys)
random.seed(1804289383)  # Same seed as in your engine

def generate_zobrist_keys():
    """Generate Zobrist keys for chess positions."""
    # 12 piece types * 64 squares
    piece_keys = [[random.getrandbits(64) for _ in range(64)] for _ in range(12)]
    
    # Castling rights (4 possibilities)
    castling_keys = [random.getrandbits(64) for _ in range(4)]
    
    # Side to move
    side_key = random.getrandbits(64)
    
    return piece_keys, castling_keys, side_key

PIECE_KEYS, CASTLING_KEYS, SIDE_KEY = generate_zobrist_keys()

class OpeningBookEntry:
    def __init__(self, hash_val, source, target, promotion, move_type, piece):
        self.hash = hash_val
        self.source = source
        self.target = target
        self.promotion = promotion
        self.move_type = move_type
        self.piece = piece
        self.weight = 1  # Start with weight 1
        
    def increment_weight(self):
        self.weight += 1

def get_move_type(board, move):
    """Determine the type of move."""
    if board.is_capture(move):
        return 1  # capture
    if board.is_castling(move):
        return 6  # castle
    if move.promotion:
        return 2  # promotion
    if board.piece_type_at(move.from_square) == chess.PAWN and \
       abs(move.from_square - move.to_square) == 16:
        return 4  # double pawn push
    return 0  # quiet move

def get_piece_type(board, square):
    """Get piece type at square."""
    piece = board.piece_at(square)
    if piece is None:
        return 0
    offset = 0 if piece.color == chess.WHITE else 6
    return piece.piece_type + offset

def calculate_hash(board):
    """Calculate Zobrist hash for the position."""
    h = 0
    
    # Hash pieces
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            piece_idx = (piece.piece_type - 1) + (6 if not piece.color else 0)
            h ^= PIECE_KEYS[piece_idx][square]
    
    # Hash castling rights
    if board.has_kingside_castling_rights(chess.WHITE):
        h ^= CASTLING_KEYS[0]
    if board.has_queenside_castling_rights(chess.WHITE):
        h ^= CASTLING_KEYS[1]
    if board.has_kingside_castling_rights(chess.BLACK):
        h ^= CASTLING_KEYS[2]
    if board.has_queenside_castling_rights(chess.BLACK):
        h ^= CASTLING_KEYS[3]
    
    # Hash side to move
    if board.turn:
        h ^= SIDE_KEY
    
    return h

def process_pgn_file(pgn_path, min_elo=2000, max_moves=20):
    """Process a PGN file and collect opening positions."""
    positions = defaultdict(dict)
    game_count = 0
    
    # Count total games first for progress bar
    print("Counting games...")
    with open(pgn_path) as f:
        for line in f:
            if line.startswith('[Event "'):
                game_count += 1
    
    print(f"Processing {game_count} games...")
    with open(pgn_path) as pgn:
        for _ in tqdm(range(game_count)):
            game = chess.pgn.read_game(pgn)
            if game is None:
                break
                
            # Check Elo ratings
            try:
                white_elo = int(game.headers.get("WhiteElo", "0"))
                black_elo = int(game.headers.get("BlackElo", "0"))
            except ValueError:
                continue  # Skip if Elo isn't a valid number
                
            if min(white_elo, black_elo) < min_elo:
                continue
                
            board = game.board()
            move_count = 0
            
            for move in game.mainline_moves():
                if move_count >= max_moves:
                    break
                    
                key = calculate_hash(board)  # Use our own hash calculation
                move_type = get_move_type(board, move)
                piece = get_piece_type(board, move.from_square)
                
                promotion = 0
                if move.promotion:
                    promotion = {
                        chess.QUEEN: 1,
                        chess.ROOK: 2,
                        chess.BISHOP: 3,
                        chess.KNIGHT: 4
                    }[move.promotion]
                
                entry = OpeningBookEntry(
                    key, move.from_square, move.to_square,
                    promotion, move_type, piece
                )
                
                move_key = (move.from_square, move.to_square, promotion, move_type, piece)
                if move_key in positions[key]:
                    positions[key][move_key].increment_weight()
                else:
                    positions[key][move_key] = entry
                    
                board.push(move)
                move_count += 1
    
    return positions

def write_book_file(positions, output_path):
    """Write positions to binary book file."""
    print(f"Writing book to {output_path}...")
    with open(output_path, 'wb') as f:
        # Write header with explicit byte order
        magic = 0x7262_6F6F_6B69_6E67  # "rbooking" in hex
        version = 1
        
        # Debug print the values we're writing
        print(f"Writing magic number: 0x{magic:016x}")
        print(f"Writing version: {version}")
        
        # Write magic number (big-endian)
        f.write(magic.to_bytes(8, byteorder='big'))
        
        # Write version (little-endian)
        f.write(version.to_bytes(4, byteorder='little'))
        
        # Write entries
        entry_count = 0
        for pos_hash, moves in positions.items():
            for entry in moves.values():
                # Write the entry structure (32 bytes total with padding)
                f.write(entry.hash.to_bytes(8, byteorder='little'))  # Position hash (8 bytes)
                f.write(entry.source.to_bytes(1, byteorder='little'))  # Source square (1 byte)
                f.write(entry.target.to_bytes(1, byteorder='little'))  # Target square (1 byte)
                f.write(entry.promotion.to_bytes(1, byteorder='little'))  # Promotion piece (1 byte)
                f.write(entry.move_type.to_bytes(1, byteorder='little'))  # Move type (1 byte)
                f.write(entry.piece.to_bytes(1, byteorder='little'))  # Piece type (1 byte)
                f.write(entry.weight.to_bytes(2, byteorder='little'))  # Weight (2 bytes)
                f.write((0).to_bytes(2, byteorder='little'))  # Learn value (2 bytes)
                # Write padding bytes to reach 32 byte alignment
                f.write((0).to_bytes(7, byteorder='little'))  # Padding (15 bytes)
                
                entry_count += 1
        
        print(f"\nWrote {entry_count} book entries")

def main():
    # Configuration
    pgn_path = "sample_games.pgn"  # Your downloaded database
    book_path = "opening_book.bin"
    min_elo = 2200  # Minimum Elo rating to consider
    max_moves = 20  # Maximum moves to store from each game
    
    # Process PGN and create book
    positions = process_pgn_file(pgn_path, min_elo, max_moves)
    write_book_file(positions, book_path)

if __name__ == "__main__":
    main()
