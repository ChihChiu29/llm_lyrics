# Goal

Create a Python based agent using Ollama-LLM with chat interface that can create lyrics for Chinese songs.


# Product Description

The agent has a CLI chat interface. 

== Initialization ===
When the agent starts, at the very beginning, it checks if it needs to resume from previous work; see “resuming workflow” section below.

If it’s a new workflow, it queries local Ollama instances and lists all available models, then prompts the user to pick one (default to first in list). Then, it takes in song styles from `song_styles.md`, lists them with indices, then asks users to pick one style. It then writes the choices to `tmp_init.md`.

=== Write Song Description ===
After that, it would come up with a short description or story on what the song would be about, what scenario the song captures, etc., and write it to `tmp_song_description_01.md`. Then it prints out the description and asks users for suggestions, then modifies it based on user suggestions. Each time it modifies the description, it writes it to a file with an increasing index, like `tmp_song_description_02.md` for the second iteration, and so on. Each time it prints out the index, the new description, then asks users to give new suggestions. It can also understand suggestions like “let’s go back to version x”. Eventually, when the user says the description is good, it saves the version user approved in `tmp_song_approved.md`.

=== Write Song Lyrics ===
Next, it takes the approved song description to write lyrics. It reads `song_lyrics_instruction.md` for extra instruction, and writes the song’s lyrics to a file, starting with `tmp_song_lyrics_01.md`. After that, it asks the user for suggestions, then writes the modified lyrics into files with increased index, like `tmp_song_lyrics_02.md` for the second revision. Each time it prints an index, the new lyrics, then asks the user for suggestions. Eventually, when the user says the lyrics look good, it comes up with a title for the song, then writes it to `<title>.txt`, with song title, black line, then lyrics.


=== Ending ===
Once a song’s lyric file is written, the agent asks whether the user wants to create a new song. If the user’s response is “yes” then first delete all the temporary files (those starting with `tmp_`), then go back to the “initialization stage”. If the user’s response is “no”, then go back to the “write song lyrics” stage as if the user hasn’t approved the lyrics.


# Resuming workflow

When the agent starts, it looks for existing `tmp_*` files to understand which stage it left over with last time, then auto resume from it. It would always assume it’s at a later stage when files from multiple stages exist. For example, if `tmp_song_lyrics_01.md` exists, it would assume that the user has already approved the song description and it’s in the last “write song lyrics” stage. It would look for the largest index from all `tmp_song_lryics_<index>.md` files, then resume from there.


# Custom commands

 During the whole flow, the user can use special commands:
- “/new”: restarts the tool, starting with model selection.
- “/desc”: if it’s in the “write song lyrics” stage, this commands put the agent back to the “write song description” stage, which prints out `tmp_song_approved.md` for user suggestions, then continue write to `tmp_song_description_<index>.md` with index being previous largest index + 1.
- “/quit”: exits the agent
