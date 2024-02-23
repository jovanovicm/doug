import berserk
import requests, pyaudio, threading, queue, tempfile
import soundfile as sf
import random
import chess
import chess.engine
from openai import OpenAI
import pygame
import time
import os
from dotenv import load_dotenv

# API KEYS #
load_dotenv()

LICHESS_API_TOKEN = os.getenv('LICHESS_API_TOKEN')
OPENAI_API_TOKEN = os.getenv('OPENAI_API_TOKEN')

# PROGRAM TIMEOUT #
timeout_start = None

# AUDIO #
# Thanks to https://github.com/ggoonnzzaallo/llm_experiments for the streamed text + audio solution

pygame.mixer.init()

is_first_audio_played = False  # Flag to check if the first audio has been played

# Queues for audio generation and playback
audio_generation_queue = queue.Queue()
audio_playback_queue = queue.Queue()


# CHESS CLIENT #
session = berserk.TokenSession(LICHESS_API_TOKEN)
client = berserk.Client(session=session)

emulated_board = chess.Board()
engine = chess.engine.SimpleEngine.popen_uci('stockfish/stockfish-windows-x86-64-avx2.exe')

recent_moves = [] # Last 3 moves played on the board
last_player_move = []
player_colour = ''
computer_colour = ''
previous_score = None # Scoring from Stockfish
enable_random = False

# OPENAI CLIENT #
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
    while True:
        audio_file_path = audio_playback_queue.get()
        if audio_file_path is None:
            break
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
        "Authorization": f'Bearer {OPENAI_API_TOKEN}'
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
                return temp_file.name
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None

def play_audio(audio_file_path):
    if audio_file_path:
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
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": prompt}
        ],
        stream=True,
        temperature=0.5,
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
                    sentence = ''
    return sentences

