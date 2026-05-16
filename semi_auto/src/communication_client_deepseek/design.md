# Goal
Create a deepseek webpage chrome extension to communicate with deepseek web UI.

# Design

- The Chrome extension has two modes: processing mode, and idle mode.
  - In idle mode, it polls the communication manager every 1 min to see if there is a new interaction to process. If yes, it goes into processing mode.
  - In processing mode, it processes the interactions, and when there is no more interaction to process, it goes back to idle mode.

- During processing:
  - It peeks for the next interaction.
  - It then inputs that into the qwen web UI, then click on the send message button.
  - It then tells the communication manager to change the interaction's status to processing.
  - It then periodically (every 10 seconds) checks if the response is ready (it can checks this by checking the status of the send message button on qwen web UI).
  - Once the response is ready, it extracts the response from the qwen web UI, then tells the communication manager to update the interaction with the response and set its status to completed.
    - Note that the UI has the whole conversation history, and it should only return the last response.

# TODO

- Implement the chrome extension in current directory. Referencing the api.md in communication manager directory for the APIs.

