import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw
import random
import asyncio
import math
import re

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

# Validate token before starting
if not TOKEN:
    print("❌ Error: TOKEN not found in .env file")
    exit(1)

# Bot configuration
BOARD_SIZE = 400
CELL_SIZE = BOARD_SIZE // 3
LINE_WIDTH = 8
X_COLOR = (220, 60, 60)
O_COLOR = (70, 130, 220)
GRID_COLOR = (40, 40, 40)
BG_COLOR = (250, 250, 250)
ACCENT_COLORS = [
    (240, 180, 60),
    (150, 220, 120),
    (220, 140, 240),
    (80, 200, 220)
]

# Enable necessary intents
intents = discord.Intents.default()
intents.message_content = True

class TicTacToeBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            activity=discord.Game(name="Tic Tac Toe | /commands"),
            status=discord.Status.online,
            help_command=None
        )
        self.games = {}
        self.locks = {}  # For concurrency control

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced globally")

bot = TicTacToeBot()

class GameState:
    def __init__(self, p1, p2, difficulty=None):
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.players = [p1, p2]
        self.turn = 0
        self.message_id = None
        self.colors = [
            random.choice(ACCENT_COLORS),
            random.choice(ACCENT_COLORS)
        ]
        self.difficulty = difficulty
        self.is_against_ai = isinstance(p2, str)  # AI is represented as string

    def mark(self, row, col):
        if self.board[row][col] != "":
            return False
        self.board[row][col] = "X" if self.turn == 0 else "O"
        return True

    def check_win(self):
        return check_board_win(self.board)  # Use unified win check

# Unified win check function
def check_board_win(board):
    # Check rows
    for row in board:
        if row[0] == row[1] == row[2] != "":
            return row[0]
    # Check columns
    for col in range(3):
        if board[0][col] == board[1][col] == board[2][col] != "":
            return board[0][col]
    # Check diagonals
    if board[0][0] == board[1][1] == board[2][2] != "":
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != "":
        return board[0][2]
    # Check for draw
    if all(cell != "" for row in board for cell in row):
        return "Draw"
    return None

def draw_x(draw, x, y, size, color, width):
    offset = size * 0.2
    draw.line([(x + offset, y + offset), 
               (x + size - offset, y + size - offset)], 
              fill=color, width=width)
    draw.line([(x + size - offset, y + offset), 
               (x + offset, y + size - offset)], 
              fill=color, width=width)

def draw_o(draw, x, y, size, color, width):
    offset = size * 0.2
    draw.ellipse([x + offset, y + offset, 
                  x + size - offset, y + size - offset], 
                 outline=color, width=width)

