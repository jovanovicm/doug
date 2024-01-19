# ♟😐♟ Doug, the friendly street hustler♟😐♟
### What is Doug?
Doug allows you to play **Player vs. Computer** games on **Lichess** with real-time audio commentary reflective of the game from
Doug's perspective (as the computer). 

### Who is Doug?
Doug is a street hustler who is known for being disgusted at the level of chess played by anyone.
He has become famous for his vocal style of play across the board.

Doug does not hold back on the trash talk, and will make you regret every bad move you make.

### Table of Contents
- **[How to Use Doug](#how-to-use)**
  - [Prerequisites](#prerequisites)
  - [Installation and Use](#installation-and-use)
  - [Known Issues](#known-issues)
- **[Methodology](#methodology)**
  - [What led to the creation of Doug?](#what-led-to-the-creation-of-doug)
  - [How does Doug work?](#how-does-doug-work)
  - [Challenges and Solutions](#challenges-and-solutions)
    - [Issues with the Lichess API](#issues-with-the-lichess-api)
    - [Introducing more context](#introducing-more-context)
- **[Pending Improvements](pending=improvements)**

## How to Use
### Prerequisites
- You must have a [Lichess](https://lichess.org/) and [OpenAI](https://openai.com/) account
- Create a [Personal API access token](https://lichess.org/account/oauth/token) to use the Lichess API when you play your games
- Create an [OpenAI API key](https://platform.openai.com/api-keys), and [fund your account](https://platform.openai.com/account/billing/overview)
> [!NOTE]
> A game of chess costs around $0.10

### Installation and Use
1. Clone the repository to your local environment and install required libraries

```bash
git clone https://github.com/jovanovicm/doug
cd doug
pip install -r requirements.txt
```
>[!NOTE]
>If you are not using Windows, you must [install a different version of Stockfish](https://stockfishchess.org/download/) and replace the folder

2. Change the name of **config_template.py** to **config.py** and populate the variables with your API keys
3. Run **doug.py** before playing a game

### Known Issues

- `soundfile.LibsndfileError: Error opening: File contains data in an unimplemented format`
  - Resolve issue with: `pip install --force-reinstall soundfile`

## Methodology
### What led to the creation of Doug?
I wanted to create something that I would enjoy using while also investigating the uses of Generative AI. I also used this project as an opportunity to improve my Python skills and overall code development ability.

ChatGPT helped a lot...

### How does Doug work?
Doug uses the Lichess API to get real-time information about your chess games. It then feeds this information into a prompt used by the OpenAI API to generate a text-based analysis of the game. 
This text-based analysis is then sent to a text-to-speech model, again using the OpenAI API, which then outputs Doug's commentary.

### Challenges and Solutions
Since ChatGPT is known to hallucinate, [especially while playing and interpreting chess games](https://twitter.com/JoINrbs/status/1624351822621315072?lang=en), you need to provide a lot of context within each prompt for an appropriate analysis to happen.

#### Issues with the Lichess API
Part of the information given by the Lichess API is the sequence of moves made in your game, which comes in the form of Long Algebraic Notation (LAN). This notation, like all notations, makes use of the grid system on a chess board and identifies the starting and ending squares of the piece moved.

>**Example of LAN**: 
>
>`e2e4 c7c6 f2f4 d7d5 e4e5 c8f5 d2d4 e7e6 g1f3 c6c5 f1b5 b8d7`

For example, `e2e4` means that the piece previously on e2 has moved to e4. Since this notation lacks information about the piece that is being moved, ChatGPT will start hallucinating after the first few opening moves have been made.

Another issue with referencing this sequence of moves is that it becomes very long in the end game, which increases the length of the prompt, therefore increasing the amount of time needed to get a response from the OpenAI API.

#### Introducing more context
To help out with the issue of hallucinations, we must introduce more context related to the moves made, and the state of the game. To do this, I use the `chess` library for python to emulate the chess game being played on Lichess within our code. Using this library, we can convert the LAN moves to a more informative notation, the Short Algebraic Notation (SAN), which includes the context of the piece being moved and what it is doing. 

>**Example of SAN**:
>
>`e4 c6 f4 d5 e5 Bf5 d4 e6 Nf3 c5 Bb5+ Nd7`

On top of this, we also introduce another notation called the Forsyth-Edwards Notation (FEN) which gives an overhead view of the board where uppercase letters signify White's pieces, while lowercase letters signify Black's pieces. 

>**Example of FEN**: 
>```
>r . . q k b n r
>p p . n . p p p
>. . . . p . . .
>. B p p P b . .
>. . . P . P . .
>. . . . . N . .
>P P P . . . P P
>R N B Q K . . R
>```

Stockfish is also integrated alongside the game to give proper game analysis, and to allow for context-dependent prompts. When all these forms of context are combined, a prompt is created and sent to the OpenAI API. 

>**Example prompt**:
>```
>elif move_classification == 'blunder':
>        prompt = f"Current state of the board: {board}. The last move is {last_move}. The most recent moves are: {', '.join(recent_moves)}."
>```

>[!NOTE]
>Since OpenAI API calls do not reference previous API calls for context, prompts must convey the momentum of the game

## Pending Improvements

