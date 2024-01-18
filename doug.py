import berserk
import requests, pyaudio, threading, queue, tempfile
import soundfile as sf
import random
import chess
import chess.engine
from openai import OpenAI
from config import LICHESS_API_TOKEN, OPENAI_API_TOKEN
import pygame

# AUDIO
pygame.mixer.init()

is_first_audio_played = False  # Flag to check if the first audio has been played

# Queues for audio generation and playback
audio_generation_queue = queue.Queue()
audio_playback_queue = queue.Queue()


#CHESS CLIENT
session = berserk.TokenSession(LICHESS_API_TOKEN)
client = berserk.Client(session=session)

emulated_board = chess.Board()
engine = chess.engine.SimpleEngine.popen_uci('stockfish/stockfish-windows-x86-64-avx2.exe')

recent_moves = [] # Last 3 moves played on the board
last_player_move = [] # Last move played by the player
player_colour = '' 
previous_score = None # Scoring from Stockfish
enable_random = False

#OPENAI CLIENT
aiclient = OpenAI(api_key=OPENAI_API_TOKEN)


def process_audio_generation_queue():
    while True:
        input_text = audio_generation_queue.get()
        if input_text is None:
            break
        audio_file_path = generate_audio(input_text)
        audio_playback_queue.put(audio_file_path)
        audio_generation_queue.task_done()

def process_audio_playback_queue():
    #time.sleep(10) #Debug Only
    while True:
        audio_file_path = audio_playback_queue.get()
        if audio_file_path is None:
            #print("No audio file path found") #Debug Only
            break
        #print(audio_file_path) #Debug Only
        play_audio(audio_file_path)
        audio_playback_queue.task_done()

# Threads for processing the audio generation and playback queues
audio_generation_thread = threading.Thread(target=process_audio_generation_queue)
audio_generation_thread.start()

audio_playback_thread = threading.Thread(target=process_audio_playback_queue)
audio_playback_thread.start()

def generate_audio(input_text, model='tts-1', voice='onyx'):
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f'Bearer {OPENAI_API_TOKEN}'  # Replace with your actual API key
    }
    data = {
        "model": model,
        "input": input_text,
        "voice": voice,
        "response_format": "opus",
    }

    with requests.post(url, headers=headers, json=data, stream=True) as response:
        if response.status_code == 200:
            # Create a temporary file to store the audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.opus') as temp_file:
                for chunk in response.iter_content(chunk_size=4096):
                    temp_file.write(chunk)
                #print(temp_file.name) #Debug Only
                return temp_file.name
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

def play_audio(audio_file_path):
    if audio_file_path:
        # Calculate the time elapsed since the start of the script
        #elapsed_time = time.time() - start_time
        #print(f"Time taken to start playing audio clip: {elapsed_time} seconds")
        #print("Attempting to play audio.") #Debug Only
        with sf.SoundFile(audio_file_path, 'r') as sound_file:
            audio = pyaudio.PyAudio()
            stream = audio.open(format=pyaudio.paInt16, channels=sound_file.channels, rate=sound_file.samplerate, output=True)
            data = sound_file.read(1024,dtype='int16')
            
            while len(data) > 0:
                stream.write(data.tobytes())
                data = sound_file.read(102,dtype='int16')

            stream.stop_stream()
            stream.close()
            audio.terminate()

def generate_text(prompt):

    completion = aiclient.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[
            {"role": "system", "content": prompt}
        ],
        stream=True,
        temperature=0,
        max_tokens=100
    )

    sentence = ''
    sentences = []
    sentence_end_chars = {'.', '?', '!', '\n'}

    for chunk in completion:
        content = chunk.choices[0].delta.content
        if content is not None:
            for char in content:
                sentence += char
                if char in sentence_end_chars:
                    sentence = sentence.strip()
                    if sentence and sentence not in sentences:
                        sentences.append(sentence)
                        audio_generation_queue.put(sentence)
                        print(f"Queued sentence: {sentence}")  # Logging queued sentence
                    sentence = ''
    return sentences

def generate_prompt(board, recent_moves, last_move, move_classification):

    if emulated_board.fullmove_number < 6:
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        """
        You are a spectator watching the following chess game.
        You reference the most recent moves and the current state of the board to get an understanding of the game, but only talk about the last move.
        You make small one or two word interjections equal to or less than 1 completion token. 
        
        """
    
    elif move_classification == 'blunder':
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        """
        You are a spectator watching the following chess game.
        You reference the most recent moves and the current state of the board to get an understanding of the game, but only talk about the last move.
        You have just witnessed a blunder. Make big scene about it with a snarky, funny, and/or rude comment equal to or under 1 completion token.
        """

    elif move_classification == 'normal':
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        """
        You are a spectator watching the following chess game.
        You reference the most recent moves and the current state of the board to get an understanding of the game, but only talk about the last move.
        You have just witnessed a normal move. Make a interjection which is one or two words which displays how uninteresting and obvious it is that is equal to or under 1 completion token.
        """

    else:
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        """
        You are a spectator watching the following chess game.
        You are actively disgusted at how the players a playing. You continously say how you could be playing better.
        You make short, nasty, witty, and funny remarks about the position.
        You reference the most recent moves and the current state of the board to get an understanding of the game, but only talk about the last move and its relation to the previous move, if needed.
        Make a remark equal to or less than 1 completion token. 
        """
    return prompt