def draw_board(board, colors):
    img = Image.new("RGB", (BOARD_SIZE, BOARD_SIZE), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    for i in range(1, 3):
        draw.line([(i * CELL_SIZE, 0), 
                   (i * CELL_SIZE, BOARD_SIZE)], 
                  fill=GRID_COLOR, width=LINE_WIDTH)
        draw.line([(0, i * CELL_SIZE), 
                   (BOARD_SIZE, i * CELL_SIZE)], 
                  fill=GRID_COLOR, width=LINE_WIDTH)
    
    mark_size = CELL_SIZE * 0.8
    mark_width = int(CELL_SIZE * 0.15)
    
    for r in range(3):
        for c in range(3):
            mark = board[r][c]
            x = c * CELL_SIZE + (CELL_SIZE - mark_size) / 2
            y = r * CELL_SIZE + (CELL_SIZE - mark_size) / 2
            
            if mark == "X":
                draw_x(draw, x, y, mark_size, X_COLOR, mark_width)
            elif mark == "O":
                draw_o(draw, x, y, mark_size, O_COLOR, mark_width)
    
    corner_size = CELL_SIZE // 4
    for pos in [(0, 0), (BOARD_SIZE - corner_size, 0),
                (0, BOARD_SIZE - corner_size), 
                (BOARD_SIZE - corner_size, BOARD_SIZE - corner_size)]:
        draw.rectangle([pos[0], pos[1], 
                        pos[0] + corner_size, 
                        pos[1] + corner_size], 
                       fill=random.choice(colors))
    
    return img

def create_embed(title, description, color=0x3498db):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    embed.set_footer(text="Tic Tac Toe Ultimate | /commands for help")
    return embed

# AI Logic
def get_empty_cells(board):
    return [(r, c) for r in range(3) for c in range(3) if board[r][c] == ""]

def get_random_move(board):
    empty = get_empty_cells(board)
    return random.choice(empty) if empty else (0, 0)

def get_medium_move(board, ai_mark):
    # Try to win if possible
    for r, c in get_empty_cells(board):
        board[r][c] = ai_mark
        if check_board_win(board) == ai_mark:
            board[r][c] = ""
            return r, c
        board[r][c] = ""
    
    # Block opponent win
    opponent_mark = "O" if ai_mark == "X" else "X"
    for r, c in get_empty_cells(board):
        board[r][c] = opponent_mark
        if check_board_win(board) == opponent_mark:
            board[r][c] = ""
            return r, c
        board[r][c] = ""
    
    # Strategic moves
    if board[1][1] == "":  # Center is best
        return 1, 1
    
    # Take a corner if available
    corners = [(0, 0), (0, 2), (2, 0), (2, 2)]
    empty_corners = [c for c in corners if board[c[0]][c[1]] == ""]
    if empty_corners:
        return random.choice(empty_corners)
    
    # Otherwise random
    return get_random_move(board)

def minimax(board, depth, is_maximizing, ai_mark, alpha=-math.inf, beta=math.inf):
    opponent_mark = "O" if ai_mark == "X" else "X"
    
    # Check game state
    result = check_board_win(board)
    if result == ai_mark:
        return 10 - depth
    elif result == opponent_mark:
        return depth - 10
    elif result == "Draw":
        return 0
    
    if is_maximizing:
        best_score = -math.inf
        for r, c in get_empty_cells(board):
            board[r][c] = ai_mark
            score = minimax(board, depth + 1, False, ai_mark, alpha, beta)
            board[r][c] = ""
            best_score = max(score, best_score)
            alpha = max(alpha, best_score)
            if beta <= alpha:
                break
        return best_score
    else:
        best_score = math.inf
        for r, c in get_empty_cells(board):
            board[r][c] = opponent_mark
            score = minimax(board, depth + 1, True, ai_mark, alpha, beta)
            board[r][c] = ""
            best_score = min(score, best_score)
            beta = min(beta, best_score)
            if beta <= alpha:
                break
        return best_score

def get_hard_move(board, ai_mark):
    best_score = -math.inf
    best_move = None
    
    for r, c in get_empty_cells(board):
        board[r][c] = ai_mark
        score = minimax(board, 0, False, ai_mark)
        board[r][c] = ""
        
        if score > best_score:
            best_score = score
            best_move = (r, c)
    
    return best_move

def ai_move(game):
    """Make an AI move based on difficulty level"""
    ai_mark = "O" if game.turn == 1 else "X"
    
    if game.difficulty == "easy":
        return get_random_move(game.board)
    elif game.difficulty == "medium":
        return get_medium_move(game.board, ai_mark)
    elif game.difficulty == "hard":
        return get_hard_move(game.board, ai_mark)
    
    return get_random_move(game.board)

async def make_ai_move(channel_id):
    """Process AI move and update game state"""
    # Check if game still exists after sleep
    await asyncio.sleep(1.0)
    if channel_id not in bot.games:
        return
    
    game = bot.games[channel_id]
    
    # Make sure it's AI's turn
    if not game.is_against_ai or game.players[game.turn] != "AI":
        return
    
    # Get AI move
    row, col = ai_move(game)
    
    # Make the move
    game.mark(row, col)
    
    # Update board image
    board_img = draw_board(game.board, game.colors)
    board_img.save(f"board_{channel_id}.png")
    
    # Check win condition
    result = game.check_win()
    
    # FIX: Get channel and validate it exists
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"⚠️ Error: Channel {channel_id} not found")
        # Cleanup
        try:
            os.remove(f"board_{channel_id}.png")
        except:
            pass
        del bot.games[channel_id]
        return
    
    if result:
        # Game over
        if result == "Draw":
            title = "🤝 It's a Draw!"
            description = "No moves left - the game is tied!"
            color = 0xf1c40f
        else:
            winner = game.players[0] if result == "X" else "AI"
            title = f"🎉 {winner} Wins!" if winner == "AI" else f"🎉 {winner.display_name} Wins!"
            description = f"**{winner}** has won the game as `{result}`!" if winner == "AI" else f"**{winner.mention}** has won the game as `{result}`!"
            color = 0x2ecc71
        
        embed = create_embed(title, description, color)
        embed.set_image(url=f"attachment://board_{channel_id}.png")
        
        try:
            message = await channel.fetch_message(game.message_id)
            await message.delete()
        except:
            pass
        
        await channel.send(
            embed=embed,
            file=discord.File(f"board_{channel_id}.png")
        )
        
        os.remove(f"board_{channel_id}.png")
        del bot.games[channel_id]
    else:
        # Game continues
        game.turn = 1 - game.turn
        next_player = game.players[game.turn]
        
        # Create player mention for human or AI name
        player_text = "AI 🤖" if next_player == "AI" else next_player.mention
        
        embed = create_embed(
            "AI Move Played!",
            f"AI placed an `{'X' if game.turn == 1 else 'O'}`\n"
            f"**Next: {player_text}**\n"
            f"Use `/move row col` to play your turn (1-3)",
            random.choice([0x1abc9c, 0x3498db])
        )
        embed.set_image(url=f"attachment://board_{channel_id}.png")
        
        try:
            message = await channel.fetch_message(game.message_id)
            await message.delete()
        except:
            pass
        
        message = await channel.send(
            embed=embed,
            file=discord.File(f"board_{channel_id}.png")
        )
        game.message_id = message.id
        
        # If it's still AI's turn (shouldn't happen in 1vAI)
        if game.is_against_ai and game.players[game.turn] == "AI":
            await make_ai_move(channel_id)

