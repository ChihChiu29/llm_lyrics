# Goal
Create a lyric creator command line tool.

# Tool Description

The DEFAULT_CLIENT is "deepseek"..

1. When the tool starts, it loads all prompts from "data/" directory.

2. It then query ollama server to list all available models, and allow user to choose one. It also create a client to communicate with the communication manager.

3. It asks user if they wants to input a style or lyrics.

4a. If user choose a style, it then asks user to give a style. It would append the user input to "data/灵感_prompt.md", then send it to commmunication manager with DEFAULT_CLIENT.

4b. If user choose lyrics, it'll use the "data/选风格_prompt.md" and append the user input to it, then send it to commmunication manager with DEFAULT_CLIENT.

5. Then, it'll ask user to give input (usually a choice, but could be free formed). The input is sent to the communication manager as-is with DEFAULT_CLIENT.

6. Once it gets the response, it'll use the "data/填写大师_prompt.md" *as is* (not appended with anything), and send that to commmunication manager with DEFAULT_CLIENT.

7. Once it gets the response, it'll use the "data/音乐总监_prompt.md" *as is* (not appended with anything), and send that to commmunication manager with DEFAULT_CLIENT.

8. Once it gets the response, it'll call the ollama client with the model user picked from step #1, and extract the score (1-10) from response in step #7. If the score is higher than 9.2, go to the last step.

9. If the score is lower than 9.2, it'll use the "data/制作人_prompt.md" *as is* (not appended with anything), and send that to commmunication manager with DEFAULT_CLIENT.

10. Repeat step #5-#9 until the score is higher than 9.2, or it has been 5 iterations.

11. If it has been 5 iterations and the score is still lower than 9.2, it'll ask user if they want to continue, and if yes, reset the iteration counter then repeat from step #5. Otherwise go to the last step.

99. (Last step) Asks if user wants to continue, and if yes, go back to step #3.

During the whole process, create a "output/<date>_<hour:min>_log.txt" to log the whole process's interaction with communication manager and with ollama.