def commentate(mode, random_chance = None):
    # Determine if we should generate text based on move classification and fullmove number
    enable_random = move_classification == 'normal' or emulated_board.fullmove_number < 6

    # Determine if we should generate text based on random chance
    enable_generate = not enable_random or (enable_random and random.random() < random_chance)

    prompt = generate_prompt(emulated_board, recent_moves, san_move, move_classification)

    # Generate on white's turn
    if mode == 'white' and not emulated_board.turn and enable_generate:
        response = generate_text(prompt)
        print(response)

    # Generate on black's turn
    elif mode == 'black' and emulated_board.turn and enable_generate:
        response = generate_text(prompt)
        print(response)
    

# To be used alongside Stockfish to evaulate moves, since ChatGPT kinda sucks at it
def classify_move(change_in_evaluation):
    if change_in_evaluation <= -200:
        return 'blunder'
    elif -200 < change_in_evaluation <= -100:
        return 'mistake'
    elif change_in_evaluation >= 200:
        return 'good'
    else:
        return 'normal'
    
def get_top_3_moves(board):
    with engine.analysis(board, multipv=3) as analysis:
        best_moves_san = []
        for info in analysis:
            if len(best_moves_san) >= 3:
                break
            if info.get("pv"):
                move_san = board.san(info["pv"][0])
                best_moves_san.append(move_san)
    return best_moves_san

while True:
    # Check for ongoing games
    ongoing_games = client.games.get_ongoing()
    if ongoing_games:
        game_id = ongoing_games[0]['gameId']
        print(f"Found an ongoing game: {game_id}")

        current_board_stream = client.board.stream_game_state(game_id)

        for game_state in current_board_stream:
            #print(game_state)

            if 'white' in game_state:
                if 'aiLevel' in game_state['white']:
                    player_colour = 'black'
                else:
                    player_colour = 'white'
            
            #print(player_colour)

            if game_state.get('status') in ['resign', 'mate', 'stalemate']:
                print('Game done.')
                emulated_board.reset()
                break

            else:
                if game_state['type'] == 'gameFull':
                    moves = game_state['state']['moves'].split()
                elif game_state['type'] == 'gameState':
                    moves = game_state['moves'].split()

                if moves:
                    last_move = moves[-1]

                    # Convert UCI to SAN before making the move
                    san_move = emulated_board.san(chess.Move.from_uci(last_move))

                    # LAST PLAYER MOVE INFO
                    # TEST METHOD FOR INCREASING CHATGPT KNOWLEDGE OF GAME
                    # Check if the last move was made by the player
                    if (emulated_board.turn and player_colour == 'white') or (not emulated_board.turn and player_colour == 'black'):
                        last_player_move.append(san_move)

                    # Keep array to be length 1
                    if len(last_player_move) > 1:
                        last_player_move.pop(0)
                    #print(last_player_move)
                    ######################################################
                                    
                    recent_moves.append(san_move)
                    #print(move_san)

                    # Only referencing last 3 moves for recent moves
                    if len(recent_moves) > 3:
                        recent_moves.pop(0)

                    # Evaluate the position before making the move
                    if previous_score is None:
                        analysis_info = engine.analyse(emulated_board, chess.engine.Limit(depth=5))
                        previous_score = analysis_info.get("score")

                    emulated_board.push_uci(last_move)

                    # TEST METHOD FOR INCREASING CHATGPT KNOWLEDGE OF GAME
                    # Get the top 3 moves from Stockfish and convert them to SAN
                    top_3_moves_san = get_top_3_moves(emulated_board)

                    # Format the moves into a string
                    formatted_moves = ", ".join([f"{i+1}{'st' if i == 0 else 'nd' if i == 1 else 'rd'} best: {move}" for i, move in enumerate(top_3_moves_san)])
                    print("Top 3 moves:", formatted_moves)
                    ######################################################

                    # Evaluate the position after making the move
                    new_analysis_info = engine.analyse(emulated_board, chess.engine.Limit(depth=5))
                    new_score = new_analysis_info.get("score")
                    #print(new_score)

                    # Evaluating moves based off of change in centipawn score using Stockfish
                    if emulated_board.turn:  # White turn
                        change_in_evaluation = previous_score.black().score(mate_score=-10000) - new_score.black().score(mate_score=-10000)
                        change_in_evaluation *= -1
                    else:  # Black turn
                         change_in_evaluation = new_score.white().score(mate_score=10000) - previous_score.white().score(mate_score=10000)

                    move_classification = classify_move(change_in_evaluation)
                    #print(f"Move classification: {move_classification}")

                    previous_score = new_score

                    commentate(player_colour, 0.5)