@bot.event
async def on_ready():
    print(f"✨ Bot is online as {bot.user} ✨")
    print(f"🔗 Invite URL: https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot%20applications.commands")

# FIXED: Improved member lookup to handle mentions properly
async def get_member(ctx, input_str):
    """Robust member lookup that handles mentions properly"""
    # First check for AI difficulties
    if input_str.lower() in ["easy", "medium", "hard"]:
        return None
    
    guild = ctx.guild
    if not guild:
        return None
    
    # Try to extract user ID from mention
    # Handle both <@123> and <@!123> formats
    match = re.match(r"<@!?(\d+)>", input_str)
    if match:
        user_id = int(match.group(1))
        # First try cache
        member = guild.get_member(user_id)
        if member:
            return member
        # Then try API if not in cache
        try:
            member = await guild.fetch_member(user_id)
            return member
        except discord.NotFound:
            return None
    
    # Try to get by exact username match
    member = discord.utils.get(guild.members, name=input_str)
    if member:
        return member
    
    # Try to get by nickname match
    member = discord.utils.get(guild.members, nick=input_str)
    if member:
        return member
    
    # Try to get by user ID
    if input_str.isdigit():
        user_id = int(input_str)
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            member = await guild.fetch_member(user_id)
            return member
        except discord.NotFound:
            return None
    
    return None

