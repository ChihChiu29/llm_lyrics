# Goal
Create a multi-client webpage chrome extension to communicate with various AI web UIs (DeepSeek, ChatGPT, Claude, Qwen).

# Design

- The Chrome extension operates via a **Per-Tab Toggle**:
  - The extension can be toggled ON/OFF on a per-tab basis. It only processes interactions in explicitly enabled tabs.

- The extension has two modes: processing mode, and idle mode.
  - In idle mode, it polls the communication manager every 15 seconds (when enabled) to see if there is a new interaction to process. If yes, it goes into processing mode.
  - In processing mode, it processes the interactions, and when there is no more interaction to process, it goes back to idle mode.

- During processing:
  - It peeks for the next interaction, reading the target `client` field.
  - It finds an enabled tab matching the target client's URL (e.g., chat.deepseek.com for DeepSeek).
  - It utilizes a modular **Adapter Architecture** to interact with the specific web UI.
  - It inputs the text into the web UI, then clicks the send message button.
  - It tells the communication manager to change the interaction's status to RUNNING.
  - It periodically checks if the response is ready (e.g., by checking for SVG Stop icons, loading spinners, or blinking cursors).
  - Once the response is ready, it extracts the response from the web UI, then tells the communication manager to update the interaction with the response and set its status to COMPLETED.
    - Note that the UI has the whole conversation history, and it should only return the last response.

# TODO

- Implement the chrome extension in current directory. Referencing the api.md in communication manager directory for the APIs.