def generate_prompt(board, recent_moves, last_move, move_classification, colour, top_line=None):

    if move_classification == 'early':
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        f"You are playing this chess game as {colour} and are talking to your opponent" \
        """
        You reference the most recent moves and the current state of the board to get an understanding of the game, but only talk about the last move.
        Talk about the moves with natural language; do not talk using chess notations.
        You make small interjections which resemble expressions of thought like "hmm" or identifying what opening it is.
        Do not talk about the analysis of the position, what the thought behind a move is, or what a move is managing to do.
        Keep your remark under 4 words and under 1 completion token.
        """
    
    elif move_classification == 'blunder':
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        f"You are playing this chess game as {colour} and are talking to your opponent" \
        """
        You reference the most recent moves and the current state of the board to get an understanding of the game.
        You have just witnessed your opponent make a blunder. 
        """ \
        f"You reference the top line to understand why it is a blunder; top line for you: {top_line}" \
        """
        Talk about the moves with natural language; do not talk using chess notations.
        Make a big scene about the move, sometimes eluding to why it is bad, with a snarky and rude comment using deadpan humour equal.
        The remark must be under 20 words and under 1 completion token.
        """

    
    elif move_classification == 'mistake':
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        f"You are playing this chess game as {colour} and are talking to your opponent" \
        """
        You reference the most recent moves and the current state of the board to get an understanding of the game.
        You have just witnessed your opponent make a mistake. 
        """ \
        f"You reference the top line to understand why it is a mistake; top line for you: {top_line}" \
        """
        Talk about the moves with natural language; do not talk using chess notations.
        Make a condensending remark about the move, sometimes eluding to why it is bad.
        The remark must be under 15 words and under 1 completion token.
        """

    elif move_classification == 'normal':
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        f"You are playing this chess game as {colour} and are talking to your opponent" \
        """
        You reference the most recent moves and the current state of the board to get an understanding of the game, but only talk about the last move.
        Talk about the moves with natural language; do not talk using chess notations.
        You have just witnessed your opponent make a normal move.
        Make a condensending interjection which is up to 10 words which vocalizes thinking about what your opponent will do, or thinking to yourself.
        """

    elif move_classification == 'good':
        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}." \
        f"You are playing this chess game as {colour} and talking to your opponent" \
        """
        You reference the most recent moves and the current state of the board to get an understanding of the game, but only talk about the last move.
        Talk about the moves with natural language; do not talk using chess notations.
        You have just witnessed your opponent make a good move.
        You think to yourself about how you knew that move was coming.
        You make a funny remark with a slightly worried tone about the position equal to or under 20 words.
        """

    return prompt

prompt_probabilities = {
    'early': 0.20,
    'blunder': 1,  
    'mistake': 1,
    'good': 0.75,     
    'normal': 0.35    
}

def commentate(mode, move_classification):
    # Check if it's the player's turn to generate a response
    if (mode == 'white' and not emulated_board.turn) or (mode == 'black' and emulated_board.turn):
        if random.random() < prompt_probabilities.get(move_classification):
            prompt = generate_prompt(emulated_board, recent_moves, san_move, move_classification, computer_colour, top_lines_str)
            response = generate_text(prompt)
            print(response)


# To be used alongside Stockfish to evaulate moves, since ChatGPT kinda sucks at it
def classify_move(change_in_evaluation):
    if emulated_board.fullmove_number < 6:
        classification = 'early'
        if change_in_evaluation <= -200:
            classification = 'blunder'
    elif change_in_evaluation <= -200:
        classification = 'blunder'
    elif -200 < change_in_evaluation <= -100:
        return 'mistake'
    elif change_in_evaluation >= 200:
        classification =  'good'
    else:
        classification = 'normal'
    
    return classification
    

def get_top_line(board, engine, depth):
    limit = chess.engine.Limit(depth=depth)
    info = engine.analyse(board, limit)

    # Extract the principal variation (best line)
    if "pv" in info and len(info["pv"]) >= depth:
        line_san = ' '.join([board.san(move) for move in info["pv"][:depth]])
        formatted_line = f"Best line: {line_san}"
        return formatted_line

    return "No line available"

while True:
    # Timeout
    if timeout_start is not None and (time.time() - timeout_start) > 120:
        print("No new game started within 2 minutes. Exiting.")
        break

    # Check for ongoing games
    ongoing_games = client.games.get_ongoing()
    if ongoing_games:
        game_id = ongoing_games[0]['gameId']
        print(f"Found an ongoing game: {game_id}")

        current_board_stream = client.board.stream_game_state(game_id)

        for game_state in current_board_stream:
            if 'white' in game_state:
                if 'aiLevel' in game_state['white']:
                    player_colour = 'black'
                    computer_colour = 'white'
                else:
                    player_colour = 'white'
                    computer_colour = 'black'

            if game_state['type'] == 'gameFull':
                moves = game_state['state']['moves'].split()
            elif game_state['type'] == 'gameState':
                moves = game_state['moves'].split()

            if game_state.get('status') == 'resign': 
                print('Game done.')
                emulated_board.reset()
                timeout_start = time.time()
                break    

            if moves:
                last_move = moves[-1]

                # Convert UCI to SAN before making the move
                san_move = emulated_board.san(chess.Move.from_uci(last_move))
                                
                recent_moves.append(san_move)

                # Only referencing last 3 moves for recent moves
                if len(recent_moves) > 3:
                    recent_moves.pop(0)

                # Evaluate the position before making the move
                if previous_score is None:
                    analysis_info = engine.analyse(emulated_board, chess.engine.Limit(depth=5))
                    previous_score = analysis_info.get("score")

                emulated_board.push_uci(last_move)

                # Evaluate the position after making the move
                new_analysis_info = engine.analyse(emulated_board, chess.engine.Limit(depth=5))
                new_score = new_analysis_info.get("score")

                # Evaluating moves based off of change in centipawn score using Stockfish
                if emulated_board.turn:  # White turn
                    change_in_evaluation = previous_score.black().score(mate_score=-10000) - new_score.black().score(mate_score=-10000)
                    change_in_evaluation *= -1
                else:  # Black turn
                    change_in_evaluation = new_score.white().score(mate_score=10000) - previous_score.white().score(mate_score=10000)

                move_classification = classify_move(change_in_evaluation)
                previous_score = new_score

                print(move_classification)

                top_lines_str = ''
                if move_classification in ['blunder','mistake']:
                    top_lines_str = get_top_line(emulated_board, engine, depth=3)

                commentate(player_colour, move_classification)

                if game_state.get('status') in ['mate', 'stalemate']:
                    print('Game done.')
                    emulated_board.reset()
                    timeout_start = time.time()
                    break

def cleanup_queues():
    audio_generation_queue.join()
    audio_generation_queue.put(None) 
    audio_playback_queue.join() 
    audio_playback_queue.put(None) 

cleanup_queues()

audio_generation_thread.join()
audio_playback_thread.join()      

pygame.mixer.quit()

os._exit(1)