@bot.hybrid_command(name="tictactoe", description="Start a Tic-Tac-Toe game")
@app_commands.describe(opponent="Player to challenge or 'easy', 'medium', 'hard' for AI")
async def tictactoe(ctx, opponent: str):
    # Setup locking for the channel
    channel_id = ctx.channel.id
    if channel_id not in bot.locks:
        bot.locks[channel_id] = asyncio.Lock()
    
    async with bot.locks[channel_id]:
        # Check for AI difficulties first
        opp_lower = opponent.lower()
        if opp_lower in ["easy", "medium", "hard"]:
            is_ai = True
            difficulty = opp_lower
            opponent_user = "AI"
        else:
            # Try to find the member
            member = await get_member(ctx, opponent)
            if member is None:
                return await ctx.send(embed=create_embed(
                    "Invalid Opponent", 
                    "Please mention a valid user or use 'easy', 'medium', 'hard' for AI", 
                    0xe74c3c
                ))
            
            is_ai = False
            difficulty = None
            opponent_user = member
        
        if ctx.channel.id in bot.games:
            return await ctx.send(embed=create_embed(
                "Game Already in Progress", 
                "There's already a game running in this channel!", 
                0xe74c3c
            ))
        
        if not is_ai:
            if opponent_user.bot or opponent_user == ctx.author:
                return await ctx.send(embed=create_embed(
                    "Invalid Opponent", 
                    "Please choose a valid human opponent!", 
                    0xe74c3c
                ))
        
        # Create game state
        bot.games[ctx.channel.id] = GameState(ctx.author, opponent_user, difficulty)
        game = bot.games[ctx.channel.id]
        
        # Handle AI going first
        if is_ai:
            game.turn = 1  # Set AI to go first
        
        # Create initial board
        board_img = draw_board(game.board, game.colors)
        board_img.save(f"board_{ctx.channel.id}.png")
        
        # Create embed based on game type
        if is_ai:
            title = "🎮 Game Against AI Started!"
            description = (f"**{ctx.author.mention} (X)** vs **AI: {difficulty.capitalize()} 🤖 (O)**\n"
                        f"{'AI goes first! 🤖' if game.turn == 1 else f'{ctx.author.mention} goes first!'}")
            color = 0x9b59b6
        else:
            title = "🎮 Game Started!"
            description = (f"**{ctx.author.mention} (X)** vs **{opponent_user.mention} (O)**\n"
                        f"{ctx.author.mention} goes first! Use `/move row col` to play (1-3)")
            color = random.choice([0x1abc9c, 0x3498db, 0x9b59b6])
        
        embed = create_embed(title, description, color)
        embed.set_image(url=f"attachment://board_{ctx.channel.id}.png")
        
        message = await ctx.send(
            embed=embed,
            file=discord.File(f"board_{ctx.channel.id}.png")
        )
        game.message_id = message.id
        
        # If playing against AI and AI goes first
        if is_ai and game.turn == 1:
            await make_ai_move(ctx.channel.id)

@bot.hybrid_command(name="move", description="Make your move in the current game")
@app_commands.describe(row="Row number (1-3)", column="Column number (1-3)")
async def move(ctx, row: int, column: int):
    channel_id = ctx.channel.id
    if channel_id not in bot.locks:
        bot.locks[channel_id] = asyncio.Lock()
    
    async with bot.locks[channel_id]:
        if channel_id not in bot.games:
            return await ctx.send(embed=create_embed(
                "No Active Game", 
                "Start a game first with `/tictactoe @player`", 
                0xe74c3c
            ))
        
        game = bot.games[channel_id]
        
        # Check if playing against AI and it's AI's turn
        if game.is_against_ai and game.players[game.turn] == "AI":
            return await ctx.send(embed=create_embed(
                "Not Your Turn", 
                "It's the AI's turn right now!", 
                0xe74c3c
            ))
        
        # Proper turn validation
        if game.is_against_ai:
            # For AI games, only the human player can move
            if ctx.author != game.players[0]:
                return await ctx.send(embed=create_embed(
                    "Not a Player", 
                    "You're not part of this game!", 
                    0xe74c3c
                ))
        else:
            # For multiplayer games
            if ctx.author not in game.players:
                return await ctx.send(embed=create_embed(
                    "Not a Player", 
                    "You're not part of this game!", 
                    0xe74c3c
                ))
            
            # Only allow the current player to move
            if ctx.author != game.players[game.turn]:
                return await ctx.send(embed=create_embed(
                    "Not Your Turn", 
                    f"It's {game.players[game.turn].mention}'s turn!", 
                    0xe74c3c
                ))
        
        # Validate move range (1-3)
        if not (1 <= row <= 3 and 1 <= column <= 3):
            return await ctx.send(embed=create_embed(
                "Invalid Move", 
                "Row and column must be between 1 and 3", 
                0xe74c3c
            ))
        
        # Convert to 0-indexed for internal use
        row0 = row - 1
        col0 = column - 1
        
        if not game.mark(row0, col0):
            return await ctx.send(embed=create_embed(
                "Invalid Move", 
                "That space is already taken!", 
                0xe74c3c
            ))
        
        # Update board image
        board_img = draw_board(game.board, game.colors)
        board_img.save(f"board_{channel_id}.png")
        
        result = game.check_win()
        
        if result:
            # Game over
            if result == "Draw":
                title = "🤝 It's a Draw!"
                description = "No moves left - the game is tied!"
                color = 0xf1c40f
            else:
                if game.is_against_ai:
                    winner = game.players[0] if result == "X" else "AI"
                    title = f"🎉 {winner} Wins!" if winner == "AI" else f"🎉 {ctx.author.display_name} Wins!"
                    description = f"**{winner}** has won the game as `{result}`!" if winner == "AI" else f"**{ctx.author.mention}** has won the game as `{result}`!"
                else:
                    winner = game.players[0] if result == "X" else game.players[1]
                    title = f"🎉 {winner.display_name} Wins!"
                    description = f"**{winner.mention}** has won the game as `{result}`!"
                color = 0x2ecc71
            
            embed = create_embed(title, description, color)
            embed.set_image(url=f"attachment://board_{channel_id}.png")
            
            try:
                message = await ctx.channel.fetch_message(game.message_id)
                await message.delete()
            except:
                pass
            
            await ctx.send(
                embed=embed,
                file=discord.File(f"board_{channel_id}.png")
            )
            
            # Cleanup
            os.remove(f"board_{channel_id}.png")
            del bot.games[channel_id]
        else:
            # Game continues
            game.turn = 1 - game.turn
            next_player = game.players[game.turn]
            
            # Create player mention for human or AI name
            player_text = "AI 🤖" if next_player == "AI" else next_player.mention
            
            # Create message based on next player
            if next_player == "AI":
                message_text = (f"{ctx.author.mention} placed an `{'X' if game.turn == 1 else 'O'}`\n"
                                f"**Next: {player_text}**\n"
                                f"AI is thinking...")
            else:
                message_text = (f"{ctx.author.mention} placed an `{'X' if game.turn == 1 else 'O'}`\n"
                                f"**Next: {player_text}**\n"
                                f"Use `/move row col` to play your turn (1-3)")
            
            embed = create_embed(
                "Move Played!",
                message_text,
                random.choice([0x1abc9c, 0x3498db])
            )
            embed.set_image(url=f"attachment://board_{channel_id}.png")
            
            try:
                message = await ctx.channel.fetch_message(game.message_id)
                await message.delete()
            except:
                pass
            
            message = await ctx.send(
                embed=embed,
                file=discord.File(f"board_{channel_id}.png")
            )
            game.message_id = message.id
            
            # If next player is AI, trigger AI move
            if game.is_against_ai and next_player == "AI":
                await make_ai_move(channel_id)

@bot.hybrid_command(name="cancel", description="Cancel the current game")
async def cancel(ctx):
    channel_id = ctx.channel.id
    if channel_id in bot.locks and channel_id in bot.games:
        async with bot.locks[channel_id]:
            if channel_id in bot.games:
                try:
                    os.remove(f"board_{channel_id}.png")
                except:
                    pass
                
                try:
                    message = await ctx.channel.fetch_message(bot.games[channel_id].message_id)
                    await message.delete()
                except:
                    pass
                
                del bot.games[channel_id]
                await ctx.send(embed=create_embed(
                    "Game Canceled", 
                    "The current game has been canceled", 
                    0x95a5a6
                ))
    else:
        await ctx.send(embed=create_embed(
            "No Game Found", 
            "There's no active game in this channel", 
            0x95a5a6
        ))

@bot.hybrid_command(name="commands", description="Show available commands")
async def show_commands(ctx):
    """Show help information"""
    embed = create_embed(
        "❓ Tic Tac Toe Commands",
        "Here are all the commands you can use:",
        0x9b59b6
    )
    
    commands_list = [
        ("`/tictactoe @player`", "Start a new game with another player"),
        ("`/tictactoe easy`", "Play against Easy AI"),
        ("`/tictactoe medium`", "Play against Medium AI"),
        ("`/tictactoe hard`", "Play against Hard AI"),
        ("`/move <row> <col>`", "Make your move (1-3 for both)"),
        ("`/cancel`", "Cancel the current game"),
        ("`/commands`", "Show this help message"),
        ("`/ping`", "Check bot latency")
    ]
    
    for name, value in commands_list:
        embed.add_field(name=name, value=value, inline=False)
    
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="ping", description="Check bot latency")
async def ping(ctx):
    """Check the bot's latency"""
    latency = round(bot.latency * 1000)
    color = 0x2ecc71 if latency < 100 else 0xf39c12 if latency < 300 else 0xe74c3c
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: **{latency}ms**",
        color=color
    )
    await ctx.send(embed=embed)

if __name__ == '__main__':
    bot.run(TOKEN)